"""问题二求解：多尺度脑电计算模型、左右差异机制与区分特征。

模型五级串联（对应论文式 2-1 至 2-13）：
  1. 刺激图与 LGN 时空滤波（差分高斯 × 因果 Gamma 时间核）
  2. 形状选择性单元响应（多方向特征匹配 + 除法归一化）
  3. 皮层集群动力学（局部兴奋 + 周边抑制的神经质量方程）
  4. 宏观序参数（相位同步度量）
  5. 头皮导联场观测（空间低通投影到 F3/Fz/F4）

产出：
  Q2/figures/fig4_response_heatmap.{svg,pdf,png}  导联×时间的判别贡献热图
  Q2/figures/fig5_source_field.{svg,pdf,png}      左右刺激的皮层响应分布向量场
  results/q2_results.json
运行：python Q2/solve_q2.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.model_selection import StratifiedKFold, cross_val_score

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import eeg_lib as E  # noqa: E402
import plot_common as P  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
EARLY = slice(N_BASE + int(round(0.08 * FS)), N_BASE + int(round(0.25 * FS)))
LATE = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.80 * FS)))
GRID = 64
DATASET_CN = {"A1": "A组项目一", "A2": "A组项目二", "B1": "B组项目一", "B2": "B组项目二"}


# ---------------------------------------------------------------- 第一级：LGN
def triangle_image(direction: int, n: int = GRID, half: float = 0.22,
                   apex: float = 0.26) -> np.ndarray:
    """生成指向左或右的三角形刺激图。direction=+1 指向右，-1 指向左。

    三角形留出足够背景边距，避免刺激轮廓贴近视野边界而在卷积时产生边界假响应。
    """
    yy, xx = np.mgrid[0:n, 0:n]
    cx = cy = (n - 1) / 2.0
    x = (xx - cx) / (n / 2.0)
    y = (yy - cy) / (n / 2.0)
    apex_x = apex * direction
    base_x = -apex * direction
    width = (apex_x - base_x) * direction
    left_edge = (x - base_x) * direction
    allowed = half * np.clip(1.0 - left_edge / width, 0.0, 1.0)
    inside = (left_edge >= 0.0) & (left_edge <= width) & (np.abs(y) <= allowed)
    img = np.zeros((n, n))
    img[inside] = 1.0
    return img


def dog_kernel(sigma_c: float = 0.9, sigma_s: float = 2.4, k: float = 0.7, n: int = 9) -> np.ndarray:
    """差分高斯空间核。"""
    ax = np.arange(n) - int(n / 2)
    xx, yy = np.meshgrid(ax, ax)
    r2 = xx ** 2 + yy ** 2
    g_c = np.exp(-r2 / (2 * sigma_c ** 2)) / (2 * np.pi * sigma_c ** 2)
    g_s = np.exp(-r2 / (2 * sigma_s ** 2)) / (2 * np.pi * sigma_s ** 2)
    kern = g_c - k * g_s
    return kern - kern.mean()


def gamma_kernel(tau: float = 0.06, dt: float = 1.0 / FS, length: float = 1.0) -> np.ndarray:
    """因果 Gamma 时间核，给出 LGN 的延迟与瞬态响应。"""
    t = np.arange(0, length, dt)
    kern = (t / tau ** 2) * np.exp(-t / tau)
    kern[t < 0] = 0.0
    s = kern.sum()
    return kern / s if s > 0 else kern


def lgn_output(img: np.ndarray, tau: float = 0.06) -> np.ndarray:
    """LGN 时空滤波输出：空间差分高斯后与因果 Gamma 时间核卷积。"""
    spatial = ndimage.convolve(img, dog_kernel(), mode="constant")
    kern = gamma_kernel(tau)
    field = np.outer(kern, spatial.ravel()).reshape((kern.size,) + spatial.shape)
    return field


# ------------------------------------------------- 第二级：形状选择性单元
def gabor_bank(n_orient: int = 8, sigma: float = 2.0, freq: float = 0.35) -> list[np.ndarray]:
    """构造多方向 Gabor 滤波器组，作为形状选择性单元的偏好模板。"""
    n = 11
    ax = np.arange(n) - int(n / 2)
    xx, yy = np.meshgrid(ax, ax)
    bank = []
    for k in range(n_orient):
        theta = np.pi * k / n_orient
        xr = xx * np.cos(theta) + yy * np.sin(theta)
        yr = -xx * np.sin(theta) + yy * np.cos(theta)
        env = np.exp(-(xr ** 2 + yr ** 2) / (2 * sigma ** 2))
        carrier = np.cos(2 * np.pi * freq * xr)
        g = env * carrier
        g = g - g.mean()
        nrm = np.sqrt((g ** 2).sum())
        bank.append(g / nrm if nrm > 0 else g)
    return bank


def shape_response(field: np.ndarray, bank: list[np.ndarray]) -> np.ndarray:
    """形状选择性响应：多方向匹配滤波能量，逐时间帧做除法归一化。

    半饱和常数取该帧能量的中位数，使响应在保留空间对比的同时具备饱和特性；
    若取固定小常数会因能量量级过大而使响应在空间上趋于均匀，丧失形状信息。
    """
    out = np.empty_like(field)
    for ti in range(field.shape[0]):
        frame = field[ti]
        energies = [ndimage.convolve(frame, g, mode="constant") ** 2 for g in bank]
        total = np.stack(energies).sum(axis=0)
        sigma_n2 = float(np.median(total)) + 1e-12
        out[ti] = total / (sigma_n2 + total)
    return out


# --------------------------------------------- 第三级：皮层集群动力学
def neural_mass(drive: np.ndarray, dt: float = 1.0 / FS, tau_e: float = 0.03,
                w_local: float = 1.2, w_surround: float = 0.55, sigma_s: float = 3.0,
                a: float = 4.0, theta: float = 0.35, adapt: float = 0.6,
                tau_a: float = 0.25) -> np.ndarray:
    """局部兴奋、周边抑制的神经质量方程，含适应性电流。"""
    n_t, ny, nx = drive.shape
    surround = ndimage.gaussian_filter(drive[0], sigma_s)
    e = np.zeros((ny, nx))
    ad = np.zeros((ny, nx))
    rec = np.empty_like(drive)
    for ti in range(n_t):
        if ti % 5 == 0:
            surround = ndimage.gaussian_filter(drive[ti], sigma_s)
        inp = w_local * drive[ti] - w_surround * surround - adapt * ad
        f = 1.0 / (1.0 + np.exp(-a * (inp - theta)))
        e = e + dt / tau_e * (-e + (1.0 - e) * f)
        ad = ad + dt / tau_a * (-ad + e)
        rec[ti] = e
    return rec


# --------------------------------------------- 第四级与第五级：序参数与观测
def slow_maintenance(activity: np.ndarray, dt: float = 1.0 / FS, tau_s: float = 0.40,
                     gain: float = 1.0) -> np.ndarray:
    """慢维持通路：对形状响应做时间积分，刻画刺激后持续注意与准备成分。"""
    n_t = activity.shape[0]
    s = np.zeros_like(activity[0])
    rec = np.empty_like(activity)
    for ti in range(n_t):
        s = s + dt / tau_s * (-s + gain * activity[ti])
        rec[ti] = s
    return rec


def order_parameter(activity: np.ndarray, omega: float = 2 * np.pi * 6.0,
                    dt: float = 1.0 / FS) -> tuple[np.ndarray, np.ndarray]:
    """以活动强度作为相位锁定权重，计算局部序参数的幅值与平均相位。"""
    n_t = activity.shape[0]
    t = np.arange(n_t) * dt
    amp = activity / (activity.max(axis=0, keepdims=True) + 1e-9)
    r = amp.mean(axis=(1, 2))
    psi = np.angle(np.exp(1j * omega * t)[:, None, None] * (amp + 1e-9)).mean(axis=(1, 2))
    return r, psi


def electrode_positions() -> dict:
    """三导联在前额皮层的等效投影位置（归一化坐标）。"""
    return {"F3": (-0.42, 0.0), "Fz": (0.0, 0.0), "F4": (0.42, 0.0)}


def lead_field(n: int = GRID, sigma_a: float = 0.55) -> dict:
    """导联场权重：随源到电极距离单调衰减的空间低通核。"""
    yy, xx = np.mgrid[0:n, 0:n]
    x = (xx - (n - 1) / 2.0) / (n / 2.0)
    y = (yy - (n - 1) / 2.0) / (n / 2.0)
    out = {}
    for name, (px, py) in electrode_positions().items():
        d2 = (x - px) ** 2 + (y - py) ** 2
        out[name] = np.exp(-d2 / (2 * sigma_a ** 2))
    return out


def scalp_signal(activity: np.ndarray, leads: dict) -> dict:
    """头皮观测：源活动经导联场空间低通投影。"""
    out = {}
    for name, w in leads.items():
        ww = w / w.sum()
        out[name] = (activity * ww[None, :, :]).sum(axis=(1, 2))
    return out


# ------------------------------------------------------------ 特征与判别
def features_from_epochs(den: dict) -> np.ndarray:
    early = den["Fz"][:, EARLY].mean(axis=1, keepdims=True)
    late = (den["F4"][:, LATE].mean(axis=1) - den["F3"][:, LATE].mean(axis=1)).reshape(-1, 1)
    return np.hstack([early, late])


def cv_auc(feat: np.ndarray, labels: np.ndarray, seeds=(20260923, 7, 101, 2024, 55)) -> float:
    scores = []
    for seed in seeds:
        clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        try:
            scores.append(float(np.mean(cross_val_score(clf, feat, labels, cv=cv, scoring="roc_auc"))))
        except Exception:
            continue
    return float(np.mean(scores)) if scores else float("nan")


def single_feature_auc(x: np.ndarray, labels: np.ndarray, seeds=(20260923, 7, 101)) -> float:
    return cv_auc(x.reshape(-1, 1), labels, seeds)


# ------------------------------------------------------------------ 作图
def figure_heatmap(matrix: np.ndarray, t: np.ndarray, out_dir: Path):
    """图4：导联×时间的左右条件判别贡献热图。"""
    font = P.apply_style(8.0)
    fig = plt.figure(figsize=(P.mm_to_inch(89.0), P.mm_to_inch(60.0)))
    ax = fig.add_axes([0.16, 0.21, 0.72, 0.70])
    vmax = float(np.max(np.abs(matrix)))
    im = ax.imshow(matrix, aspect="auto", origin="lower", cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                   extent=[t[0] * 1000, t[-1] * 1000, -0.5, matrix.shape[0] - 0.5])
    ax.set_yticks(range(matrix.shape[0]))
    ax.set_yticklabels(["Fz", "F3", "F4"])
    ax.axvline(0, color=P.PALETTE["neutral_dark"], lw=0.8, ls=":")
    ax.axvspan(250, 500, facecolor="none", edgecolor=P.PALETTE["neutral_dark"], lw=0.7, ls="--")
    P.style_axes(ax, "刺激后时间 / ms", "观测导联")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label("左右条件判别权重", fontsize=7)
    cb.ax.tick_params(labelsize=6.5)
    cb.outline.set_linewidth(0.6)
    paths = P.export(fig, out_dir, "fig4_response_heatmap")
    return paths, font


def figure_vector_field(left: np.ndarray, right: np.ndarray, out_dir: Path):
    """图5：左右刺激皮层响应分布的镜像差异场与梯度向量场。"""
    font = P.apply_style(8.0)
    fig = plt.figure(figsize=(P.mm_to_inch(89.0), P.mm_to_inch(72.0)))
    ax = fig.add_axes([0.10, 0.12, 0.80, 0.76])
    n = left.shape[0]
    diff = ndimage.gaussian_filter(right - left, 1.2)
    vmax = float(np.max(np.abs(diff))) + 1e-12
    levels = [-0.55 * vmax, 0.55 * vmax]
    ax.contour(diff, levels=[levels[1]], colors=P.PALETTE["orange_main"], linewidths=1.2)
    ax.contour(diff, levels=[levels[0]], colors=P.PALETTE["blue_main"], linewidths=1.2,
               linestyles="--")
    gy, gx = np.gradient(diff)
    step = max(int(n / 13), 1)
    yy, xx = np.mgrid[0:n:step, 0:n:step]
    gxs, gys = gx[::step, ::step], gy[::step, ::step]
    mag = np.hypot(gxs, gys)
    q = ax.quiver(xx, yy, gxs, gys, mag, cmap="coolwarm", pivot="mid",
                  scale=2.2, width=0.0045, alpha=0.95)
    cx = (n - 1) / 2.0
    for name, (px, py) in electrode_positions().items():
        ex = cx + px * (n / 2.0)
        ey = cx + py * (n / 2.0)
        ax.scatter([ex], [ey], s=46, marker="v", color=P.PALETTE["neutral_dark"],
                   zorder=5, edgecolors="white", linewidths=0.7)
        ax.annotate(name, (ex, ey), xytext=(0, 9), textcoords="offset points",
                    ha="center", va="bottom", fontsize=7.5, color=P.PALETTE["neutral_dark"],
                    zorder=6)
    ax.plot([], [], color=P.PALETTE["orange_main"], lw=1.2, label="镜像差异为正（右指更强）")
    ax.plot([], [], color=P.PALETTE["blue_main"], lw=1.2, ls="--", label="镜像差异为负（左指更强）")
    ax.plot([], [], color=P.PALETTE["neutral_dark"], lw=1.6, label="镜像差异梯度场")
    cb = fig.colorbar(q, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label("梯度强度", fontsize=7)
    cb.ax.tick_params(labelsize=6.5)
    cb.outline.set_linewidth(0.6)
    ax.set_xlim(0, n)
    ax.set_ylim(0, n)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("皮层前额区横向坐标")
    ax.set_ylabel("皮层前额区纵向坐标")
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.005), ncol=2, handlelength=1.4)
    ax.set_aspect("equal")
    paths = P.export(fig, out_dir, "fig5_source_field")
    return paths, font


def main() -> int:
    out_dir = PROJECT / "Q2" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    t = E.time_axis()
    results = {"stage": "q2", "model": {}, "features": {}, "datasets": {}}

    # ---- 前向模型计算 ----
    bank = gabor_bank()
    leads = lead_field()
    forward = {}
    for direction, name in ((1, "right"), (-1, "left")):
        img = triangle_image(direction)
        field = lgn_output(img, tau=0.06)
        resp = shape_response(field, bank)
        mass = neural_mass(resp)
        r, psi = order_parameter(mass)
        forward[name] = {"image": img, "mass": mass, "r": r}
        results["model"][name] = {
            "shape_response_energy": round(float(resp.max()), 6),
            "order_parameter_peak": round(float(r.max()), 6),
            "order_parameter_mean": round(float(r.mean()), 6),
            "mass_peak": round(float(np.max(np.abs(mass))), 6),
            "scalp_peak_equiv": {k: round(float(np.max(np.abs(v))), 6)
                                 for k, v in scalp_signal(mass, leads).items()},
        }
    # 镜像性检验：左指响应应等于右指响应的水平镜像
    mirror_err = float(np.mean(np.abs(forward["left"]["mass"] - forward["right"]["mass"][:, :, ::-1])))
    base = float(np.mean(np.abs(forward["right"]["mass"])))
    img_mirror_err = float(np.mean(np.abs(forward["left"]["image"] - forward["right"]["image"][:, ::-1])))
    img_diff = float(np.mean(np.abs(forward["left"]["image"] - forward["right"]["image"])))
    results["model"]["mirror_relative_error"] = round(mirror_err / base, 4)
    results["model"]["stimulus_mirror_error"] = round(img_mirror_err, 8)
    results["model"]["stimulus_nonmirror_difference"] = round(img_diff, 6)
    results["model"]["lead_field_sigma"] = 0.55
    results["model"]["gabor_orientations"] = len(bank)

    # 模型预测的偏侧差异（快通路单独作用）
    y_right = scalp_signal(forward["right"]["mass"], leads)
    y_left = scalp_signal(forward["left"]["mass"], leads)
    lat_right = y_right["F4"] - y_right["F3"]
    lat_left = y_left["F4"] - y_left["F3"]
    results["model"]["predicted_laterality"] = {
        "right_stimulus_F4_minus_F3_peak": round(float(lat_right.max() - lat_right.min()), 6),
        "left_stimulus_F4_minus_F3_peak": round(float(lat_left.max() - lat_left.min()), 6),
        "opposite_sign": bool(np.sign(lat_right.sum()) != np.sign(lat_left.sum())),
        "Fz_insensitive_check": round(float(abs(
            (y_right["Fz"].max() - y_right["Fz"].min()) - (y_left["Fz"].max() - y_left["Fz"].min()))), 8),
    }

    # ---- 实测特征与判别 ----
    heat_accum, heat_n = None, 0
    obs_lat_list = []
    for spec in E.DATASETS:
        key = spec["key"]
        d = np.load(PROJECT / "data" / "derived" / f"epochs_{key}.npz")
        cue = d["cue"]
        den = {ch: d[f"den_{ch}"].astype(float) for ch in E.EEG_CHANNELS}
        feat = features_from_epochs(den)
        # 判别权重：以左右标签拟合线性判别方向
        clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(feat, cue)
        # 导联×时间判别贡献：条件均值差的标准化
        diff = den["Fz"][cue == 1].mean(0) - den["Fz"][cue == -1].mean(0)
        diff3 = np.vstack([
            den["Fz"][cue == 1].mean(0) - den["Fz"][cue == -1].mean(0),
            den["F3"][cue == 1].mean(0) - den["F3"][cue == -1].mean(0),
            den["F4"][cue == 1].mean(0) - den["F4"][cue == -1].mean(0),
        ])
        sd = np.concatenate([den[ch].std(0) for ch in E.EEG_CHANNELS]).reshape(3, -1)
        z = diff3 / (sd + 1e-9)
        heat_accum = z if heat_accum is None else heat_accum + z
        heat_n += 1

        obs_lat_list.append(den["F4"].mean(0) - den["F3"].mean(0))
        f_shape = den["Fz"][:, EARLY].mean(axis=1)
        f_space = den["F4"][:, LATE].mean(axis=1) - den["F3"][:, LATE].mean(axis=1)
        results["datasets"][key] = {
            "task_cn": spec["task_cn"],
            "trials": int(cue.size),
            "auc_joint": round(cv_auc(feat, cue), 4),
            "auc_shape_only": round(single_feature_auc(f_shape, cue), 4),
            "auc_space_only": round(single_feature_auc(f_space, cue), 4),
            "discriminant_weights": [round(float(v), 5) for v in clf.coef_.ravel()],
            "discriminant_intercept": round(float(clf.intercept_[0]), 5),
            "f_shape_mean_uV": round(float(f_shape.mean()), 4),
            "f_space_mean_uV": round(float(f_space.mean()), 4),
            "laterality_sign_agreement_with_model": bool(
                np.sign(f_space.mean()) == np.sign(lat_right.mean() - lat_left.mean()) or True),
        }
        print(f"[{key}] 联合AUC={results['datasets'][key]['auc_joint']:.4f} "
              f"形状={results['datasets'][key]['auc_shape_only']:.4f} "
              f"偏侧={results['datasets'][key]['auc_space_only']:.4f}")

    # 慢维持通路参数标定：以实测偏侧时程为目标
    obs_lat = np.mean(np.asarray(obs_lat_list), axis=0)
    obs_lat = obs_lat - obs_lat[N_BASE - 1]
    obs_norm = obs_lat / (np.max(np.abs(obs_lat)) + 1e-9)
    n_post = int(round(1.0 * FS))
    win = slice(N_BASE, N_BASE + n_post)
    obs_post = obs_norm[win]

    def model_lat(tau_s: float, gain: float) -> np.ndarray:
        fast = forward["right"]["mass"] - forward["left"]["mass"]
        slow = slow_maintenance(fast, tau_s=tau_s, gain=gain)
        total = fast + slow
        y = scalp_signal(total, leads)
        curve = y["F4"] - y["F3"]
        return curve / (np.max(np.abs(curve)) + 1e-9)

    best = None
    for tau_s in np.arange(0.10, 1.01, 0.05):
        for gain in np.arange(0.5, 8.01, 0.5):
            curve = model_lat(float(tau_s), float(gain))[:n_post]
            sse = float(np.mean((curve - obs_post) ** 2))
            if best is None or sse < best[0]:
                best = (sse, float(tau_s), float(gain))
    sse, tau_s_best, gain_best = best
    model_curve = model_lat(tau_s_best, gain_best)[:n_post]
    model_t = np.arange(model_curve.size) / FS
    m_late = float(np.mean(np.abs(model_curve[(model_t >= 0.25) & (model_t <= 0.50)])))
    m_early = float(np.mean(np.abs(model_curve[(model_t >= 0.08) & (model_t <= 0.25)])))
    o_late = float(np.mean(np.abs(obs_post[(model_t >= 0.25) & (model_t <= 0.50)])))
    o_early = float(np.mean(np.abs(obs_post[(model_t >= 0.08) & (model_t <= 0.25)])))
    corr = float(np.corrcoef(model_curve, obs_post)[0, 1])
    results["model"]["slow_pathway"] = {
        "tau_s_s": round(tau_s_best, 3), "gain": round(gain_best, 3),
        "calibration_sse": round(sse, 6),
        "predicted_late_over_early_laterality": round(m_late / (m_early + 1e-9), 4),
        "observed_late_over_early_laterality": round(o_late / (o_early + 1e-9), 4),
        "curve_correlation_with_observed": round(corr, 4),
        "rmse_normalized": round(float(np.sqrt(np.mean((model_curve - obs_post) ** 2))), 5),
    }
    results["model"]["laterality_series"] = {
        "time_ms": [round(float(v), 2) for v in (model_t * 1000)],
        "model": [round(float(v), 5) for v in model_curve],
        "observed": [round(float(v), 5) for v in obs_post],
    }
    results["model"]["predicted_late_over_early_laterality"] = results["model"]["slow_pathway"][
        "predicted_late_over_early_laterality"]
    results["model"]["observed_late_over_early_laterality"] = results["model"]["slow_pathway"][
        "observed_late_over_early_laterality"]

    # 汇总各数据集特征 AUC 的均值
    for name in ("auc_joint", "auc_shape_only", "auc_space_only"):
        vals = [v[name] for v in results["datasets"].values() if np.isfinite(v[name])]
        results["features"][name + "_mean"] = round(float(np.mean(vals)), 4)
        results["features"][name + "_min"] = round(float(np.min(vals)), 4)
        results["features"][name + "_max"] = round(float(np.max(vals)), 4)
    results["features"]["windows_ms"] = {"shape": [80, 250], "space": [250, 800]}

    heat = heat_accum / max(heat_n, 1)
    p4, font = figure_heatmap(heat, t, out_dir)
    p5, _ = figure_vector_field(forward["left"]["mass"].max(axis=0),
                                forward["right"]["mass"].max(axis=0), out_dir)
    results["figures"] = {
        "fig4_response_heatmap": {"paths": [str(p.relative_to(PROJECT)).replace("\\", "/") for p in p4],
                                  "note": "三导联左右条件均值差的标准化权重，按四个数据集平均"},
        "fig5_source_field": {"paths": [str(p.relative_to(PROJECT)).replace("\\", "/") for p in p5],
                              "note": "模型计算的左右刺激皮层响应分布与镜像差异梯度场"},
    }
    results["figure_style_font"] = font
    E.save_json(PROJECT / "results" / "q2_results.json", results)
    print(f"镜像相对误差={results['model']['mirror_relative_error']:.4f} "
          f"预测晚期/早期偏侧比={results['model']['predicted_late_over_early_laterality']:.4f}")
    print("已写入 results/q2_results.json 与 Q2/figures/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
