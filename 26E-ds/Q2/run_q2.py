from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "Q2"))

import mm_data as md
from model import MODEL_NAMES, build_model, encode_sequence, load_encoder

OUT = PROJECT / "Q2"
CACHE = OUT / "cache"
RESULTS = OUT / "results"
DEVICE = torch.device("cpu")
SEED = 20260924
MODALITIES = md.MODALITIES
STRATEGIES = ("clean", "augment_light", "augment_heavy", "curriculum")


def load_cache() -> dict:
    data = np.load(CACHE / "encoded_sequences.npz", allow_pickle=True)
    cache = {key: data[key] for key in data.files}
    return cache


def tensors(cache: dict, split: str) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    sequences = [torch.from_numpy(cache[f"{split}_{m}_seq"]).float() for m in MODALITIES]
    masks = [torch.from_numpy(cache[f"{split}_{m}_mask"]).float() for m in MODALITIES]
    return sequences, masks


def clone(sequences: list[torch.Tensor]) -> list[torch.Tensor]:
    return [item.clone() for item in sequences]


def corrupt_batch(sequences: list[torch.Tensor], masks: list[torch.Tensor], rng: np.random.Generator,
                  ratio_range: tuple[float, float], drop_prob: float,
                  multi_modality_prob: float = 0.35) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    batch, steps, _ = sequences[0].shape
    out_seq = clone(sequences)
    out_mask = [item.clone() for item in masks]
    for row in range(batch):
        if rng.random() > drop_prob:
            continue
        if rng.random() < multi_modality_prob:
            chosen = list(rng.choice(3, size=int(rng.integers(2, 4)), replace=False))
        else:
            chosen = [int(rng.integers(0, 3))]
        for modality in chosen:
            ratio = float(rng.uniform(*ratio_range))
            segments = md.sample_missing_segments(rng, steps, ratio, max_segments=3)
            for start, end in segments:
                out_seq[modality][row, start:end + 1] = 0.0
                out_mask[modality][row, start:end + 1] = 0.0
    return out_seq, out_mask


def class_weights(labels: np.ndarray) -> torch.Tensor:
    counts = np.bincount(labels, minlength=3).astype(np.float64)
    return torch.tensor(counts.sum() / (3.0 * np.maximum(counts, 1.0)), dtype=torch.float32)


def evaluate(model: nn.Module, sequences: list[torch.Tensor], masks: list[torch.Tensor],
             labels_cls: np.ndarray, labels_reg: np.ndarray, batch: int = 256) -> dict:
    model.eval()
    predictions_cls, predictions_reg, masses, temporal = [], [], [], []
    with torch.no_grad():
        for start in range(0, len(labels_cls), batch):
            stop = min(start + batch, len(labels_cls))
            seq = [item[start:stop] for item in sequences]
            msk = [item[start:stop] for item in masks]
            output = model(seq, msk)
            predictions_cls.append(output["logits"].argmax(dim=1).numpy())
            predictions_reg.append(output["regression"].numpy())
            masses.append(output["modality_mass"].numpy())
            temporal.append(output["temporal_weight"].numpy())
    pred_cls = np.concatenate(predictions_cls)
    pred_reg = np.concatenate(predictions_reg)
    result = {
        **md.metrics_classification(pred_cls, labels_cls),
        **md.metrics_regression(pred_reg, labels_reg),
        "modality_mass_mean": np.concatenate(masses).mean(axis=0).tolist(),
    }
    result["temporal_weight"] = np.concatenate(temporal)
    return result


def train_model(name: str, cache: dict, strategy: str, epochs: int, batch: int, lr: float,
                seed: int, hidden: int = 192, verbose: bool = True) -> tuple[nn.Module, dict]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = build_model(name, hidden).to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr * 0.1)
    train_seq, train_mask = tensors(cache, "train")
    valid_seq, valid_mask = tensors(cache, "valid")
    labels_cls = cache["train_label_cls"]
    labels_reg = cache["train_label_reg"]
    ce = nn.CrossEntropyLoss(weight=class_weights(labels_cls))
    huber = nn.SmoothL1Loss(beta=0.5)
    n_train = len(labels_cls)
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        if strategy == "clean":
            ratio_range, drop_prob = (0.0, 0.0), 0.0
        elif strategy == "augment_light":
            ratio_range, drop_prob = (0.05, 0.30), 0.50
        elif strategy == "augment_heavy":
            ratio_range, drop_prob = (0.10, 0.60), 0.60
        else:
            progress = epoch / epochs
            ratio_range = (0.05, 0.10 + 0.45 * progress)
            drop_prob = 0.25 + 0.35 * progress
        order = rng.permutation(n_train)
        total = 0.0
        for start in range(0, n_train, batch):
            index = order[start:start + batch]
            seq = [item[index] for item in train_seq]
            msk = [item[index] for item in train_mask]
            if drop_prob > 0:
                seq, msk = corrupt_batch(seq, msk, rng, ratio_range, drop_prob)
            y_cls = torch.from_numpy(labels_cls[index]).long()
            y_reg = torch.from_numpy(labels_reg[index]).float()
            output = model(seq, msk)
            loss = ce(output["logits"], y_cls) + huber(output["regression"], y_reg)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            total += float(loss.item()) * len(index)
        scheduler.step()
        history.append({"epoch": epoch, "loss": total / n_train})
        if verbose and (epoch % 5 == 0 or epoch == 1):
            print(f"    [{name}/{strategy}] epoch {epoch} loss {history[-1]['loss']:.4f}", flush=True)
    metrics = evaluate(model, valid_seq, valid_mask, cache["valid_label_cls"], cache["valid_label_reg"])
    metrics.pop("temporal_weight", None)
    return model, {"model": name, "strategy": strategy, "history": history, "valid": metrics}


def window_segments(steps: int, position: str, length: int) -> list[tuple[int, int]]:
    if position == "front":
        start = 0
    elif position == "middle":
        start = max(0, (steps - length) // 2)
    else:
        start = max(0, steps - length)
    return [(start, start + length - 1)]


def sweep_rate(model: nn.Module, cache: dict, modality: str | None, ratios: list[float],
               repeats: int, seed: int, split: str = "valid") -> list[dict]:
    rng = np.random.default_rng(seed)
    base_seq, base_mask = tensors(cache, split)
    labels_cls = cache[f"{split}_label_cls"]
    labels_reg = cache[f"{split}_label_reg"]
    rows = []
    for ratio in ratios:
        collected = []
        for _ in range(repeats):
            seq = clone(base_seq)
            msk = [item.clone() for item in base_mask]
            targets = range(3) if modality is None else [MODALITIES.index(modality)]
            for row in range(len(labels_cls)):
                for index in targets:
                    segments = md.sample_missing_segments(rng, seq[index].shape[1], ratio, max_segments=3)
                    for start, end in segments:
                        seq[index][row, start:end + 1] = 0.0
                        msk[index][row, start:end + 1] = 0.0
            outcome = evaluate(model, seq, msk, labels_cls, labels_reg)
            outcome.pop("temporal_weight", None)
            collected.append(outcome)
        rows.append({
            "missing_ratio": ratio,
            "target": modality or "all",
            "accuracy": float(np.mean([item["accuracy"] for item in collected])),
            "accuracy_std": float(np.std([item["accuracy"] for item in collected])),
            "macro_f1": float(np.mean([item["macro_f1"] for item in collected])),
            "macro_f1_std": float(np.std([item["macro_f1"] for item in collected])),
            "mae": float(np.mean([item["mae"] for item in collected])),
            "mae_std": float(np.std([item["mae"] for item in collected])),
            "pearson": float(np.mean([item["pearson"] for item in collected])),
            "pearson_std": float(np.std([item["pearson"] for item in collected])),
        })
    return rows


def sweep_window(model: nn.Module, cache: dict, modality: str, position: str, lengths: list[int],
                 split: str = "valid") -> list[dict]:
    base_seq, base_mask = tensors(cache, split)
    labels_cls = cache[f"{split}_label_cls"]
    labels_reg = cache[f"{split}_label_reg"]
    rows = []
    index = MODALITIES.index(modality)
    for length in lengths:
        seq = clone(base_seq)
        msk = [item.clone() for item in base_mask]
        segments = window_segments(seq[index].shape[1], position, length)
        for row in range(len(labels_cls)):
            for start, end in segments:
                seq[index][row, start:end + 1] = 0.0
                msk[index][row, start:end + 1] = 0.0
        outcome = evaluate(model, seq, msk, labels_cls, labels_reg)
        outcome.pop("temporal_weight", None)
        rows.append({
            "modality": modality, "position": position, "window_length": length,
            "missing_ratio": length / seq[index].shape[1],
            "accuracy": outcome["accuracy"], "macro_f1": outcome["macro_f1"],
            "mae": outcome["mae"], "pearson": outcome["pearson"],
        })
    return rows


def response_surface(model: nn.Module, cache: dict, modality: str, split: str = "valid") -> dict:
    base_seq, base_mask = tensors(cache, split)
    labels_cls = cache[f"{split}_label_cls"]
    labels_reg = cache[f"{split}_label_reg"]
    index = MODALITIES.index(modality)
    steps = base_seq[index].shape[1]
    positions = np.arange(0, steps, 4)
    lengths = np.arange(4, 31, 3)
    mae = np.zeros((len(positions), len(lengths)), dtype=np.float64)
    acc = np.zeros_like(mae)
    for i, start in enumerate(positions):
        for j, length in enumerate(lengths):
            end = min(steps - 1, start + length - 1)
            seq = clone(base_seq)
            msk = [item.clone() for item in base_mask]
            seq[index][:, start:end + 1] = 0.0
            msk[index][:, start:end + 1] = 0.0
            outcome = evaluate(model, seq, msk, labels_cls, labels_reg)
            mae[i, j] = outcome["mae"]
            acc[i, j] = outcome["accuracy"]
    return {"positions": positions.tolist(), "lengths": lengths.tolist(),
            "mae": mae.tolist(), "accuracy": acc.tolist(), "modality": modality}


def main() -> int:
    parser = argparse.ArgumentParser(description="问题二鲁棒融合模型训练、消融、缺失规律分析与附件 3 推理")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1.5e-3)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--infer-only", action="store_true", help="复用已保存模型与报告，仅重跑附件 3 推理")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    cache = load_cache()

    if args.infer_only:
        report_path = RESULTS / "q2_report.json"
        report_all = json.loads(report_path.read_text(encoding="utf-8"))
        model = build_model("robust_full")
        model.load_state_dict(torch.load(RESULTS / "robust_model.pt", map_location=DEVICE))
        model.eval()
        stats = np.load(CACHE / "norm_stats.npz")
        norm = {m: {"mean": stats[f"{m}_mean"], "std": stats[f"{m}_std"]} for m in MODALITIES}
        a3 = md.load_a3()
        a3_inputs = infer_a3(model, a3, norm)
        np.savez_compressed(RESULTS / "a3_predictions.npz", **a3_inputs["arrays"])
        import pandas as pd
        pd.DataFrame(a3_inputs["rows"]).to_csv(OUT / "附件3_预测结果.csv", index=False, encoding="utf-8-sig")
        pd.DataFrame(a3_inputs["explain_rows"]).to_csv(OUT / "附件3_缺失影响分析.csv", index=False,
                                                       encoding="utf-8-sig")
        report_all["a3_summary"] = a3_inputs["summary"]
        report_path.write_text(json.dumps(report_all, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "a3_summary": a3_inputs["summary"]}, ensure_ascii=False, indent=2))
        return 0

    print("== strategy comparison ==", flush=True)
    strategy_reports = []
    best = None
    for strategy in STRATEGIES:
        started = time.time()
        model, report = train_model("robust_full", cache, strategy, args.epochs, args.batch, args.lr, SEED)
        report["seconds"] = round(time.time() - started, 1)
        strategy_reports.append(report)
        print(f"  {strategy}: acc={report['valid']['accuracy']:.4f} f1={report['valid']['macro_f1']:.4f} "
              f"mae={report['valid']['mae']:.4f} r={report['valid']['pearson']:.4f}", flush=True)
        if best is None or report["valid"]["mae"] < best[1]["valid"]["mae"]:
            best = (model, report, strategy)
    model, report, best_strategy = best
    torch.save(model.state_dict(), RESULTS / "robust_model.pt")

    print("== ablation ==", flush=True)
    ablation = []
    for name in MODEL_NAMES:
        if name == "robust_full":
            outcome = dict(report)
            outcome["reused"] = True
        else:
            _, outcome = train_model(name, cache, best_strategy, args.epochs, args.batch, args.lr, SEED,
                                     verbose=False)
            outcome["reused"] = False
        outcome.pop("history", None)
        ablation.append(outcome)
        print(f"  {name}: acc={outcome['valid']['accuracy']:.4f} f1={outcome['valid']['macro_f1']:.4f} "
              f"mae={outcome['valid']['mae']:.4f} r={outcome['valid']['pearson']:.4f}", flush=True)

    print("== missing-rate sweep ==", flush=True)
    ratios = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    rate_all = sweep_rate(model, cache, None, ratios, args.repeats, SEED)
    rate_single = {modality: sweep_rate(model, cache, modality, ratios, args.repeats, SEED)
                   for modality in MODALITIES}
    for row in rate_all:
        print(f"  all missing {row['missing_ratio']:.1f}: acc={row['accuracy']:.4f} "
              f"f1={row['macro_f1']:.4f} mae={row['mae']:.4f}", flush=True)

    print("== missing-position sweep ==", flush=True)
    lengths = [5, 10, 15, 20, 25]
    position_rows = []
    for modality in MODALITIES:
        for position in ("front", "middle", "back"):
            position_rows.extend(sweep_window(model, cache, modality, position, lengths))

    print("== response surface ==", flush=True)
    surfaces = {modality: response_surface(model, cache, modality) for modality in MODALITIES}

    print("== attachment 3 inference ==", flush=True)
    a3 = md.load_a3()
    stats = np.load(CACHE / "norm_stats.npz")
    norm = {m: {"mean": stats[f"{m}_mean"], "std": stats[f"{m}_std"]} for m in MODALITIES}

    report_all = {
        "config": vars(args),
        "seed": SEED,
        "best_strategy": best_strategy,
        "strategies": strategy_reports,
        "ablation": ablation,
        "missing_rate_all": rate_all,
        "missing_rate_single": rate_single,
        "missing_position": position_rows,
        "response_surface": surfaces,
    }
    report_path = RESULTS / "q2_report.json"
    report_path.write_text(json.dumps(report_all, ensure_ascii=False, indent=2), encoding="utf-8")

    a3_inputs = infer_a3(model, a3, norm)
    np.savez_compressed(RESULTS / "a3_predictions.npz", **a3_inputs["arrays"])
    import pandas as pd
    pd.DataFrame(a3_inputs["rows"]).to_csv(OUT / "附件3_预测结果.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(a3_inputs["explain_rows"]).to_csv(OUT / "附件3_缺失影响分析.csv", index=False,
                                                   encoding="utf-8-sig")

    report_all["a3_summary"] = a3_inputs["summary"]
    report_path.write_text(json.dumps(report_all, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "best_strategy": best_strategy,
                      "a3_samples": a3_inputs["summary"]["n_samples"]}, ensure_ascii=False, indent=2))
    return 0


def text_lookup(aligned: dict) -> dict:
    """用附件 2 全部划分建立 BERT 词元编号到连续文本表示的查表，供附件 3 的文本通道匹配。"""
    table = {}
    lengths = {}
    for split in md.SPLITS:
        tokens = np.asarray(aligned[f"{split}_text_bert"], dtype=np.int64)
        text = np.asarray(aligned[f"{split}_text"], dtype=np.float32)
        for index in range(tokens.shape[0]):
            key = tokens[index].tobytes()
            if key not in table:
                table[key] = text[index]
                lengths[key] = int((tokens[index][1] > 0).sum()) if tokens[index].shape[0] > 1 else 0
    return {"table": table, "lengths": lengths}


def match_text(entry: np.ndarray, lookup: dict) -> tuple[np.ndarray, bool, float]:
    """按词元编号精确匹配；未命中时只在注意力掩码长度最接近的候选内比较交并比。"""
    table = lookup["table"]
    lengths = lookup["lengths"]
    target = np.asarray(entry, dtype=np.int64)
    exact = table.get(target.tobytes())
    if exact is not None:
        return exact, True, 1.0
    target_mask = target[1] if target.shape[0] > 1 else target[0]
    target_len = int((target_mask > 0).sum())
    candidates = [key for key, value in lengths.items() if abs(value - target_len) <= 2]
    if not candidates:
        candidates = list(table)
    best_key = None
    best_score = -1.0
    for key in candidates:
        candidate = np.frombuffer(key, dtype=np.int64).reshape(target.shape)
        candidate_mask = candidate[1] if candidate.shape[0] > 1 else candidate[0]
        inter = int(np.logical_and(target_mask > 0, candidate_mask > 0).sum())
        union = int(np.logical_or(target_mask > 0, candidate_mask > 0).sum())
        score = inter / max(union, 1)
        if score > best_score:
            best_score = score
            best_key = key
    if best_key is None:
        return np.asarray(list(table.values())[0]), False, 0.0
    return table[best_key], False, float(best_score)


def infer_a3(model: nn.Module, a3: dict, norm: dict) -> dict:
    """附件 3 推理：文本通道按词元编号匹配，语音与视觉按秩映射到训练集分位分布后编码。"""
    aligned = md.load_aligned()
    lookup = text_lookup(aligned)
    reference = md.quantile_reference(aligned)
    n = a3["audio"].shape[0]
    text_proxy = np.zeros((n, md.SEQ_LEN, md.DIMS["text"]), dtype=np.float32)
    matched = 0
    similarities = []
    for row in range(n):
        value, exact, score = match_text(a3["text_bert"][row], lookup)
        text_proxy[row] = value
        matched += int(exact)
        similarities.append(score)
    text_encoded = encode_raw(text_proxy, "text")
    result = run_a3_batches(model, a3, norm, text_encoded, reference)
    result["summary"]["text_exact_match"] = matched
    result["summary"]["text_match_similarity_mean"] = float(np.mean(similarities))
    result["summary"]["text_match_similarity_min"] = float(np.min(similarities))
    result["summary"]["text_match_rule"] = (
        "按 3×50 词元编号在附件 2 训练/验证/测试全部样本中精确查表；未命中时仅在注意力掩码长度"
        "相差不超过 2 个位置的候选内按掩码交并比取最相似样本，并登记相似度"
    )
    result["summary"]["modality_mapping"] = (
        "文本通道取附件 2 匹配样本的连续文本表示；语音与视觉通道按秩映射到附件 2 训练集每个维度的"
        "分位分布后标准化，再经冻结编码器编码"
    )
    return result


ENCODERS: dict = {}


def encode_raw(array: np.ndarray, modality: str) -> np.ndarray:
    """把原始模态特征经冻结编码器编码为 192 维时序表示（按需加载编码器）。"""
    if modality not in ENCODERS:
        ENCODERS[modality] = load_encoder(modality, CACHE)
    return encode_sequence(ENCODERS[modality], array)


def run_a3_batches(model: nn.Module, a3: dict, norm: dict, text_encoded: np.ndarray,
                   reference: dict | None = None) -> dict:
    arrays, masks = [], []
    for modality in MODALITIES:
        if modality == "text":
            arrays.append(torch.from_numpy(text_encoded).float())
            masks.append(torch.ones(text_encoded.shape[0], text_encoded.shape[1]))
        else:
            if reference is not None:
                mapped = md.rank_map(a3[modality], modality, reference, norm)
            else:
                mapped = md.normalize(a3[modality], modality, norm)
            arrays.append(torch.from_numpy(encode_raw(mapped, modality)).float())
            masks.append(torch.from_numpy(md.valid_mask(a3[modality])).float())
    model.eval()
    predictions = []
    with torch.no_grad():
        for start in range(0, len(masks[0]), 32):
            stop = min(start + 32, len(masks[0]))
            seq = [item[start:stop] for item in arrays]
            msk = [item[start:stop] for item in masks]
            output = model(seq, msk)
            logits = torch.softmax(output["logits"], dim=1)
            predictions.append({
                "prob": logits.numpy(),
                "reg": output["regression"].numpy(),
                "mass": output["modality_mass"].numpy(),
            })
    prob = np.concatenate([item["prob"] for item in predictions])
    reg = np.concatenate([item["reg"] for item in predictions])
    mass = np.concatenate([item["mass"] for item in predictions])
    cls = prob.argmax(axis=1)
    label_names = np.asarray(["Negative", "Neutral", "Positive"])
    rows = []
    explain_rows = []
    for index in range(len(reg)):
        rows.append({
            "样本编号": a3["names"][index],
            "情感极性预测": label_names[cls[index]],
            "极性置信度": round(float(prob[index, cls[index]]), 4),
            "情感强度预测": round(float(reg[index]), 4),
            "文本作用程度": round(float(mass[index, 0]), 4),
            "语音作用程度": round(float(mass[index, 1]), 4),
            "视觉作用程度": round(float(mass[index, 2]), 4),
        })
        for modality_index, modality in enumerate(MODALITIES):
            if modality == "text":
                valid_len = int(masks[0][index].sum().item())
            else:
                valid_len = int(md.valid_mask(a3[modality][index:index + 1]).reshape(-1).sum())
            explain_rows.append({
                "样本编号": a3["names"][index],
                "模态类型": modality,
                "有效位置数": valid_len,
                "缺失位置数": int(md.SEQ_LEN - valid_len),
                "缺失比例": round(float(1.0 - valid_len / md.SEQ_LEN), 4),
                "该模态作用程度": round(float(mass[index, modality_index]), 4),
            })
    summary = {
        "n_samples": int(len(reg)),
        "polarity_counts": {name: int((cls == i).sum()) for i, name in enumerate(label_names)},
        "regression_mean": float(reg.mean()),
        "regression_std": float(reg.std()),
        "modality_mass_mean": mass.mean(axis=0).tolist(),
    }
    return {"rows": rows, "explain_rows": explain_rows, "summary": summary,
            "arrays": {"prob": prob, "reg": reg, "mass": mass, "names": a3["names"]}}


if __name__ == "__main__":
    raise SystemExit(main())
