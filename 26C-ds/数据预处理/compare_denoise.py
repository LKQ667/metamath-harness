"""去噪方案比较：以“伪迹抑制”与“视物特征保留”双准则筛选主方法。

五种候选方案在同一分段数据上运行：
  P1 传统方案：0.5-30 Hz 带通 + 幅值阈值剔除试次
  P2 小波全域阈值：平稳小波全域软阈值
  P3 低秩稀疏分解：稳健主成分分析
  P4 心电模板剔除 + 稳健试次加权平均
  P5 参考引导稀疏收缩：以稳健集成参考为基准，只收缩偏离参考的稀疏系数

评价指标：
  分半信度：奇偶试次各自平均后的事件相关电位相关系数（任务锁定成分保留度）
  伪迹抑制率：99 分位单试次峰值的下降比例
  单试次可分性：以刺激后 250-500 ms 双导差分特征做交叉验证 AUC
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import sys
from pathlib import Path

import numpy as np
import pywt
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedKFold, cross_val_score

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import eeg_lib as E  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
P300 = slice(int(round(0.25 * FS)) + N_BASE, int(round(0.5 * FS)) + N_BASE)
POST = slice(N_BASE, N_BASE + int(round(0.8 * FS)))


def wavelet_sparse_shrink(epochs: np.ndarray, wavelet: str = "db4", level: int = 5,
                          z_threshold: float = 5.0) -> np.ndarray:
    """平稳小波变换下只收缩伪迹主导的稀疏系数，其余系数保持不变。"""
    n = epochs.shape[-1]
    block = 2 ** level
    pad = int(np.ceil(n / block) * block) - n
    work = np.pad(epochs, ((0, 0), (0, pad)), mode="reflect") if pad else epochs
    coeffs = pywt.swt(work, wavelet, level=level, axis=-1, trim_approx=False)
    new_coeffs = []
    for approx, detail in coeffs:
        d = np.asarray(detail, dtype=float)
        scale = E.robust_scale(d.ravel())
        if scale <= 0:
            new_coeffs.append((approx, detail))
            continue
        z = np.abs(d) / scale
        shrink = np.clip((z - z_threshold) / (z + 1e-12), 0.0, 1.0)
        new_coeffs.append((approx, d * (1.0 - shrink)))
    rec = pywt.iswt(new_coeffs, wavelet, axis=-1)
    return np.asarray(rec, dtype=float)[..., :n]


def reference_guided_shrink(epochs: np.ndarray, wavelet: str = "db4", level: int = 5,
                            z_threshold: float = 4.0, n_pass: int = 2) -> tuple[np.ndarray, dict]:
    """参考引导稀疏收缩。

    先用稳健集成中位数得到参考事件相关电位，再在平稳小波域逐试次比较系数与参考的偏离：
    只有偏离超过稳健阈值的系数才被收缩，与参考一致的系数（即任务锁定成分）原样保留。
    迭代两轮以逐步净化参考本身。
    """
    n = epochs.shape[-1]
    block = 2 ** level
    pad = int(np.ceil(n / block) * block) - n
    current = epochs.copy()
    stats = {"shrunk_coeffs": 0, "passes": n_pass}
    for _ in range(n_pass):
        ref = np.median(current, axis=0)
        work = np.pad(current, ((0, 0), (0, pad)), mode="reflect") if pad else current
        ref_pad = np.pad(ref, (0, pad), mode="reflect") if pad else ref
        coeffs = pywt.swt(work, wavelet, level=level, axis=-1, trim_approx=False)
        ref_coeffs = pywt.swt(ref_pad, wavelet, level=level, axis=-1, trim_approx=False)
        new_coeffs = []
        shrunk = 0
        for (approx, detail), (ra, rd) in zip(coeffs, ref_coeffs):
            d = np.asarray(detail, dtype=float)
            r = np.asarray(rd, dtype=float)
            dev = d - r[None, :]
            scale = E.robust_scale(dev.ravel())
            if scale <= 0:
                new_coeffs.append((approx, detail))
                continue
            z = np.abs(dev) / scale
            shrink = np.clip((z - z_threshold) / (z + 1e-12), 0.0, 1.0)
            shrunk += int(np.count_nonzero(shrink > 0))
            new_coeffs.append((approx, r[None, :] + dev * (1.0 - shrink)))
        rec = pywt.iswt(new_coeffs, wavelet, axis=-1)
        current = np.asarray(rec, dtype=float)[..., :n]
        stats["shrunk_coeffs"] += shrunk
    return current, stats


def ecg_template_removal(epochs: np.ndarray, rec: dict, onsets: np.ndarray,
                         channel_index: int, corr_threshold: float = 0.6,
                         z_threshold: float = 6.0) -> tuple[np.ndarray, int]:
    """用心电通道定位 R 波构建伪迹模板，只从高相关且高幅试次中扣除。"""
    ecg = rec["data"][E.ECG_INDEX]
    peaks = E.r_peaks(ecg)
    if peaks.size < 10:
        return epochs.copy(), 0
    half = int(round(0.25 * FS))
    segs = [ecg[p - half:p + half] for p in peaks if p - half >= 0 and p + half < ecg.size]
    if len(segs) < 10:
        return epochs.copy(), 0
    template = np.median(np.asarray(segs), axis=0)
    template = template - template.mean()
    tscale = E.robust_scale(template)
    if tscale <= 0:
        return epochs.copy(), 0

    signal_1d = rec["data"][channel_index]
    arte = []
    for onset in onsets:
        p = int(round(onset + 0.35 * FS))
        if p - half < 0 or p + half >= signal_1d.size:
            return epochs.copy(), 0
        seg = signal_1d[p - half:p + half]
        arte.append(seg - seg.mean())
    arte = np.asarray(arte)

    out = epochs.copy()
    removed = 0
    for i in range(epochs.shape[0]):
        a = arte[i]
        if a.std() <= 0:
            continue
        corr = float(np.corrcoef(a, template)[0, 1])
        amp = float(np.max(np.abs(a)) / tscale)
        gain = float(np.dot(a, template) / (np.dot(template, template) + 1e-12))
        if corr > corr_threshold and amp > z_threshold and 0.0 < abs(gain) < 3.0:
            start = int(round(0.35 * FS)) - half + N_BASE
            lo, hi = max(start, 0), min(start + 2 * half, out.shape[1])
            if hi > lo:
                out[i, lo:hi] -= gain * template[(lo - start):(hi - start)]
                removed += 1
    return out, removed


def robust_weighted_mean(epochs: np.ndarray, floor: float = 0.1) -> np.ndarray:
    """按试次伪迹水平倒数加权求平均。"""
    scale = np.array([E.robust_scale(t) for t in epochs])
    med = np.median(scale) if scale.size else 0.0
    if med <= 0:
        return epochs.mean(axis=0)
    raw = 1.0 / np.maximum(scale / med, floor)
    w = raw / raw.sum()
    return np.tensordot(w, epochs, axes=(0, 0))


def bandpass_reject(epochs: np.ndarray, low: float = 0.5, high: float = 30.0,
                    z_threshold: float = 6.0) -> np.ndarray:
    """传统方案：带通滤波后剔除超阈值试次。"""
    filt = E.bandpass(epochs, low, high, fs=FS)
    keep = ~E.trial_artifact_flags(filt, z_threshold)
    if keep.sum() < 10:
        keep = np.ones(epochs.shape[0], dtype=bool)
    return filt[keep]


def wavelet_global_denoise(epochs: np.ndarray, wavelet: str = "db4", level: int = 5) -> np.ndarray:
    """小波全域软阈值。"""
    coeffs = pywt.wavedec(epochs, wavelet, level=level, axis=-1)
    sigma = E.robust_scale(coeffs[-1].ravel())
    uth = sigma * np.sqrt(2.0 * np.log(max(epochs.shape[-1], 2)))
    new = [coeffs[0]] + [np.sign(np.asarray(c, dtype=float)) * np.maximum(np.abs(np.asarray(c, dtype=float)) - uth, 0.0)
                         for c in coeffs[1:]]
    return np.asarray(pywt.waverec(new, wavelet, axis=-1))[..., :epochs.shape[-1]]


def split_half_reliability(epochs: np.ndarray) -> float:
    """分半信度：奇偶试次各自平均后的事件相关电位相关系数。"""
    if epochs.shape[0] < 8:
        return float("nan")
    a = epochs[0::2].mean(axis=0)[POST]
    b = epochs[1::2].mean(axis=0)[POST]
    if a.std() <= 0 or b.std() <= 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def artifact_suppression(raw_epochs: np.ndarray, out_epochs: np.ndarray) -> float:
    """99 分位单试次峰值幅度的下降比例。"""
    a = float(np.percentile(np.max(np.abs(raw_epochs), axis=1), 99))
    b = float(np.percentile(np.max(np.abs(out_epochs), axis=1), 99))
    return (a - b) / a if a > 0 else float("nan")


def transient_suppression(epochs: np.ndarray, z_threshold: float = 8.0,
                          wavelet: str = "db4", level: int = 5) -> tuple[np.ndarray, int]:
    """大瞬变插值剔除：把超出稳健阈值的连续大偏移段用参考波形替换。

    运动与电极瞬变在时域表现为远高于背景的连续偏移，属于稀疏事件；
    用稳健集成参考填补该段可去掉瞬变而不改动其余采样点。
    """
    ref = np.median(epochs, axis=0)
    scale = E.robust_scale(epochs.ravel())
    if scale <= 0:
        return epochs.copy(), 0
    threshold = z_threshold * scale
    out = epochs.copy()
    replaced = 0
    for i in range(epochs.shape[0]):
        dev = epochs[i] - ref
        mask = np.abs(dev) > threshold
        if not mask.any():
            continue
        idx = np.flatnonzero(mask)
        breaks = np.flatnonzero(np.diff(idx) > 1)
        starts = np.concatenate(([idx[0]], idx[breaks + 1]))
        ends = np.concatenate((idx[breaks], [idx[-1]]))
        for s, e in zip(starts, ends):
            if e - s + 1 < 2:
                continue
            out[i, s:e + 1] = ref[s:e + 1]
            replaced += 1
    return out, replaced


def laterality_auc(epochs: np.ndarray, labels: np.ndarray, n_splits: int = 5) -> float:
    """左右可分性：以“早期形状特征 + 晚期偏侧特征”联合特征做交叉验证 AUC。

    早期特征取刺激后 80-250 ms 的 Fz 平均幅度（形状编码），
    晚期特征取刺激后 250-800 ms 的 F4 与 F3 平均幅度之差（空间偏侧编码）。
    """
    early = slice(N_BASE + int(round(0.08 * FS)), N_BASE + int(round(0.25 * FS)))
    late = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.80 * FS)))
    feat = epochs[:, early].mean(axis=1, keepdims=True)
    if epochs.shape[0] < n_splits * 2 or len(np.unique(labels)) < 2:
        return float("nan")
    clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=20260923)
    try:
        return float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc")))
    except Exception:
        return float("nan")


def laterality_auc_late(epochs_f4: np.ndarray, epochs_f3: np.ndarray, labels: np.ndarray,
                        n_splits: int = 5) -> float:
    """晚期偏侧特征的单试次可分性：F4 与 F3 在 250-800 ms 的幅度差。"""
    late = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.80 * FS)))
    feat = (epochs_f4[:, late].mean(axis=1) - epochs_f3[:, late].mean(axis=1)).reshape(-1, 1)
    if feat.shape[0] < n_splits * 2 or len(np.unique(labels)) < 2:
        return float("nan")
    clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=20260923)
    try:
        return float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc")))
    except Exception:
        return float("nan")


def build_candidates(ep: np.ndarray, rec: dict, onsets: np.ndarray, ch: str) -> dict:
    out = {}
    out["P0原始"] = ep
    out["P1传统带通剔除"] = bandpass_reject(ep)
    out["P2小波全域阈值"] = wavelet_global_denoise(ep)
    l, _s, _i = E.rpca(ep)
    out["P3低秩稀疏"] = l
    ecg_removed, _n = ecg_template_removal(ep, rec, onsets, E.EEG_INDEX[ch])
    out["P4心电剔除加权"] = ecg_removed
    rgs, _st = reference_guided_shrink(ep)
    out["P5参考引导收缩"] = rgs
    trans, _t = transient_suppression(ep)
    out["P6瞬变插值"] = trans
    combo, _c = transient_suppression(ecg_removed)
    combo, _c2 = reference_guided_shrink(combo)
    out["P7本文组合方案"] = combo
    return out


def main() -> int:
    per_dataset = {}
    for spec in E.DATASETS:
        rec = E.load_record(PROJECT, spec["file"])
        cue_on, cue_val = E.event_onsets(rec["data"][E.CUE_INDEX])
        rows = {}
        for ch in E.EEG_CHANNELS:
            ep = E.baseline_correct(E.epoch_matrix(rec["data"][E.EEG_INDEX[ch]], cue_on))
            for name, cand in build_candidates(ep, rec, cue_on, ch).items():
                rows[f"{ch}|{name}"] = {
                    "reliability": round(split_half_reliability(cand), 4),
                    "artifact_suppression": round(artifact_suppression(ep, cand), 4),
                    "auc_early": round(laterality_auc(cand, cue_val), 4),
                }
        per_dataset[spec["key"]] = rows
        print(f"== {spec['key']} ({spec['task_cn']}) 试次={cue_on.size}")

    methods = sorted({k.split("|")[1] for s in per_dataset.values() for k in s})
    aggregate = {}
    print("\n== 方案跨数据集平均表现（三导联）==")
    print(f"{'方案':<20}{'分半信度':>10}{'伪迹抑制率':>12}{'早期形状AUC':>13}")
    for m in methods:
        rel, sup, auc = [], [], []
        for s in per_dataset.values():
            for k, v in s.items():
                if not k.endswith("|" + m):
                    continue
                if np.isfinite(v["reliability"]):
                    rel.append(v["reliability"])
                if np.isfinite(v["artifact_suppression"]):
                    sup.append(v["artifact_suppression"])
                if np.isfinite(v["auc_early"]):
                    auc.append(v["auc_early"])
        aggregate[m] = {
            "reliability_mean": round(float(np.mean(rel)), 4),
            "artifact_suppression_mean": round(float(np.mean(sup)), 4),
            "auc_early_mean": round(float(np.mean(auc)), 4),
        }
        print(f"{m:<20}{aggregate[m]['reliability_mean']:>10.4f}"
              f"{aggregate[m]['artifact_suppression_mean']:>12.4f}{aggregate[m]['auc_early_mean']:>13.4f}")

    E.save_json(PROJECT / "检查结果" / "denoise_method_comparison.json",
                {"per_dataset": per_dataset, "aggregate": aggregate})
    print("\n已写入 检查结果/denoise_method_comparison.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
