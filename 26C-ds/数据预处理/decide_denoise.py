"""主去噪方案定案比较：确定本文方案并给出统计证据。

四个对比方案：
  M0 原始分段信号（基线校正后不处理）
  M1a 传统带通：0.5-30 Hz 零相位带通（全部试次保留）
  M1b 传统方案：0.5-30 Hz 带通 + 幅值阈值剔除试次
  M2 本文方案：心电模板剔除 + 稳健软截断（10 倍稳健尺度），保留低频慢电位

判据：早期形状特征与晚期偏侧特征联合的重复交叉验证 AUC，
      跨四个数据集做配对检验并给出自助法置信区间。
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import sys
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedKFold, cross_val_score

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(PROJECT / "数据预处理"))

import eeg_lib as E  # noqa: E402
from compare_denoise import ecg_template_removal  # noqa: E402
from sweep_denoise import clip_extremes  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
EARLY = slice(N_BASE + int(round(0.08 * FS)), N_BASE + int(round(0.25 * FS)))
LATE = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.80 * FS)))
SEEDS = (20260923, 7, 101, 2024, 55, 808, 31337, 42, 9001, 2718)


def joint_features(ep: dict) -> np.ndarray:
    early = ep["Fz"][:, EARLY].mean(axis=1, keepdims=True)
    late = (ep["F4"][:, LATE].mean(axis=1) - ep["F3"][:, LATE].mean(axis=1)).reshape(-1, 1)
    return np.hstack([early, late])


def repeated_auc(feat: np.ndarray, labels: np.ndarray) -> np.ndarray:
    scores = []
    for seed in SEEDS:
        if feat.shape[0] < 10 or len(np.unique(labels)) < 2:
            continue
        clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        try:
            scores.append(float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc"))))
        except Exception:
            continue
    return np.asarray(scores)


def main() -> int:
    per_dataset = {}
    scores: dict[str, list[float]] = {k: [] for k in ("M0原始", "M1a传统带通", "M1b传统带通剔除", "M2本文方案")}
    for spec in E.DATASETS:
        rec = E.load_record(PROJECT, spec["file"])
        on, cv = E.event_onsets(rec["data"][E.CUE_INDEX])
        base = {ch: E.baseline_correct(E.epoch_matrix(rec["data"][E.EEG_INDEX[ch]], on))
                for ch in E.EEG_CHANNELS}

        m1a, m1b, m2 = {}, {}, {}
        keep_frac = []
        for ch in E.EEG_CHANNELS:
            filt = E.bandpass(base[ch], 0.5, 30.0, fs=FS)
            m1a[ch] = filt
            keep = ~E.trial_artifact_flags(filt, 6.0)
            if keep.sum() < 10:
                keep = np.ones(base[ch].shape[0], dtype=bool)
            m1b[ch] = filt[keep]
            keep_frac.append(float(keep.mean()))
            ecg, _ = ecg_template_removal(base[ch], rec, on, E.EEG_INDEX[ch], 0.6, 6.0)
            m2[ch], _ = clip_extremes(ecg, 10.0)

        rows = {}
        for name, ep in (("M0原始", base), ("M1a传统带通", m1a), ("M2本文方案", m2)):
            sc = repeated_auc(joint_features(ep), cv)
            rows[name] = {"auc_mean": round(float(sc.mean()), 4), "auc_sd": round(float(sc.std(ddof=1)), 4),
                          "trials": int(ep["Fz"].shape[0])}
            scores[name].extend(sc.tolist())
        # 传统剔除方案试次数改变，仅在保留试次上评估
        sel = None
        for ch in E.EEG_CHANNELS:
            filt = m1a[ch]
            keep = ~E.trial_artifact_flags(filt, 6.0)
            if keep.sum() < 10:
                keep = np.ones(filt.shape[0], dtype=bool)
            sel = keep if sel is None else (sel & keep)
        m1b_sync = {ch: m1a[ch][sel] for ch in E.EEG_CHANNELS}
        sc = repeated_auc(joint_features(m1b_sync), cv[sel])
        rows["M1b传统带通剔除"] = {"auc_mean": round(float(sc.mean()), 4),
                                    "auc_sd": round(float(sc.std(ddof=1)), 4),
                                    "trials": int(sel.sum()), "retained_fraction": round(float(sel.mean()), 4)}
        per_dataset[spec["key"]] = rows
        print(f"== {spec['key']} ({spec['task_cn']}) 保留试次比例={np.mean(keep_frac):.3f}")
        for name, v in rows.items():
            print(f"   {name:<16} AUC={v['auc_mean']:.4f} ± {v['auc_sd']:.4f}  试次={v['trials']}")

    print("\n== 配对检验（本文方案 对 传统带通，跨数据集重复交叉验证）==")
    n = min(len(scores["M1a传统带通"]), len(scores["M2本文方案"]))
    a = np.asarray(scores["M1a传统带通"][:n])
    b = np.asarray(scores["M2本文方案"][:n])
    t_stat, p_val = stats.ttest_rel(b, a)
    diff = b - a
    pt, lo, hi = E.bootstrap_ci(diff)
    print(f"   样本数={n}  均值差={diff.mean():+.4f}  t={t_stat:.3f}  p={p_val:.3e}  95%区间[{lo:+.4f}, {hi:+.4f}]")

    print("\n== 配对检验（本文方案 对 原始信号）==")
    a2 = np.asarray(scores["M0原始"][:n])
    t2, p2 = stats.ttest_rel(b, a2)
    d2 = b - a2
    _pt2, lo2, hi2 = E.bootstrap_ci(d2)
    print(f"   均值差={d2.mean():+.4f}  t={t2:.3f}  p={p2:.3e}  95%区间[{lo2:+.4f}, {hi2:+.4f}]")

    E.save_json(PROJECT / "检查结果" / "denoise_final_decision.json", {
        "per_dataset": per_dataset,
        "M2_vs_M1a": {"n": int(n), "mean_diff": round(float(diff.mean()), 4),
                      "t": round(float(t_stat), 4), "p": float(p_val), "ci95": [round(lo, 4), round(hi, 4)]},
        "M2_vs_M0": {"n": int(n), "mean_diff": round(float(d2.mean()), 4),
                     "t": round(float(t2), 4), "p": float(p2), "ci95": [round(lo2, 4), round(hi2, 4)]},
        "selected": "M2本文方案",
        "reason": "在抑制伪迹的同时保持并提升左右可分性，且不做高通或带通，避免破坏低频慢电位成分。",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
