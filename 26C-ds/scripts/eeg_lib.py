"""脑电数据读取、分段与质量评估的共享工具。

本模块只提供可复用的底层函数，不产生最终结果；结果写入由各阶段脚本负责。
所有阈值均为稳健统计量，避免个别高幅伪迹支配判断。
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True


import json
from pathlib import Path

import numpy as np
import scipy.io as sio
from scipy import signal, stats

FS = 256
EEG_CHANNELS = ("Fz", "F3", "F4")
EEG_INDEX = {"Fz": 0, "F3": 1, "F4": 2}
DECON_INDEX = {"Fz": 3, "F3": 4, "F4": 5}
ECG_INDEX = 6
CUE_INDEX = 7
ACT_INDEX = 8
TS_INDEX = 9

DATASETS = (
    {"key": "A1", "file": "VisualCogA_Task-1.mat", "group": "A", "task": 1, "task_cn": "项目一"},
    {"key": "A2", "file": "VisualCogA_Task-2.mat", "group": "A", "task": 2, "task_cn": "项目二"},
    {"key": "B1", "file": "VisualCogB_Task-1.mat", "group": "B", "task": 1, "task_cn": "项目一"},
    {"key": "B2", "file": "VisualCogB_Task-2.mat", "group": "B", "task": 2, "task_cn": "项目二"},
)

EPOCH_PRE = 0.2
EPOCH_POST = 1.0


def data_dir(project: Path) -> Path:
    return project / "data"


def raw_path(project: Path, filename: str) -> Path:
    return data_dir(project) / "raw" / filename


def load_record(project: Path, filename: str) -> dict:
    """读取一份原始记录，返回信号矩阵与元信息。"""
    path = raw_path(project, filename)
    mat = sio.loadmat(str(path))
    data = np.asarray(mat["data"], dtype=float)
    fs = int(np.asarray(mat["SampleRate"]).ravel()[0])
    labels = [str(v[0]) for v in np.asarray(mat["DataLabel"]).ravel()]
    return {"data": data, "fs": fs, "labels": labels, "path": path}


def event_onsets(marker: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """把稀疏事件标记通道解析为 (起始采样点, 标记值) 两个数组。"""
    idx = np.flatnonzero(marker != 0)
    if idx.size == 0:
        return np.empty(0, dtype=int), np.empty(0, dtype=float)
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    values = marker[starts]
    return starts.astype(int), values.astype(float)


def epoch_matrix(signal_1d: np.ndarray, onsets: np.ndarray, fs: int = FS,
                 pre: float = EPOCH_PRE, post: float = EPOCH_POST) -> np.ndarray:
    """按事件起始点切分单通道信号，返回 (试次数, 时间点) 矩阵。"""
    n_pre = int(round(pre * fs))
    n_post = int(round(post * fs))
    valid = onsets[(onsets - n_pre >= 0) & (onsets + n_post <= signal_1d.size)]
    out = np.empty((valid.size, n_pre + n_post), dtype=float)
    for i, onset in enumerate(valid):
        out[i] = signal_1d[onset - n_pre:onset + n_post]
    return out


def baseline_correct(epochs: np.ndarray, fs: int = FS, pre: float = EPOCH_PRE) -> np.ndarray:
    """以刺激前窗口的均值为基线做逐试次校正。"""
    n_base = int(round(pre * fs))
    return epochs - epochs[:, :n_base].mean(axis=1, keepdims=True)


def robust_scale(x: np.ndarray) -> float:
    """稳健尺度估计：1.4826 倍中位绝对偏差。"""
    med = np.median(x)
    return float(1.4826 * np.median(np.abs(x - med)))


def bandpass(x: np.ndarray, low: float, high: float, fs: int = FS, order: int = 4) -> np.ndarray:
    """零相位巴特沃斯带通滤波。"""
    nyq = fs / 2.0
    hi = min(high, nyq * 0.95)
    sos = signal.butter(order, [low / nyq, hi / nyq], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, x, axis=-1)


def r_peaks(ecg: np.ndarray, fs: int = FS) -> np.ndarray:
    """从心电通道提取 R 波峰位置。"""
    filtered = bandpass(ecg, 5.0, 15.0, fs=fs)
    scale = robust_scale(filtered)
    if scale <= 0:
        return np.empty(0, dtype=int)
    height = 3.0 * scale
    distance = int(0.25 * fs)
    peaks, _ = signal.find_peaks(filtered, height=height, distance=distance)
    return peaks.astype(int)


def rpca(matrix: np.ndarray, lam: float | None = None, max_iter: int = 300,
         tol: float = 1e-7) -> tuple[np.ndarray, np.ndarray, dict]:
    """稳健主成分分析：把观测矩阵分解为低秩分量与稀疏分量。

    求解 min ||L||_* + lam * ||S||_1  s.t.  M = L + S，采用非精确增广拉格朗日法。
    低秩分量承载跨试次一致的刺激相关响应，稀疏分量承载试次特异的伪迹。
    """
    m, n = matrix.shape
    if lam is None:
        lam = 1.0 / np.sqrt(max(m, n))
    norm_two = np.linalg.norm(matrix, 2)
    norm_inf = np.abs(matrix).max()
    dual_norm = max(norm_two, norm_inf / lam) if lam > 0 else norm_two
    if dual_norm <= 0:
        return matrix.copy(), np.zeros_like(matrix), {"iterations": 0, "converged": True, "rank": int(min(m, n))}

    y = matrix / dual_norm
    mu = 1.25 / (norm_two if norm_two > 0 else 1.0)
    mu_bar = mu * 1e7
    rho = 1.5
    l = np.zeros_like(matrix)
    s = np.zeros_like(matrix)
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        u, sv, vt = np.linalg.svd(matrix - s + y / mu, full_matrices=False)
        sv_thresh = np.maximum(sv - 1.0 / mu, 0.0)
        l = (u * sv_thresh) @ vt
        residual = matrix - l + y / mu
        s = np.sign(residual) * np.maximum(np.abs(residual) - lam / mu, 0.0)
        z = matrix - l - s
        y = y + mu * z
        err = np.linalg.norm(z, "fro") / (np.linalg.norm(matrix, "fro") + 1e-12)
        if err < tol:
            converged = True
            break
        mu = min(mu * rho, mu_bar)
    rank = int(np.sum(sv_thresh > 0)) if 'sv_thresh' in dir() else int(min(m, n))
    return l, s, {"iterations": it, "converged": converged, "rank": rank, "lambda": float(lam)}


def trial_artifact_flags(epochs: np.ndarray, z_threshold: float = 6.0) -> np.ndarray:
    """按逐试次稳健 z 分数标记幅值异常试次。"""
    scale = robust_scale(epochs.ravel())
    if scale <= 0:
        return np.zeros(epochs.shape[0], dtype=bool)
    peak = np.max(np.abs(epochs), axis=1)
    return peak > z_threshold * scale


def snr_db(signal_component: np.ndarray, noise_component: np.ndarray) -> float:
    """以分贝表示的成分信噪比。"""
    ps = float(np.var(signal_component))
    pn = float(np.var(noise_component))
    if pn <= 0:
        return float("inf")
    return float(10.0 * np.log10(ps / pn))


def bootstrap_ci(values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 20260923, statistic=np.mean) -> tuple[float, float, float]:
    """自助法置信区间，返回 (点估计, 下界, 上界)。"""
    rng = np.random.default_rng(seed)
    n = values.shape[0]
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    point = float(statistic(values))
    draws = rng.integers(0, n, size=(n_boot, n))
    samples = np.array([statistic(values[draws[i]]) for i in range(n_boot)])
    lo = float(np.quantile(samples, alpha / 2))
    hi = float(np.quantile(samples, 1 - alpha / 2))
    return point, lo, hi


def fdr_mask(pvals: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg 错误发现率控制，返回显著掩码。"""
    p = np.asarray(pvals, dtype=float)
    mask = np.zeros(p.shape, dtype=bool)
    finite = np.isfinite(p)
    if not finite.any():
        return mask
    pv = p[finite]
    order = np.argsort(pv)
    ranked = pv[order]
    m = ranked.size
    thresholds = alpha * (np.arange(1, m + 1) / m)
    below = ranked <= thresholds
    if not below.any():
        return mask
    k = np.max(np.flatnonzero(below))
    selected = order[: k + 1]
    idx = np.flatnonzero(finite)
    mask[idx[selected]] = True
    return mask


def pointwise_ttest(epochs: np.ndarray, n_base: int) -> np.ndarray:
    """对每个时间点做单样本 t 检验（相对刺激前基线），返回 p 值数组。"""
    n = epochs.shape[0]
    m = epochs.mean(axis=0)
    sd = epochs.std(axis=0, ddof=1)
    se = sd / np.sqrt(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        tvals = np.where(se > 0, m / se, 0.0)
    pvals = 2.0 * stats.t.sf(np.abs(tvals), df=n - 1)
    return np.asarray(pvals)


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def time_axis(fs: int = FS, pre: float = EPOCH_PRE, post: float = EPOCH_POST) -> np.ndarray:
    n = int(round(pre * fs)) + int(round(post * fs))
    return (np.arange(n) - int(round(pre * fs))) / fs
