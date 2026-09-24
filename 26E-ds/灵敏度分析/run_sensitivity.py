from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "Q2"))

import mm_data as md
from model import build_model
from run_q2 import tensors

OUT = PROJECT / "灵敏度分析"
CACHE = PROJECT / "Q2" / "cache"
RESULTS = PROJECT / "Q2" / "results"
DEVICE = torch.device("cpu")
SEED = 20260924
MODALITIES = md.MODALITIES
STEPS = md.SEQ_LEN

PARAMETERS = (
    ("文本缺失率", "text_ratio", 0.0, 0.7),
    ("语音缺失率", "audio_ratio", 0.0, 0.7),
    ("视觉缺失率", "vision_ratio", 0.0, 0.7),
    ("单区间最大长度", "max_segment", 1.0, 25.0),
    ("缺失区间数上限", "n_segments", 1.0, 5.0),
    ("可信度门控阈值", "gate_threshold", 0.05, 0.95),
)
PARAM_LOW = np.asarray([item[2] for item in PARAMETERS])
PARAM_HIGH = np.asarray([item[3] for item in PARAMETERS])
LOCAL_BASE = np.asarray([0.0, 0.0, 0.0, 13.0, 3.0, 0.5])
LOCAL_BASE_MISSING = np.asarray([0.35, 0.35, 0.35, 13.0, 3.0, 0.5])


def load_model(hidden: int = 192):
    model = build_model("robust_full", hidden)
    model.load_state_dict(torch.load(RESULTS / "robust_model.pt", map_location=DEVICE))
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


def build_segment_pool(batch: int, n_segments: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """预生成固定缺失区间池：所有评估共用同一池，保证只由参数差异引起输出差异。"""
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, STEPS, size=(batch, n_segments))
    lengths = rng.integers(1, STEPS + 1, size=(batch, n_segments))
    return starts, lengths


def corrupt_deterministic(sequences: list[torch.Tensor], masks: list[torch.Tensor],
                          params: np.ndarray, pool: tuple[np.ndarray, np.ndarray]
                          ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
    """按参数确定性地从固定区间池取用区间，避免评估之间引入额外随机性。"""
    seq = [item.clone() for item in sequences]
    msk = [item.clone() for item in masks]
    ratios = {"text": float(params[0]), "audio": float(params[1]), "vision": float(params[2])}
    max_segment = max(1, int(round(float(params[3]))))
    n_segments = max(1, int(round(float(params[4]))))
    starts, lengths = pool
    batch = seq[0].shape[0]
    for modality_index, modality in enumerate(MODALITIES):
        ratio = ratios[modality]
        if ratio <= 0:
            continue
        target = int(round(ratio * STEPS))
        for row in range(batch):
            remaining = target
            for segment in range(n_segments):
                if remaining <= 0:
                    break
                length = int(min(lengths[row, segment], max_segment, remaining))
                start = int(starts[row, segment])
                end = min(STEPS - 1, start + length - 1)
                seq[modality_index][row, start:end + 1] = 0.0
                msk[modality_index][row, start:end + 1] = 0.0
                remaining -= (end - start + 1)
    return seq, msk


def evaluate(model, base_sequences, base_masks, params, pool, labels_cls, labels_reg,
             batch: int = 256) -> dict:
    sequences, masks = corrupt_deterministic(base_sequences, base_masks, params, pool)
    logits, regression, confidence = [], [], []
    with torch.no_grad():
        for start in range(0, len(labels_cls), batch):
            stop = min(start + batch, len(labels_cls))
            output = model([item[start:stop] for item in sequences],
                           [item[start:stop] for item in masks])
            probability = torch.softmax(output["logits"], dim=1)
            logits.append(output["logits"].argmax(dim=1).numpy())
            regression.append(output["regression"].numpy())
            confidence.append(probability.max(dim=1).values.numpy())
    prediction = np.concatenate(logits)
    value = np.concatenate(regression)
    conf = np.concatenate(confidence)
    gate_threshold = float(params[5])
    penalty = (conf < gate_threshold).astype(np.float64)
    return {
        "accuracy": float((prediction == labels_cls).mean()),
        "macro_f1": float(md.metrics_classification(prediction, labels_cls)["macro_f1"]),
        "mae": float(np.abs(value - labels_reg).mean()),
        "robust_score": float((conf * (1.0 - 0.5 * penalty)).mean()),
    }


def sobol_indices(model, base_sequences, base_masks, labels_cls, labels_reg,
                  base_samples: int, seed: int) -> dict:
    """Saltelli 方案的随机抽样实现：一阶指数与总阶指数均用 Jansen 估计器。

    所有评估共用同一缺失区间池与同一组参数样本，保证方差分解只反映参数变化。"""
    rng = np.random.default_rng(seed)
    dim = len(PARAMETERS)
    pool = build_segment_pool(len(labels_cls), 5, seed + 991)
    sample_a = rng.random((base_samples, dim))
    sample_b = rng.random((base_samples, dim))
    scaled_a = PARAM_LOW + sample_a * (PARAM_HIGH - PARAM_LOW)
    scaled_b = PARAM_LOW + sample_b * (PARAM_HIGH - PARAM_LOW)
    keys = ("accuracy", "macro_f1", "mae", "robust_score")
    values_a = {key: [] for key in keys}
    values_b = {key: [] for key in keys}
    for index in range(base_samples):
        outcome_a = evaluate(model, base_sequences, base_masks, scaled_a[index], pool,
                             labels_cls, labels_reg)
        outcome_b = evaluate(model, base_sequences, base_masks, scaled_b[index], pool,
                             labels_cls, labels_reg)
        for key in keys:
            values_a[key].append(outcome_a[key])
            values_b[key].append(outcome_b[key])
    values_a = {key: np.asarray(value) for key, value in values_a.items()}
    values_b = {key: np.asarray(value) for key, value in values_b.items()}
    values_ab: dict[int, dict[str, np.ndarray]] = {}
    for d in range(dim):
        collected = {key: [] for key in keys}
        for index in range(base_samples):
            mixed = scaled_a[index].copy()
            mixed[d] = scaled_b[index][d]
            outcome = evaluate(model, base_sequences, base_masks, mixed, pool,
                               labels_cls, labels_reg)
            for key in keys:
                collected[key].append(outcome[key])
        values_ab[d] = {key: np.asarray(value) for key, value in collected.items()}

    indices: dict = {"parameters": [item[0] for item in PARAMETERS],
                     "keys": [item[1] for item in PARAMETERS],
                     "ranges": [[item[2], item[3]] for item in PARAMETERS],
                     "base_samples": base_samples,
                     "evaluations": int(base_samples * (2 + dim)),
                     "estimator": "Jansen (Saltelli 2010) 一阶与总阶估计器，随机抽样、共用缺失区间池"}
    for key in keys:
        y_a, y_b = values_a[key], values_b[key]
        variance = float(np.var(np.concatenate([y_a, y_b])))
        first, total = [], []
        for d in range(dim):
            y_ab = values_ab[d][key]
            numerator = float(np.mean(y_b * (y_ab - y_a)))
            first.append(numerator / variance if variance > 1e-12 else 0.0)
            total.append(1.0 - numerator / variance if variance > 1e-12 else 0.0)
        indices[key] = {
            "first_order": [float(item) for item in first],
            "total_order": [float(item) for item in total],
            "variance": variance,
            "mean": float(np.mean(np.concatenate([y_a, y_b]))),
            "std": float(np.sqrt(variance)),
        }
    return indices


def local_sensitivity(model, base_sequences, base_masks, labels_cls, labels_reg, seed: int) -> dict:
    """局部敏感度：无缺失基线与三模态均缺失 35% 基线下的参数端点效应。"""
    pool = build_segment_pool(len(labels_cls), 5, seed + 991)
    clean = evaluate(model, base_sequences, base_masks, LOCAL_BASE, pool, labels_cls, labels_reg)
    with_missing = evaluate(model, base_sequences, base_masks, LOCAL_BASE_MISSING, pool,
                            labels_cls, labels_reg)
    rows = []
    for index, (label, key, low, high) in enumerate(PARAMETERS):
        for bound, name in ((low, "下界"), (high, "上界")):
            for scenario, base_params, baseline in (
                ("无缺失基线", LOCAL_BASE, clean),
                ("三模态均缺失 35%", LOCAL_BASE_MISSING, with_missing),
            ):
                params = base_params.copy()
                params[index] = bound
                outcome = evaluate(model, base_sequences, base_masks, params, pool,
                                   labels_cls, labels_reg)
                rows.append({
                    "参数": label,
                    "取值": name,
                    "参数值": bound,
                    "场景": scenario,
                    "极性准确率": outcome["accuracy"],
                    "强度平均绝对误差": outcome["mae"],
                    "稳健得分": outcome["robust_score"],
                    "相对基线的强度误差变化": outcome["mae"] - baseline["mae"],
                    "相对基线的准确率变化": outcome["accuracy"] - baseline["accuracy"],
                })
    return {"clean_baseline": clean, "missing_baseline": with_missing, "rows": rows}


def joint_surface(model, base_sequences, base_masks, labels_cls, labels_reg, seed: int,
                  grid: int = 7) -> dict:
    pool = build_segment_pool(len(labels_cls), 5, seed + 991)
    text_ratios = np.linspace(0.0, 0.7, grid)
    audio_ratios = np.linspace(0.0, 0.7, grid)
    score = np.zeros((grid, grid), dtype=float)
    accuracy = np.zeros_like(score)
    for i, text_ratio in enumerate(text_ratios):
        for j, audio_ratio in enumerate(audio_ratios):
            params = np.asarray([text_ratio, audio_ratio, 0.0, 13.0, 3.0, 0.5])
            outcome = evaluate(model, base_sequences, base_masks, params, pool,
                               labels_cls, labels_reg)
            score[i, j] = outcome["robust_score"]
            accuracy[i, j] = outcome["accuracy"]
    return {"text_ratios": text_ratios.tolist(), "audio_ratios": audio_ratios.tolist(),
            "robust_score": score.tolist(), "accuracy": accuracy.tolist(), "grid": grid}


def main() -> int:
    parser = argparse.ArgumentParser(description="鲁棒模型的全局敏感度分析（Sobol 方差分解）")
    parser.add_argument("--base-samples", type=int, default=120)
    parser.add_argument("--split", type=str, default="valid")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    model = load_model()
    raw = np.load(CACHE / "encoded_sequences.npz", allow_pickle=True)
    cache = {key: raw[key] for key in raw.files}
    base_sequences, base_masks = tensors(cache, args.split)
    labels_cls = cache[f"{args.split}_label_cls"]
    labels_reg = cache[f"{args.split}_label_reg"]

    indices = sobol_indices(model, base_sequences, base_masks, labels_cls, labels_reg,
                            args.base_samples, SEED)
    (OUT / "sensitivity_indices.json").write_text(
        json.dumps(indices, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    local = local_sensitivity(model, base_sequences, base_masks, labels_cls, labels_reg, SEED)
    (OUT / "local_sensitivity.json").write_text(
        json.dumps(local, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    surface = joint_surface(model, base_sequences, base_masks, labels_cls, labels_reg, SEED)
    (OUT / "joint_surface.json").write_text(
        json.dumps(surface, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "evaluations": indices["evaluations"],
                      "clean_baseline": local["clean_baseline"],
                      "missing_baseline": local["missing_baseline"],
                      "surface_grid": surface["grid"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
