"""慢漂移处理方案比较：确定既能去掉低频漂移、又不破坏视物特征的方案。

低频漂移在项目二数据中幅值可达数百微伏，设备自带滤波器把它连同任务响应一起去掉
（对照通道 FzDecon 在刺激后窗口均值不足 1 微伏）。本脚本比较不同漂移处理方式，
统一以“早期形状特征 + 晚期偏侧特征”的交叉验证 AUC 作为视物特征保留度的判据。

处理方式：
  D0 不处理
  D1 0.3 Hz 零相位高通
  D2 0.5 Hz 零相位高通
  D3 1.0 Hz 零相位高通
  D4 0.5-30 Hz 带通（传统方案）
  D5 稳健移动中位数去趋势（窗长 0.5 s）
每种方式后接同一套伪迹修复（大瞬变插值 + 参考引导小波稀疏收缩）。
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedKFold, cross_val_score

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "数据预处理"))

import eeg_lib as E  # noqa: E402
from compare_denoise import reference_guided_shrink, transient_suppression  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
EARLY = slice(N_BASE + int(round(0.08 * FS)), N_BASE + int(round(0.25 * FS)))
LATE = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.80 * FS)))


def detrend_median(epochs: np.ndarray, window_s: float = 0.5) -> np.ndarray:
    """稳健移动中位数去趋势：扣除以宽窗中位数估计的低频趋势。"""
    size = int(round(window_s * FS)) | 1
    trend = ndimage.median_filter(epochs, size=(1, size), mode="nearest")
    return epochs - trend


DRIFT_METHODS = {
    "D0不处理": lambda ep: ep,
    "D1高通0.3Hz": lambda ep: E.bandpass(ep, 0.3, 120.0),
    "D2高通0.5Hz": lambda ep: E.bandpass(ep, 0.5, 120.0),
    "D3高通1.0Hz": lambda ep: E.bandpass(ep, 1.0, 120.0),
    "D4带通0.5-30Hz": lambda ep: E.bandpass(ep, 0.5, 30.0),
    "D5中位数去趋势": detrend_median,
}


def joint_auc(ep: dict, labels: np.ndarray, n_splits: int = 5) -> float:
    """早期 Fz 形状特征与晚期 F4-F3 偏侧特征联合的交叉验证 AUC。"""
    early = ep["Fz"][:, EARLY].mean(axis=1, keepdims=True)
    late = (ep["F4"][:, LATE].mean(axis=1) - ep["F3"][:, LATE].mean(axis=1)).reshape(-1, 1)
    feat = np.hstack([early, late])
    if feat.shape[0] < n_splits * 2 or len(np.unique(labels)) < 2:
        return float("nan")
    clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=20260923)
    try:
        return float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc")))
    except Exception:
        return float("nan")


def single_auc(feat: np.ndarray, labels: np.ndarray, n_splits: int = 5) -> float:
    if feat.shape[0] < n_splits * 2 or len(np.unique(labels)) < 2:
        return float("nan")
    clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=20260923)
    try:
        return float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc")))
    except Exception:
        return float("nan")


def main() -> int:
    per_dataset = {}
    for spec in E.DATASETS:
        rec = E.load_record(PROJECT, spec["file"])
        on, cv = E.event_onsets(rec["data"][E.CUE_INDEX])
        base = {ch: E.baseline_correct(E.epoch_matrix(rec["data"][E.EEG_INDEX[ch]], on))
                for ch in E.EEG_CHANNELS}
        rows = {}
        for name, fn in DRIFT_METHODS.items():
            ep = {ch: fn(base[ch]) for ch in E.EEG_CHANNELS}
            raw_late = {ch: float(np.abs(ep[ch][:, LATE]).mean()) for ch in E.EEG_CHANNELS}
            repaired = {}
            for ch in E.EEG_CHANNELS:
                s1, _ = transient_suppression(ep[ch])
                s2, _ = reference_guided_shrink(s1)
                repaired[ch] = s2
            rows[name] = {
                "joint_auc": round(joint_auc(ep, cv), 4),
                "joint_auc_repaired": round(joint_auc(repaired, cv), 4),
                "early_fz_auc": round(single_auc(ep["Fz"][:, EARLY].mean(axis=1, keepdims=True), cv), 4),
                "late_lat_auc": round(single_auc(
                    (ep["F4"][:, LATE].mean(axis=1) - ep["F3"][:, LATE].mean(axis=1)).reshape(-1, 1), cv), 4),
                "late_abs_mean_uV": round(float(np.mean(list(raw_late.values()))), 3),
            }
        per_dataset[spec["key"]] = rows
        print(f"== {spec['key']} ({spec['task_cn']})")
        for name, v in rows.items():
            print(f"   {name:<18} 联合AUC={v['joint_auc']:.3f}(修复后{v['joint_auc_repaired']:.3f}) "
                  f"早期Fz={v['early_fz_auc']:.3f} 晚期偏侧={v['late_lat_auc']:.3f} 晚期幅度={v['late_abs_mean_uV']:8.2f} uV")

    print("\n== 跨数据集平均 ==")
    agg = {}
    for name in DRIFT_METHODS:
        keys = ["joint_auc", "joint_auc_repaired", "early_fz_auc", "late_lat_auc", "late_abs_mean_uV"]
        agg[name] = {k: round(float(np.mean([per_dataset[s][name][k] for s in per_dataset])), 4) for k in keys}
        print(f"   {name:<18} 联合AUC={agg[name]['joint_auc']:.3f}(修复后{agg[name]['joint_auc_repaired']:.3f}) "
              f"早期Fz={agg[name]['early_fz_auc']:.3f} 晚期偏侧={agg[name]['late_lat_auc']:.3f} "
              f"晚期幅度={agg[name]['late_abs_mean_uV']:8.2f} uV")
    E.save_json(PROJECT / "检查结果" / "drift_method_comparison.json",
                {"per_dataset": per_dataset, "aggregate": agg})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
