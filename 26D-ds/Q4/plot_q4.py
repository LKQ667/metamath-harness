# -*- coding: utf-8 -*-
"""问题四图表：任务分区结构与组间资源配置对比。

单面板（panel_count=1），符合项目锁定的"禁用子图"策略。

运行：python Q4/plot_q4.py
输出：Q4/figures/fig_q4_partition.{png,pdf,svg}
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402

from common_d import RESULTS_DIR, build_scenario  # noqa: E402

FIGDIR = os.path.join(ROOT, "Q4", "figures")


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from plot_common import (PALETTE, apply_py_nature_style, run_py_nature_qa,
                             save_py_nature_figure)

    os.makedirs(FIGDIR, exist_ok=True)
    apply_py_nature_style(font_size=8.0, profile="competition_cn")

    sc = build_scenario()
    data = json.load(open(os.path.join(RESULTS_DIR, "q4_results.json"), encoding="utf-8"))
    two = data["分区结果"]["2组"]
    three = data["分区结果"]["3组"]
    groups = two["分区"]
    detail = two["组明细"]
    pos = {a["id"]: (a["lon"], a["lat"]) for a in sc.areas}

    fig, ax = plt.subplots(figsize=(6.8, 5.0))
    dem = sc.dem
    nrow, ncol = dem.elev.shape
    lon_axis = dem.origin[0] + dem.res[0] * np.arange(ncol)
    lat_axis = dem.origin[1] - dem.res[1] * np.arange(nrow)
    ax.contourf(*np.meshgrid(lon_axis, lat_axis), dem.elev, levels=16,
                cmap="Greys", alpha=0.26)

    # 问题三的同架次关系（必须同组）
    q3 = json.load(open(os.path.join(RESULTS_DIR, "q3_results.json"), encoding="utf-8"))
    drawn = set()
    for s in q3["运输架次"]:
        r = s["route"]
        for i in range(len(r) - 1):
            key = tuple(sorted((r[i], r[i + 1])))
            if key in drawn:
                continue
            drawn.add(key)
            (x1, y1), (x2, y2) = pos[r[i]], pos[r[i + 1]]
            ax.plot([x1, x2], [y1, y2], color=PALETTE["neutral_mid"],
                    linewidth=0.8, alpha=0.75, zorder=2)
    ax.plot([], [], color=PALETTE["neutral_mid"], linewidth=0.8,
            label="同架次必须同组关系")

    gcolors = [PALETTE["blue_main"], PALETTE["orange_main"], PALETTE["teal_main"]]
    for gi, g in enumerate(groups):
        for a in g:
            ax.scatter(*pos[a], s=58, marker="o", facecolor=gcolors[gi % 3],
                       edgecolor="white", linewidths=0.9, zorder=6,
                       label=f"任务组{gi + 1}（{len(g)} 个服务区）")
            ax.annotate(a, pos[a], textcoords="offset points", xytext=(6.5, 3.0),
                        fontsize=6.2, color="#1A1A1A", zorder=8)
    # 三分区归属用空心环标注，便于同时读出两种分区的差异
    g3map = {}
    for gi, g in enumerate(three["分区"]):
        for a in g:
            g3map[a] = gi
    for a, gi in g3map.items():
        ax.scatter(*pos[a], s=132, marker="o", facecolor="none",
                   edgecolor=gcolors[gi % 3], linewidths=1.5, zorder=5,
                   linestyle="--")
    ax.scatter([], [], s=132, marker="o", facecolor="none",
               edgecolor=PALETTE["neutral_dark"], linewidths=1.5, linestyle="--",
               label="空心环颜色=3 组分区归属")
    ax.scatter([sc.center["lon"]], [sc.center["lat"]], s=115, marker="*",
               facecolor=PALETTE["gold_main"], edgecolor="black", linewidths=0.8,
               zorder=9, label="调度中心 O01")

    a2 = two["合计"]
    a3 = three["合计"]
    txt = (
        "分区方式对比（组内独立执行）\n"
        f"2 组：运输无人机 {a2['运输无人机']} 架，共享电池 {a2['共享电池']} 组，"
        f"中继无人机 {a2['中继无人机']} 架，中继组件 {a2['中继能源组件']} 组\n"
        f"      架次 {a2['运输架次']}，完成时间 {a2['完成时间'] / 3600:.2f} h，"
        f"组间质量不均衡 {a2['质量不均衡']:.3f}\n"
        f"3 组：运输无人机 {a3['运输无人机']} 架，共享电池 {a3['共享电池']} 组，"
        f"中继无人机 {a3['中继无人机']} 架，中继组件 {a3['中继能源组件']} 组\n"
        f"      架次 {a3['运输架次']}，完成时间 {a3['完成时间'] / 3600:.2f} h，"
        f"组间质量不均衡 {a3['质量不均衡']:.3f}\n"
        f"资源缺口：2 组为 {sum(a2['缺口'].values())} 项，3 组为 {sum(a3['缺口'].values())} 项"
    )
    ax.text(0.015, 0.015, txt, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=6.6, color=PALETTE["black"], zorder=12,
            bbox=dict(boxstyle="round,pad=0.36", facecolor="white",
                      edgecolor=PALETTE["neutral_dark"], linewidth=0.8))
    ax.set_xlabel("经度（°）")
    ax.set_ylabel("纬度（°）")
    ax.tick_params(labelsize=7)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(float(min(a["lon"] for a in sc.areas)) - 0.018,
                float(max(a["lon"] for a in sc.areas)) + 0.018)
    ax.set_ylim(float(min(a["lat"] for a in sc.areas)) - 0.012,
                float(max(a["lat"] for a in sc.areas)) + 0.030)
    hs, ls = ax.get_legend_handles_labels()
    seen, hh, ll = set(), [], []
    for h, l in zip(hs, ls):
        if l in seen:
            continue
        seen.add(l)
        hh.append(h)
        ll.append(l)
    ax.legend(hh, ll, loc="upper left", fontsize=6.8, handletextpad=0.4,
              borderpad=0.35, labelspacing=0.32)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q4_partition"),
                             dpi=320, profile="competition_cn")
    print("图11 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q4_partition"),
                                     profile="competition_cn").passed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())