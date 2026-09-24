"""去噪强度扫描：寻找既能抑制伪迹又不破坏视物特征的处理强度。

由定案比较可知，左右可分信息主要落在低频持续成分上，因此去噪必须窄目标化。
本脚本扫描不同强度的伪迹处理，同时报告伪迹抑制率与可分性 AUC，用于确定最终方案。
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import sys
from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedKFold, cross_val_score

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "数据预处理"))

import eeg_lib as E  # noqa: E402
from compare_denoise import ecg_template_removal, transient_suppression  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
EARLY = slice(N_BASE + int(round(0.08 * FS)), N_BASE + int(round(0.25 * FS)))
LATE = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.80 * FS)))
SEEDS = (20260923, 7, 101, 2024, 55, 808, 31337, 42, 9001, 2718)


def joint_features(ep: dict) -> np.ndarray:
    early = ep["Fz"][:, EARLY].mean(axis=1, keepdims=True)
    late = (ep["F4"][:, LATE].mean(axis=1) - ep["F3"][:, LATE].mean(axis=1)).reshape(-1, 1)
    return np.hstack([early, late])


def repeated_auc(feat: np.ndarray, labels: np.ndarray) -> float:
    scores = []
    for seed in SEEDS:
        clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        try:
            scores.append(float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc"))))
        except Exception:
            continue
    return float(np.mean(scores))


def clip_extremes(epochs: np.ndarray, z: float) -> tuple[np.ndarray, int]:
    """对超出稳健尺度的极端采样点做软截断，保留其余全部波形。"""
    scale = E.robust_scale(epochs.ravel())
    if scale <= 0:
        return epochs.copy(), 0
    limit = z * scale
    n = int(np.count_nonzero(np.abs(epochs) > limit))
    return np.clip(epochs, -limit, limit), n


def main() -> int:
    configs = {
        "C0原始": lambda ep, rec, on, ch: ep,
        "C1仅心电剔除": lambda ep, rec, on, ch: ecg_template_removal(ep, rec, on, E.EEG_INDEX[ch], 0.6, 6.0)[0],
        "C2心电+瞬变20倍": lambda ep, rec, on, ch: transient_suppression(
            ecg_template_removal(ep, rec, on, E.EEG_INDEX[ch], 0.6, 6.0)[0], 20.0)[0],
        "C3心电+瞬变12倍": lambda ep, rec, on, ch: transient_suppression(
            ecg_template_removal(ep, rec, on, E.EEG_INDEX[ch], 0.6, 6.0)[0], 12.0)[0],
        "C4心电+瞬变8倍": lambda ep, rec, on, ch: transient_suppression(
            ecg_template_removal(ep, rec, on, E.EEG_INDEX[ch], 0.6, 6.0)[0], 8.0)[0],
        "C5心电+截断20倍": lambda ep, rec, on, ch: clip_extremes(
            ecg_template_removal(ep, rec, on, E.EEG_INDEX[ch], 0.6, 6.0)[0], 20.0)[0],
        "C6心电+截断10倍": lambda ep, rec, on, ch: clip_extremes(
            ecg_template_removal(ep, rec, on, E.EEG_INDEX[ch], 0.6, 6.0)[0], 10.0)[0],
    }
    agg = {k: {"auc": [], "supp": [], "rel": []} for k in configs}
    per_dataset = {}
    for spec in E.DATASETS:
        rec = E.load_record(PROJECT, spec["file"])
        on, cv = E.event_onsets(rec["data"][E.CUE_INDEX])
        base = {ch: E.baseline_correct(E.epoch_matrix(rec["data"][E.EEG_INDEX[ch]], on))
                for ch in E.EEG_CHANNELS}
        rows = {}
        for name, fn in configs.items():
            ep = {ch: fn(base[ch], rec, on, ch) for ch in E.EEG_CHANNELS}
            auc = repeated_auc(joint_features(ep), cv)
            supp = float(np.mean([(np.percentile(np.max(np.abs(base[ch]), 1), 99)
                                   - np.percentile(np.max(np.abs(ep[ch]), 1), 99))
                                  / np.percentile(np.max(np.abs(base[ch]), 1), 99) for ch in E.EEG_CHANNELS]))
            rel = float(np.mean([float(np.corrcoef(ep[ch][0::2].mean(0)[N_BASE:],
                                                   ep[ch][1::2].mean(0)[N_BASE:])[0, 1]) for ch in E.EEG_CHANNELS]))
            rows[name] = {"auc": round(auc, 4), "artifact_suppression": round(supp, 4), "reliability": round(rel, 4)}
            agg[name]["auc"].append(auc)
            agg[name]["supp"].append(supp)
            agg[name]["rel"].append(rel)
        per_dataset[spec["key"]] = rows

    print(f"{'方案':<20}{'可分性AUC':>12}{'伪迹抑制率':>12}{'分半信度':>12}")
    summary = {}
    for name in configs:
        summary[name] = {
            "auc_mean": round(float(np.mean(agg[name]["auc"])), 4),
            "auc_min": round(float(np.min(agg[name]["auc"])), 4),
            "artifact_suppression_mean": round(float(np.mean(agg[name]["supp"])), 4),
            "reliability_mean": round(float(np.mean(agg[name]["rel"])), 4),
        }
        s = summary[name]
        print(f"{name:<20}{s['auc_mean']:>12.4f}{s['artifact_suppression_mean']:>12.4f}{s['reliability_mean']:>12.4f}")
    E.save_json(PROJECT / "检查结果" / "denoise_strength_sweep.json",
                {"per_dataset": per_dataset, "summary": summary})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
