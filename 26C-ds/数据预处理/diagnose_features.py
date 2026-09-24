"""左右刺激判别特征诊断：确定哪些脑电特征真正承载左右信息。

在原始分段数据上比较多种特征构造方式的交叉验证 AUC，为问题二的特征表示提供实测依据。
所有特征均来自刺激后窗口，评估统一使用分层五折交叉验证与线性判别分析。
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import sys
from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import eeg_lib as E  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
WINDOWS = {
    "P1_80_150ms": (0.08, 0.15),
    "N2_150_250ms": (0.15, 0.25),
    "P300_250_500ms": (0.25, 0.50),
    "晚期_500_800ms": (0.50, 0.80),
    "全窗口_0_800ms": (0.0, 0.80),
}


def window_slice(low: float, high: float) -> slice:
    return slice(N_BASE + int(round(low * FS)), N_BASE + int(round(high * FS)))


def cv_auc(feat: np.ndarray, labels: np.ndarray, n_splits: int = 5) -> float:
    if len(np.unique(labels)) < 2 or feat.shape[0] < n_splits * 2:
        return float("nan")
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=20260923)
    try:
        return float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc")))
    except Exception:
        return float("nan")


def main() -> int:
    report = {}
    for spec in E.DATASETS:
        rec = E.load_record(PROJECT, spec["file"])
        cue_on, cue_val = E.event_onsets(rec["data"][E.CUE_INDEX])
        ep = {ch: E.baseline_correct(E.epoch_matrix(rec["data"][E.EEG_INDEX[ch]], cue_on))
              for ch in E.EEG_CHANNELS}
        rows = {}
        for wname, (lo, hi) in WINDOWS.items():
            sl = window_slice(lo, hi)
            single = {ch: ep[ch][:, sl].mean(axis=1, keepdims=True) for ch in E.EEG_CHANNELS}
            lat = (ep["F4"][:, sl].mean(axis=1) - ep["F3"][:, sl].mean(axis=1)).reshape(-1, 1)
            combo = np.hstack([single["Fz"], single["F3"], single["F4"], lat])
            rows[wname] = {
                "Fz幅值": round(cv_auc(single["Fz"], cue_val), 4),
                "F3幅值": round(cv_auc(single["F3"], cue_val), 4),
                "F4幅值": round(cv_auc(single["F4"], cue_val), 4),
                "F4减F3偏侧": round(cv_auc(lat, cue_val), 4),
                "三导联加偏侧": round(cv_auc(combo, cue_val), 4),
            }
        # 时域波形特征：对波形做时间点降采样后直接判别
        sl = window_slice(0.0, 0.8)
        wave = np.hstack([ep[ch][:, sl][:, ::8] for ch in E.EEG_CHANNELS])
        wave_lat = ep["F4"][:, sl][:, ::8] - ep["F3"][:, sl][:, ::8]
        rows["时域波形"] = {
            "Fz幅值": round(cv_auc(ep["Fz"][:, sl][:, ::8], cue_val), 4),
            "F3幅值": round(cv_auc(ep["F3"][:, sl][:, ::8], cue_val), 4),
            "F4幅值": round(cv_auc(ep["F4"][:, sl][:, ::8], cue_val), 4),
            "F4减F3偏侧": round(cv_auc(wave_lat, cue_val), 4),
            "三导联加偏侧": round(cv_auc(np.hstack([wave, wave_lat]), cue_val), 4),
        }
        report[spec["key"]] = rows
        print(f"== {spec['key']} ({spec['task_cn']}) 试次={cue_on.size} "
              f"左={int((cue_val == -1).sum())} 右={int((cue_val == 1).sum())}")
        for wname, vals in rows.items():
            txt = "  ".join(f"{k}={v:.3f}" for k, v in vals.items())
            print(f"   {wname:<16}{txt}")

    print("\n== 跨数据集平均 ==")
    for wname in list(WINDOWS) + ["时域波形"]:
        keys = list(next(iter(report.values()))[wname])
        avg = {k: float(np.mean([report[s][wname][k] for s in report])) for k in keys}
        txt = "  ".join(f"{k}={v:.3f}" for k, v in avg.items())
        print(f"   {wname:<16}{txt}")
    E.save_json(PROJECT / "检查结果" / "laterality_feature_diagnosis.json", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
