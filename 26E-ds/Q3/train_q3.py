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
sys.path.insert(0, str(PROJECT / "Q3"))

import mm_data as md
from model_q3 import build_interpretable

OUT = PROJECT / "Q3"
CACHE = PROJECT / "Q2" / "cache"
RESULTS = OUT / "results"
DEVICE = torch.device("cpu")
SEED = 20260924
MODALITIES = md.MODALITIES


def load_cache() -> dict:
    data = np.load(CACHE / "encoded_sequences.npz", allow_pickle=True)
    return {key: data[key] for key in data.files}


def tensors(cache: dict, split: str) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    sequences = [torch.from_numpy(cache[f"{split}_{m}_seq"]).float() for m in MODALITIES]
    masks = [torch.from_numpy(cache[f"{split}_{m}_mask"]).float() for m in MODALITIES]
    return sequences, masks


def class_weights(labels: np.ndarray) -> torch.Tensor:
    counts = np.bincount(labels, minlength=3).astype(np.float64)
    return torch.tensor(counts.sum() / (3.0 * np.maximum(counts, 1.0)), dtype=torch.float32)


def train(epochs: int, batch: int, lr: float, hidden: int, seed: int,
          drop_prob: float = 0.35, verbose: bool = True) -> tuple[nn.Module, dict]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    cache = load_cache()
    model = build_interpretable(hidden).to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr * 0.1)
    train_seq, train_mask = tensors(cache, "train")
    labels_cls = cache["train_label_cls"]
    labels_reg = cache["train_label_reg"]
    ce = nn.CrossEntropyLoss(weight=class_weights(labels_cls))
    huber = nn.SmoothL1Loss(beta=0.5)
    n_train = len(labels_cls)
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        order = rng.permutation(n_train)
        total = 0.0
        for start in range(0, n_train, batch):
            index = order[start:start + batch]
            seq = [item[index].clone() for item in train_seq]
            msk = [item[index].clone() for item in train_mask]
            for row in range(len(index)):
                if rng.random() > drop_prob:
                    continue
                chosen = [int(rng.integers(0, 3))] if rng.random() < 0.6 else list(rng.choice(3, 2, replace=False))
                for modality in chosen:
                    ratio = float(rng.uniform(0.05, 0.45))
                    for s, e in md.sample_missing_segments(rng, seq[modality].shape[1], ratio, max_segments=2):
                        seq[modality][row, s:e + 1] = 0.0
                        msk[modality][row, s:e + 1] = 0.0
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
            print(f"  q3 epoch {epoch} loss {history[-1]['loss']:.4f}", flush=True)
    return model, {"history": history}


def infer(model: nn.Module, sequences: list[torch.Tensor], masks: list[torch.Tensor],
          batch: int = 256) -> dict:
    model.eval()
    logits, reg, alpha, beta, contribution = [], [], [], [], []
    with torch.no_grad():
        for start in range(0, sequences[0].shape[0], batch):
            stop = min(start + batch, sequences[0].shape[0])
            output = model([item[start:stop] for item in sequences],
                           [item[start:stop] for item in masks])
            logits.append(output["logits"].numpy())
            reg.append(output["regression"].numpy())
            alpha.append(output["modality_alpha"].numpy())
            beta.append(output["position_beta"].numpy())
            contribution.append(output["position_contribution"].numpy())
    return {
        "logits": np.concatenate(logits),
        "regression": np.concatenate(reg),
        "alpha": np.concatenate(alpha),
        "beta": np.concatenate(beta),
        "contribution": np.concatenate(contribution),
    }


def deletion_test(model: nn.Module, cache: dict, top_k: int, split: str = "valid",
                  repeats: int = 8, seed: int = SEED) -> dict:
    """删除最重要位置与删除随机位置后的输出变化对比，量化证据定位的有效性。

    同时记录两条判据：分类置信度的下降量与回归预测值的偏移量。回归预测值对输入扰动的
    敏感度远高于已经饱和的分类置信度，因此在置信度接近 1 时以预测值偏移为主要判据。"""
    rng = np.random.default_rng(seed)
    sequences, masks = tensors(cache, split)
    base = infer(model, sequences, masks)
    base_prob = torch.softmax(torch.from_numpy(base["logits"]), dim=1).numpy()
    base_conf = base_prob[np.arange(len(base_prob)), base_prob.argmax(axis=1)]
    base_value = np.asarray(base["regression"], dtype=float)
    importance = base["contribution"].sum(axis=1)
    order = np.argsort(-importance, axis=1)

    def drop_response(indices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        seq = [item.clone() for item in sequences]
        msk = [item.clone() for item in masks]
        for row in range(seq[0].shape[0]):
            for position in indices[row]:
                for modality in range(3):
                    seq[modality][row, position] = 0.0
                    msk[modality][row, position] = 0.0
        outcome = infer(model, seq, msk)
        prob = torch.softmax(torch.from_numpy(outcome["logits"]), dim=1).numpy()
        return (prob[np.arange(len(prob)), prob.argmax(axis=1)],
                np.asarray(outcome["regression"], dtype=float))

    top_conf, top_value = drop_response(order[:, :top_k])
    steps = sequences[0].shape[1]
    random_conf, random_value = [], []
    for _ in range(repeats):
        random_idx = np.stack([rng.choice(steps, size=top_k, replace=False)
                               for _ in range(sequences[0].shape[0])])
        conf, value = drop_response(random_idx)
        random_conf.append(conf)
        random_value.append(value)
    random_conf = np.mean(random_conf, axis=0)
    random_value = np.mean(random_value, axis=0)
    return {
        "top_k": top_k,
        "confidence_base": float(base_conf.mean()),
        "confidence_drop_top": float((base_conf - top_conf).mean()),
        "confidence_drop_random": float((base_conf - random_conf).mean()),
        "confidence_gain": float(((base_conf - top_conf) - (base_conf - random_conf)).mean()),
        "value_shift_top": float(np.abs(top_value - base_value).mean()),
        "value_shift_random": float(np.abs(random_value - base_value).mean()),
        "value_gain": float((np.abs(top_value - base_value) - np.abs(random_value - base_value)).mean()),
        "repeats": repeats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="训练可解释性融合模型并完成验证集解释质量核对")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1.5e-3)
    parser.add_argument("--hidden", type=int, default=192)
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.time()
    model, report = train(args.epochs, args.batch, args.lr, args.hidden, SEED)
    torch.save(model.state_dict(), RESULTS / "interpretable_model.pt")

    cache = load_cache()
    valid_seq, valid_mask = tensors(cache, "valid")
    test_seq, test_mask = tensors(cache, "test")
    valid_out = infer(model, valid_seq, valid_mask)
    test_out = infer(model, test_seq, test_mask)

    valid_metrics = {
        **md.metrics_classification(valid_out["logits"].argmax(axis=1), cache["valid_label_cls"]),
        **md.metrics_regression(valid_out["regression"], cache["valid_label_reg"]),
    }
    test_metrics = {
        **md.metrics_classification(test_out["logits"].argmax(axis=1), cache["test_label_cls"]),
        **md.metrics_regression(test_out["regression"], cache["test_label_reg"]),
    }
    np.savez_compressed(
        RESULTS / "q3_valid_outputs.npz",
        alpha=valid_out["alpha"], beta=valid_out["beta"],
        contribution=valid_out["contribution"], regression=valid_out["regression"],
        logits=valid_out["logits"], labels_cls=cache["valid_label_cls"],
        labels_reg=cache["valid_label_reg"],
    )
    print(json.dumps({"ok": True, "stage": "trained", "valid": valid_metrics,
                      "test": test_metrics}, ensure_ascii=False, indent=2), flush=True)

    deletion = [deletion_test(model, cache, k) for k in (1, 3, 5, 10)]

    polarity_names = np.asarray(["Negative", "Neutral", "Positive"])
    pred = valid_out["logits"].argmax(axis=1)
    truth = cache["valid_label_cls"]
    per_class = {}
    for index, name in enumerate(polarity_names):
        mask = truth == index
        if mask.sum() == 0:
            continue
        per_class[name] = {
            "n": int(mask.sum()),
            "accuracy": float((pred[mask] == truth[mask]).mean()),
            "mean_alpha": valid_out["alpha"][mask].mean(axis=0).tolist(),
            "mean_reg_abs_error": float(np.abs(valid_out["regression"][mask] - cache["valid_label_reg"][mask]).mean()),
        }

    error_rows = []
    abs_error = np.abs(valid_out["regression"] - cache["valid_label_reg"])
    order = np.argsort(-abs_error)[:40]
    for index in order:
        error_rows.append({
            "样本序号": int(index),
            "真实情感强度": float(cache["valid_label_reg"][index]),
            "预测情感强度": float(valid_out["regression"][index]),
            "绝对误差": float(abs_error[index]),
            "真实极性": str(polarity_names[truth[index]]),
            "预测极性": str(polarity_names[pred[index]]),
            "文本作用程度": float(valid_out["alpha"][index, 0]),
            "语音作用程度": float(valid_out["alpha"][index, 1]),
            "视觉作用程度": float(valid_out["alpha"][index, 2]),
        })

    payload = {
        "config": vars(args),
        "seed": SEED,
        "history": report["history"],
        "valid": valid_metrics,
        "test": test_metrics,
        "deletion_test": deletion,
        "per_class": per_class,
        "top_errors": error_rows,
        "modality_alpha_mean": valid_out["alpha"].mean(axis=0).tolist(),
        "position_beta_mean": valid_out["beta"].mean(axis=0).tolist(),
        "seconds": round(time.time() - started, 1),
    }
    (RESULTS / "q3_training_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "valid": valid_metrics, "test": test_metrics,
                      "deletion": deletion}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
