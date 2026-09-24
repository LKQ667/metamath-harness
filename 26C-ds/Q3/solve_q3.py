"""问题三求解：双源认知宏观模型、参数辨识与脑电数据验证。

模型（对应论文式 3-1 至 3-8）：
  两路 Kuramoto 振子群分别代表 LGN—皮层视觉通路与海马体—前额记忆通路，
  记忆通路经延迟 τ_H 与增益 g_H 耦合到视觉通路；前额叶整合变量含符合项，
  最终经导联场投影到 F3/Fz/F4 三个观测点。

产出：
  Q3/figures/fig6_parameter_contour.{svg,pdf,png}   参数辨识误差曲面与敏感性等值线
  灵敏度分析/figures/fig6_parameter_contour.{svg,pdf,png}
  results/q3_results.json
运行：python Q3/solve_q3.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import eeg_lib as E  # noqa: E402
import plot_common as P  # noqa: E402

FS = E.FS
N_BASE = int(round(E.EPOCH_PRE * FS))
N_POST = int(round(1.0 * FS))
EARLY = slice(N_BASE + int(round(0.08 * FS)), N_BASE + int(round(0.25 * FS)))
LATE = slice(N_BASE + int(round(0.25 * FS)), N_BASE + int(round(0.80 * FS)))
DATASET_CN = {"A1": "A组项目一", "A2": "A组项目二", "B1": "B组项目一", "B2": "B组项目二"}
DT = 1.0 / FS
N_V, N_H = 120, 80


def gamma_drive(n: int, tau: float = 0.09, delay: float = 0.06) -> np.ndarray:
    """刺激驱动包络：延迟起振的因果 Gamma 曲线，峰值归一。"""
    t = np.arange(n) * DT
    t = np.maximum(t - delay, 0.0)
    env = (t / tau ** 2) * np.exp(-t / tau)
    m = env.max()
    return env / m if m > 0 else env


def simulate(params: dict, n: int = N_POST, seed: int = 20260923) -> dict:
    """模拟双源认知宏观模型，返回序参数、整合变量与头皮预测信号。"""
    rng = np.random.default_rng(seed)
    tau_h = float(params["tau_H"])
    g_h = float(params["g_H"])
    beta_v = float(params["beta_V"])
    beta_h = float(params["beta_H"])
    gamma = float(params["gamma"])
    tau_r = float(params["tau_R"])
    k_vv = float(params.get("K_VV", 3.0))
    k_hh = float(params.get("K_HH", 2.0))
    k_vh = float(params.get("K_VH", 1.5))
    k_hv = float(params.get("K_HV", 1.5))

    w_v = 2 * np.pi * 10.0 + rng.normal(0, 0.6, N_V)
    w_h = 2 * np.pi * 6.0 + rng.normal(0, 0.4, N_H)
    th_v = rng.uniform(-np.pi, np.pi, N_V)
    th_h = rng.uniform(-np.pi, np.pi, N_H)
    drive = gamma_drive(n)
    delay_steps = int(round(tau_h * FS))

    r_v_hist = np.empty(n)
    r_h_hist = np.empty(n)
    psi_v_hist = np.empty(n)
    psi_h_hist = np.empty(n)
    for i in range(n):
        z_v = np.exp(1j * th_v).mean()
        z_h = np.exp(1j * th_h).mean()
        r_v, psi_v = np.abs(z_v), np.angle(z_v)
        r_h, psi_h = np.abs(z_h), np.angle(z_h)
        r_v_hist[i], psi_v_hist[i] = r_v, psi_v
        r_h_hist[i], psi_h_hist[i] = r_h, psi_h

        j = max(i - delay_steps, 0)
        lag_v = np.exp(1j * th_v)  # 视觉通路相位（当前）
        z_v_lag = np.exp(1j * th_v).mean()
        z_h_lag = np.exp(1j * th_h).mean()
        # 记忆通路对视觉通路的延迟耦合：用历史序参数近似延迟效应
        r_h_delay = r_h_hist[j]
        psi_h_delay = psi_h_hist[j]

        th_v = th_v + DT * (
            w_v
            + k_vv * r_v * np.sin(psi_v - th_v)
            + k_hv * r_h_delay * np.sin(psi_h_delay - th_v)
            + drive[i] * 6.0 * np.sin(-th_v)
        )
        th_h = th_h + DT * (
            w_h
            + k_hh * r_h * np.sin(psi_h - th_h)
            + k_vh * r_v * np.sin(psi_v - th_h)
            + 0.35 * drive[i] * 4.0 * np.sin(-th_h)
        )

    # 前额叶认知整合（含符合项）
    R = np.zeros(n)
    for i in range(n):
        j = max(i - delay_steps, 0)
        rhs = (beta_v * r_v_hist[i] + beta_h * g_h * r_h_hist[j]
               + gamma * r_v_hist[i] * r_h_hist[j])
        R[i] = R[i - 1] + DT / tau_r * (-R[i - 1] + rhs) if i > 0 else 0.0

    # 记忆通路的慢包络：海马体对照过程比视觉响应更慢，形成可区分的晚期持续成分。
    # 若两路包络形状相同，增益 g_H 在形状拟合中不可辨识，因此显式引入慢化时间常数。
    tau_h_slow = float(params.get("tau_H_slow", 0.35))
    r_h_slow = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc = acc + DT / tau_h_slow * (-acc + r_h_hist[i])
        r_h_slow[i] = acc

    # 头皮观测：题面指出脑电图是对大量神经元同步现象序参数的一种观测，
    # 因此观测对象是序参数包络本身，而非序参数与瞬时相位的乘积。
    lead = {"F3": (-0.42, 0.0), "Fz": (0.0, 0.0), "F4": (0.42, 0.0)}
    y = {}
    for name, (px, _py) in lead.items():
        w_v = np.exp(-((px + 0.30) ** 2) / (2 * 0.55 ** 2))
        w_h = np.exp(-((px - 0.0) ** 2) / (2 * 0.75 ** 2))
        y[name] = w_v * r_v_hist + w_h * g_h * r_h_slow + R
    return {"r_V": r_v_hist, "r_H": r_h_hist, "r_H_slow": r_h_slow,
            "psi_V": psi_v_hist, "psi_H": psi_h_hist,
            "R": R, "y": y, "drive": drive}


def normalized(x: np.ndarray) -> np.ndarray:
    s = np.max(np.abs(x))
    return x / s if s > 0 else x


def weighted_sse(model_y: dict, obs: dict, weights: dict, mask: np.ndarray) -> float:
    """三导联加权残差平方和；预测与实测分别归一化到单位峰值后比较。"""
    total = 0.0
    for ch in ("Fz", "F3", "F4"):
        a = normalized(model_y[ch][:N_POST])[mask]
        b = normalized(obs[ch][mask])
        total += weights[ch] * float(np.mean((a - b) ** 2))
    return total


def figure_contour(tau_grid, gain_grid, sse, best, out_dir: Path):
    """图6：参数辨识误差曲面与敏感性等值线。"""
    font = P.apply_style(8.0)
    fig = plt.figure(figsize=(P.mm_to_inch(89.0), P.mm_to_inch(70.0)))
    ax = fig.add_axes([0.17, 0.20, 0.68, 0.68])
    lo, hi = float(sse.min()), float(np.quantile(sse, 0.97))
    levels = np.linspace(lo, hi, 7)
    cs = ax.contourf(tau_grid, gain_grid, sse, levels=levels, cmap="Blues_r", alpha=0.95,
                     extend="max")
    cl = ax.contour(tau_grid, gain_grid, sse, levels=levels[1:-1],
                    colors=P.PALETTE["neutral_dark"], linewidths=0.6, alpha=0.85)
    ax.clabel(cl, inline=True, fontsize=6, fmt="%.4f")
    ax.scatter([best[1]], [best[2]], s=70, marker="*", color=P.PALETTE["red_strong"],
               zorder=6, edgecolors="white", linewidths=0.8, label="辨识最优参数")
    ax.set_xlabel("记忆通路延迟 $\\tau_H$ / s")
    ax.set_ylabel("记忆通路增益 $g_H$")
    cb = fig.colorbar(cs, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label("加权残差平方和", fontsize=7)
    cb.ax.tick_params(labelsize=6.5)
    cb.outline.set_linewidth(0.6)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncol=2, handlelength=1.2)
    paths = P.export(fig, out_dir, "fig6_parameter_contour")
    return paths, font


def main() -> int:
    out_dir = PROJECT / "Q3" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"stage": "q3", "model": {}, "datasets": {}, "validation": {}}

    # ---- 实测目标：四份记录的导联平均响应 ----
    obs_all = {}
    for spec in E.DATASETS:
        d = np.load(PROJECT / "data" / "derived" / f"epochs_{spec['key']}.npz")
        obs_all[spec["key"]] = {ch: d[f"den_{ch}"].astype(float).mean(axis=0)[N_BASE:]
                                for ch in E.EEG_CHANNELS}
    obs_mean = {ch: np.mean([obs_all[k][ch] for k in obs_all], axis=0) for ch in E.EEG_CHANNELS}
    weights = {ch: 1.0 / (np.std(obs_mean[ch]) + 1e-9) for ch in E.EEG_CHANNELS}
    wsum = sum(weights.values())
    weights = {k: v / wsum for k, v in weights.items()}
    mask = np.ones(N_POST, dtype=bool)

    # ---- 参数辨识：两阶段网格搜索 ----
    base = {"beta_V": 1.0, "beta_H": 1.0, "gamma": 0.8}
    coarse_tau = np.arange(0.00, 0.41, 0.05)
    coarse_gain = np.arange(0.20, 6.01, 0.40)
    coarse_tr = np.arange(0.10, 1.01, 0.20)
    best = None
    for th in coarse_tau:
        for gh in coarse_gain:
            for tr in coarse_tr:
                p = dict(base, tau_H=float(th), g_H=float(gh), tau_R=float(tr))
                s = weighted_sse(simulate(p)["y"], obs_mean, weights, mask)
                if best is None or s < best[0]:
                    best = (s, float(th), float(gh), float(tr))
    for _round in range(2):
        span = (0.03, 0.12, 0.10) if _round == 0 else (0.012, 0.05, 0.04)
        steps = (5, 5, 5)
        for dth in np.linspace(-span[0], span[0], steps[0]):
            for dgh in np.linspace(-span[1], span[1], steps[1]):
                for dtr in np.linspace(-span[2], span[2], steps[2]):
                    th = max(best[1] + dth, 0.0)
                    gh = max(best[2] + dgh, 0.02)
                    tr = max(best[3] + dtr, 0.03)
                    p = dict(base, tau_H=float(th), g_H=float(gh), tau_R=float(tr))
                    s = weighted_sse(simulate(p)["y"], obs_mean, weights, mask)
                    if s < best[0]:
                        best = (s, float(th), float(gh), float(tr))
    sse_best, tau_best, gain_best, tr_best = best
    results["model"]["identified"] = {
        "tau_H_s": round(tau_best, 4), "g_H": round(gain_best, 4), "tau_R_s": round(tr_best, 4),
        "weighted_sse": round(sse_best, 6),
        "fixed_parameters": base,
        "oscillators": {"visual": N_V, "hippocampal": N_H},
    }

    # ---- 误差曲面（用于图6与敏感性分析）----
    tau_grid_v = np.arange(0.00, 0.41, 0.02)
    gain_grid_v = np.arange(0.20, 6.01, 0.125)
    TG, GG = np.meshgrid(tau_grid_v, gain_grid_v, indexing="ij")
    SSE = np.empty_like(TG)
    for i, th in enumerate(tau_grid_v):
        for j, gh in enumerate(gain_grid_v):
            p = dict(base, tau_H=float(th), g_H=float(gh), tau_R=float(tr_best))
            SSE[i, j] = weighted_sse(simulate(p)["y"], obs_mean, weights, mask)

    # 局部敏感度：在最优参数附近做单参数扰动
    sens = {}
    for name, base_val, delta in (("tau_H", tau_best, 0.04), ("g_H", gain_best, 0.20),
                                  ("beta_V", base["beta_V"], 0.25), ("beta_H", base["beta_H"], 0.25),
                                  ("gamma", base["gamma"], 0.25), ("tau_R", tr_best, 0.10)):
        p = dict(base, tau_H=tau_best, g_H=gain_best, tau_R=tr_best)
        p[name] = base_val + delta
        up = weighted_sse(simulate(p)["y"], obs_mean, weights, mask)
        p[name] = max(base_val - delta, 1e-6)
        dn = weighted_sse(simulate(p)["y"], obs_mean, weights, mask)
        sens[name] = {"sse_up": round(float(up), 6), "sse_down": round(float(dn), 6),
                      "sensitivity": round(float((up - dn) / (2 * delta)), 6)}
    results["validation"]["local_sensitivity"] = sens

    # ---- 逐数据集验证 ----
    best_params = dict(base, tau_H=tau_best, g_H=gain_best, tau_R=tr_best)
    sim_best = simulate(best_params)
    for key, obs in obs_all.items():
        row = {"task_cn": DATASET_CN[key]}
        cors, rmses = [], []
        for ch in ("Fz", "F3", "F4"):
            a = normalized(sim_best["y"][ch][:N_POST])
            b = normalized(obs[ch])
            cors.append(float(np.corrcoef(a, b)[0, 1]))
            rmses.append(float(np.sqrt(np.mean((a - b) ** 2))))
        row["correlation"] = {ch: round(c, 4) for ch, c in zip(("Fz", "F3", "F4"), cors)}
        row["rmse_normalized"] = {ch: round(v, 4) for ch, v in zip(("Fz", "F3", "F4"), rmses)}
        row["mean_correlation"] = round(float(np.mean(cors)), 4)
        row["phi_memory_sustain"] = round(float(gain_best * np.mean(sim_best["r_H_slow"])), 6)
        results["datasets"][key] = row
        print(f"[{key}] 平均相关={row['mean_correlation']:.4f} RMSE={np.mean(rmses):.4f}")

    # ---- 行为学分层验证 ----
    layers = {}
    for spec in E.DATASETS:
        d = np.load(PROJECT / "data" / "derived" / f"epochs_{spec['key']}.npz")
        cue = d["cue"]
        act = d["action"]
        agree = (cue < 0) == (act < 0)
        ep = d["den_Fz"].astype(float)
        for tag, sel in (("应答与提示一致", agree), ("应答与提示不一致", ~agree)):
            if sel.sum() < 5:
                continue
            layers.setdefault(tag, []).append(float(ep[sel][:, LATE].mean()))
    results["validation"]["behavioral_stratification"] = {
        tag: {"n_datasets": len(v), "late_mean_uV": round(float(np.mean(v)), 4)} for tag, v in layers.items()
    }
    # 一致性比例
    agree_rates = {}
    for spec in E.DATASETS:
        d = np.load(PROJECT / "data" / "derived" / f"epochs_{spec['key']}.npz")
        agree_rates[spec["key"]] = round(float(np.mean((d["cue"] < 0) == (d["action"] < 0))), 4)
    results["validation"]["cue_action_agreement"] = agree_rates
    results["validation"]["overall"] = {
        "mean_correlation": round(float(np.mean([v["mean_correlation"] for v in results["datasets"].values()])), 4),
        "max_correlation": round(float(np.max([v["mean_correlation"] for v in results["datasets"].values()])), 4),
        "min_correlation": round(float(np.min([v["mean_correlation"] for v in results["datasets"].values()])), 4),
    }

    # ---- 图6 ----
    p6, font = figure_contour(TG, GG, SSE, best, out_dir)
    sens_dir = PROJECT / "灵敏度分析" / "figures"
    sens_dir.mkdir(parents=True, exist_ok=True)
    for p in p6:
        shutil.copy2(p, sens_dir / p.name)
    results["figures"] = {
        "fig6_parameter_contour": {
            "paths": [str(p.relative_to(PROJECT)).replace("\\", "/") for p in p6],
            "sensitivity_copy": [str((sens_dir / p.name).relative_to(PROJECT)).replace("\\", "/") for p in p6],
            "note": "以四份记录平均响应为目标的加权残差平方和曲面，横轴为记忆通路延迟，纵轴为记忆通路增益",
        }
    }
    results["figure_style_font"] = font
    E.save_json(PROJECT / "results" / "q3_results.json", results)
    print(f"辨识结果 τ_H={tau_best:.3f} s  g_H={gain_best:.3f}  τ_R={tr_best:.3f} s  加权SSE={sse_best:.5f}")
    print("已写入 results/q3_results.json、Q3/figures/、灵敏度分析/figures/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
