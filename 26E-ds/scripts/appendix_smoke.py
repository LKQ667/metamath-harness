"""附录净化代码的等价性回归入口。

对每个附录文件执行一次确定性的轻量测试：导入模块并对纯函数或模型前向做合成输入计算，
把结果写成 JSON。原版与净化版在同一环境下分别运行，输出逐项比对，用于证明净化只改变
书写形式而不改变语义与数值结果。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
for item in ("scripts", "Q1", "Q2", "Q3", "数据预处理", "灵敏度分析"):
    sys.path.insert(0, str(PROJECT / item))

SEED = 20260924


def run_model() -> dict:
    import torch
    from model import MODEL_NAMES, build_model

    torch.manual_seed(SEED)
    seq = [torch.randn(4, 50, 192) for _ in range(3)]
    msk = [torch.ones(4, 50) for _ in range(3)]
    msk[1][:, 30:] = 0.0
    report = {}
    for name in MODEL_NAMES:
        model = build_model(name)
        out = model(seq, msk)
        report[name] = {
            "params": int(sum(p.numel() for p in model.parameters())),
            "logits_shape": list(out["logits"].shape),
            "regression_sum": round(float(out["regression"].sum().detach()), 6),
            "mass_sum": round(float(out["modality_mass"].sum().detach()), 6),
        }
    return report


def run_model_q3() -> dict:
    import torch
    from model_q3 import build_interpretable

    torch.manual_seed(SEED)
    seq = [torch.randn(4, 50, 192) for _ in range(3)]
    msk = [torch.ones(4, 50) for _ in range(3)]
    msk[2][:, :20] = 0.0
    model = build_interpretable()
    out = model(seq, msk)
    return {
        "params": int(sum(p.numel() for p in model.parameters())),
        "logits_shape": list(out["logits"].shape),
        "alpha_sum": round(float(out["modality_alpha"].sum().detach()), 6),
        "beta_sum": round(float(out["position_beta"].sum().detach()), 6),
        "contribution_sum": round(float(out["position_contribution"].sum().detach()), 6),
    }


def run_mm_data() -> dict:
    import mm_data as md

    rng = np.random.default_rng(SEED)
    array = rng.normal(size=(6, 8, 3))
    array[0, 4:] = 0.0
    mask = md.valid_mask(array)
    segments = md.sample_missing_segments(rng, 8, 0.5, max_segments=2)
    corrupted = md.apply_segments(array[0], segments)
    pred = np.asarray([0, 1, 2, 1, 0, 2])
    target = np.asarray([0, 1, 1, 1, 2, 2])
    return {
        "valid_mask_sum": int(mask.sum()),
        "segment_count": len(segments),
        "corrupted_zero_ratio": round(float((corrupted == 0).all(axis=1).mean()), 6),
        "classification": {key: round(value, 6)
                           for key, value in md.metrics_classification(pred, target).items()},
        "regression": {key: round(value, 6)
                       for key, value in md.metrics_regression(
                           np.asarray([0.1, 0.2, 0.3]), np.asarray([0.2, 0.2, 0.2])).items()},
    }


def run_text_features() -> dict:
    from text_features import hash_index, text_features, tokens_of

    text = "This product is not good at all but the service was helpful"
    features = text_features(text)
    return {
        "token_count": len(tokens_of(text)),
        "hash_index_first": int(hash_index("this")),
        "features_shape": list(features.shape),
        "norm_sum": round(float(np.linalg.norm(features, axis=1).sum()), 6),
        "valid_positions": int((np.abs(features).sum(axis=1) > 0).sum()),
    }


def run_prepare_data() -> dict:
    import prepare_data as pd

    mask = np.asarray([True, True, False, False, False, True, True])
    segments = pd.mask_segments(mask)
    array = np.zeros((3, 5, 2))
    array[0, :2] = 1.0
    stats = pd.modality_stats("demo", array, "train")
    return {
        "segments": segments,
        "valid_ratio": round(float((array.sum(axis=2) > 0).mean()), 6),
        "zero_ratio": round(stats["zero_ratio"], 6),
        "n_dims": stats["n_dims"],
        "shape": stats["shape"],
    }


def run_extract_features() -> dict:
    import extract_features as ef

    bounds = ef.grid_bounds(10.0)
    features, valid = ef.text_features("hello world this is a short test sentence")
    return {
        "bounds_shape": list(bounds.shape),
        "bounds_last_edge": round(float(bounds[-1, 1]), 6),
        "grid_monotonic": bool(np.all(np.diff(bounds[:, 0]) > 0)),
        "text_shape": list(features.shape),
        "text_valid": int(valid.sum()),
        "text_norm_first": round(float(np.linalg.norm(features[0])), 6),
    }


def run_run_sensitivity() -> dict:
    import run_sensitivity as rs

    pool = rs.build_segment_pool(5, 3, SEED)
    params = np.asarray([0.4, 0.2, 0.0, 10.0, 2.0, 0.5])
    seq = [np.ones((5, 10, 4), dtype=np.float32) for _ in range(3)]
    msk = [np.ones((5, 10), dtype=np.float32) for _ in range(3)]
    import torch

    t_seq = [torch.from_numpy(item) for item in seq]
    t_msk = [torch.from_numpy(item) for item in msk]
    out_seq, out_msk = rs.corrupt_deterministic(t_seq, t_msk, params, pool)
    return {
        "pool_shapes": [list(item.shape) for item in pool],
        "text_zero_ratio": round(float((out_seq[0].numpy() == 0).mean()), 6),
        "audio_zero_ratio": round(float((out_seq[1].numpy() == 0).mean()), 6),
        "vision_untouched": bool(np.all(out_seq[2].numpy() == 1.0)),
        "mask_consistent": bool(np.all(out_msk[0].numpy() >= 0.0)),
        "param_low": [float(item) for item in rs.PARAM_LOW],
        "param_high": [float(item) for item in rs.PARAM_HIGH],
    }


def run_train_q3() -> dict:
    import torch
    from train_q3 import class_weights

    labels = np.asarray([0, 0, 1, 2, 2, 2])
    weights = class_weights(labels)
    import model_q3

    model = model_q3.build_interpretable(hidden=64)
    seq = [torch.randn(3, 12, 64) for _ in range(3)]
    msk = [torch.ones(3, 12) for _ in range(3)]
    out = model(seq, msk)
    return {
        "class_weights": [round(float(item), 6) for item in weights.numpy()],
        "logits_shape": list(out["logits"].shape),
        "beta_row_sum": round(float(out["position_beta"][0].sum().detach()), 6),
        "params": int(sum(p.numel() for p in model.parameters())),
    }


def run_run_q3() -> dict:
    import run_q3 as rq

    mask = np.asarray([True, True, False, False, True])
    return {
        "segments": rq.segments_of(mask),
        "constants": {"seq_len": int(rq.SEQ_LEN)},
        "modalities": list(rq.MODALITIES),
    }


RUNNERS = {
    "model": run_model,
    "model_q3": run_model_q3,
    "mm_data": run_mm_data,
    "text_features": run_text_features,
    "prepare_data": run_prepare_data,
    "extract_features": run_extract_features,
    "run_sensitivity": run_run_sensitivity,
    "train_q3": run_train_q3,
    "run_q3": run_run_q3,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="附录净化代码等价性回归")
    parser.add_argument("--module", required=True, choices=sorted(RUNNERS))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = RUNNERS[args.module]()
    target = Path(args.out)
    if not target.is_absolute():
        target = PROJECT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                      encoding="utf-8")
    print(json.dumps({"ok": True, "module": args.module, "keys": sorted(report)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
