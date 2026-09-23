# -*- coding: utf-8 -*-
"""灵敏度分析：返航安全余量与需求规模对组批结果与能耗的联合影响。

以问题一的精确组批模型为评估器，在（返航安全余量 ρ，需求缩放系数 s）二维网格上
重算总架次数、总运输能耗与累计作业时间，得到响应面并识别不可行区域。

运行：python 灵敏度分析/sensitivity.py
输出：results/sensitivity_results.json、灵敏度分析/figures/fig_sens_surface.{png,pdf,svg}
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "Q1"))

import numpy as np  # noqa: E402

from common_d import RESULTS_DIR, build_scenario, write_json  # noqa: E402
from solve_q1 import (  # noqa: E402
    build_caps, classify, enumerate_patterns, max_safe_payload, solve_area,
)

FIGDIR = os.path.join(ROOT, "灵敏度分析", "figures")


def scale_counts(counts, s):
    """按缩放系数调整各类物品数量：至少保留 1 件以维持服务区的投送需求。"""
    return [max(1, int(round(c * s))) for c in counts]


def evaluate_grid(sc, areas, by_area, cats_by_area, counts_by_area,
                  rhos, scales):
    """在（ρ, s）网格上评估三指标与可行性。"""
    out = {"rho": [], "scale": [], "N": [], "E": [], "T": [], "feasible": []}
    for s in scales:
        sc_counts = {a: scale_counts(counts_by_area[a], s) for a in areas}
        for rho in rhos:
            payload = {g: {a: max_safe_payload(sc, t, a, rho=rho)
                           for a in areas} for g, t in sc.types.items()}
            # 可行性：每类物品都能被某机型单独承运
            feasible = True
            for a in areas:
                heaviest = max((c["mass"] for c, n in
                                zip(cats_by_area[a], sc_counts[a]) if n > 0),
                               default=0.0)
                if heaviest > 0 and not any(payload[g][a] + 1e-9 >= heaviest
                                            for g in sc.types):
                    feasible = False
                    break
            if not feasible:
                out["rho"].append(float(rho))
                out["scale"].append(float(s))
                out["N"].append(np.nan)
                out["E"].append(np.nan)
                out["T"].append(np.nan)
                out["feasible"].append(0)
                continue
            n_tot, e_tot, t_tot = 0, 0.0, 0.0
            for a in areas:
                caps = build_caps(sc, a, {g: payload[g][a] for g in sc.types})
                r = solve_area(cats_by_area[a], sc_counts[a], caps, ("N", "E", "T"))
                n_tot += r["N"]
                e_tot += r["E"]
                t_tot += r["T"]
            out["rho"].append(float(rho))
            out["scale"].append(float(s))
            out["N"].append(float(n_tot))
            out["E"].append(float(e_tot))
            out["T"].append(float(t_tot))
            out["feasible"].append(1)
    return out


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from plot_common import (PALETTE, apply_py_nature_style, run_py_nature_qa,
                             save_py_nature_figure)

    os.makedirs(FIGDIR, exist_ok=True)
    apply_py_nature_style(font_size=8.0, profile="competition_cn")

    sc = build_scenario()
    areas = [a["id"] for a in sc.areas]
    by_area = {}
    for b in sc.boxes:
        by_area.setdefault(b["area_id"], []).append(b)
    cats_by_area, counts_by_area = {}, {}
    for a in areas:
        cats_by_area[a], counts_by_area[a] = classify(by_area[a])

    rhos = [round(x, 3) for x in np.arange(0.10, 0.3601, 0.01)]
    scales = [round(x, 2) for x in np.arange(0.70, 1.451, 0.05)]
    print(f"网格规模：ρ {len(rhos)} 档 × 需求缩放 {len(scales)} 档 = {len(rhos)*len(scales)} 点")
    grid = evaluate_grid(sc, areas, by_area, cats_by_area, counts_by_area, rhos, scales)

    R = np.array(grid["rho"]).reshape(len(scales), len(rhos))
    S = np.array(grid["scale"]).reshape(len(scales), len(rhos))
    N = np.array(grid["N"]).reshape(len(scales), len(rhos))
    E = np.array(grid["E"]).reshape(len(scales), len(rhos))
    T = np.array(grid["T"]).reshape(len(scales), len(rhos))
    F = np.array(grid["feasible"]).reshape(len(scales), len(rhos))

    print("\n=== 响应面（总运输能耗 kWh） ===")
    print("缩放\\ρ  " + " ".join(f"{r:6.2f}" for r in rhos[::4]))
    for i, s in enumerate(scales):
        row = " ".join(f"{E[i, j]:6.2f}" if F[i, j] else "   -- " for j in range(0, len(rhos), 4))
        print(f"{s:5.2f}  {row}")

    n_infeas = int((F == 0).sum())
    print(f"\n不可行网格点 {n_infeas}/{F.size}（{100.0*n_infeas/F.size:.1f}%）")
    okN = N[F == 1]
    print(f"可行点总架次数范围 {np.nanmin(okN):.0f}~{np.nanmax(okN):.0f}，"
          f"能耗范围 {np.nanmin(E):.3f}~{np.nanmax(E):.3f} kWh")

    # 弹性：在 s=1 处对 ρ 的局部敏感度
    i1 = scales.index(1.0)
    dE = np.gradient(E[i1, :], rhos)
    dN = np.gradient(N[i1, :], rhos)
    print(f"\n需求缩放 s=1 时：∂E/∂ρ 范围 {np.nanmin(dE):.3f}~{np.nanmax(dE):.3f} kWh/单位，"
          f"∂N/∂ρ 范围 {np.nanmin(dN):.3f}~{np.nanmax(dN):.3f} 架次/单位")

    # ---------------- 图12：三维响应面 ----------------
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    import matplotlib.colors as mcolors
    fig = plt.figure(figsize=(6.6, 5.0))
    ax = fig.add_subplot(111, projection="3d")
    Em = np.where(F == 1, E, np.nan)
    # 离散色阶：控制 SVG 中的不同颜色数量，满足可编辑矢量图的颜色上限要求
    cmap = plt.get_cmap("viridis", 9)
    norm = mcolors.BoundaryNorm(np.linspace(np.nanmin(E), np.nanmax(E), 10), cmap.N)
    surf = ax.plot_surface(R, S, Em, cmap=cmap, norm=norm, linewidth=0.3,
                           edgecolor="#2B2B2B", alpha=0.96, antialiased=False,
                           rstride=2, cstride=2)
    cb = fig.colorbar(surf, ax=ax, pad=0.10, fraction=0.035, shrink=0.78,
                      ticks=np.linspace(np.nanmin(E), np.nanmax(E), 6))
    cb.set_label("总运输能耗（kWh）", fontsize=7.6)
    cb.ax.tick_params(labelsize=6.8)
    # 不可行区域以红色网格标出边界
    if n_infeas:
        first_bad = [np.nanmin(np.where(F[:, j] == 0, scales, np.nan))
                     if (F[:, j] == 0).any() else np.nan for j in range(len(rhos))]
        fb = np.array(first_bad, dtype=float)
        ok = ~np.isnan(fb)
        if ok.any():
            ax.plot(R[0, ok], fb[ok], np.nanmax(Em) * np.ones(ok.sum()),
                    color=PALETTE["red_strong"], linewidth=2.0, zorder=12,
                    label="不可行边界（其下需求规模不可投递）")
    ax.set_xlabel("返航安全余量 $\\rho$", fontsize=7.6, labelpad=2)
    ax.set_ylabel("需求缩放系数 $s$", fontsize=7.6, labelpad=2)
    ax.set_zlabel("总运输能耗（kWh）", fontsize=7.6, labelpad=2)
    ax.tick_params(labelsize=6.6, pad=1)
    ax.view_init(elev=24, azim=-128)
    ax.set_title("")
    if n_infeas:
        ax.legend(loc="upper left", fontsize=6.6, handletextpad=0.4, borderpad=0.3)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_sens_surface"),
                             dpi=320, profile="competition_cn")
    qa = run_py_nature_qa(os.path.join(FIGDIR, "fig_sens_surface"), profile="competition_cn")
    print("图12 QA:", qa.passed, {k: v for k, v in qa.checks.items() if v is False})

    write_json(os.path.join(RESULTS_DIR, "sensitivity_results.json"), {
        "网格": grid,
        "rhos": rhos, "scales": scales,
        "不可行点数": n_infeas, "网格总数": int(F.size),
        "可行点架次数范围": [float(np.nanmin(okN)), float(np.nanmax(okN))],
        "能耗范围_kWh": [float(np.nanmin(E)), float(np.nanmax(E))],
        "s=1时_dE_drho": [float(x) for x in dE],
        "s=1时_dN_drho": [float(x) for x in dN],
    })
    print("\n已写出 results/sensitivity_results.json 与灵敏度分析/figures/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())