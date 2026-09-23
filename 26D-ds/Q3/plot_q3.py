# -*- coding: utf-8 -*-
"""问题三图表：通信覆盖与中继布点、直连链路余量分布。

两张图均为单面板（panel_count=1），符合项目锁定的"禁用子图"策略。

运行：python Q3/plot_q3.py
输出：Q3/figures/fig_q3_*.{png,pdf,svg}
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "Q3"))

import numpy as np  # noqa: E402

from common_d import COMM, RESULTS_DIR, build_scenario, fspl, gateway_point, haversine  # noqa: E402
from solve_q3 import O01, init_comm, link_max_loss  # noqa: E402

FIGDIR = os.path.join(ROOT, "Q3", "figures")


def d3(p1, p2):
    import math
    dh = haversine(p1[0], p1[1], p2[0], p2[1])
    dz = p2[2] - p1[2]
    return math.sqrt(dh * dh + dz * dz)


def margin(sc, p1, p2, key1, key2):
    """链路余量 = 门限 − 实际总损耗（正值为可用）。"""
    blocked = sc.dem.los_blocked(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], n=110)
    loss = fspl(COMM["freq_mhz"], d3(p1, p2) / 1000.0) + (COMM["L_obs"] if blocked else 0.0)
    return link_max_loss(key1, key2) - loss


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from plot_common import (PALETTE, apply_py_nature_style, run_py_nature_qa,
                             save_py_nature_figure)

    os.makedirs(FIGDIR, exist_ok=True)
    apply_py_nature_style(font_size=8.0, profile="competition_cn")

    sc = build_scenario()
    init_comm(sc)
    data = json.load(open(os.path.join(RESULTS_DIR, "q3_results.json"), encoding="utf-8"))
    hovers = data["选中悬停"]
    sched = data["运输架次"]
    GW = gateway_point(sc)

    # ---------------- 图9：运输航迹、中继布点与通信覆盖（vector_2d） ----------------
    dem = sc.dem
    nrow, ncol = dem.elev.shape
    lon_axis = dem.origin[0] + dem.res[0] * np.arange(ncol)
    lat_axis = dem.origin[1] - dem.res[1] * np.arange(nrow)
    lon_g, lat_g = np.meshgrid(lon_axis, lat_axis)

    fig, ax = plt.subplots(figsize=(6.8, 5.2))
    ax.contourf(lon_g, lat_g, dem.elev, levels=18, cmap="Greys", alpha=0.30)
    ax.contour(lon_g, lat_g, dem.elev, levels=8, colors="#9A9A9A",
               linewidths=0.35, alpha=0.65)

    # 运输航迹
    for k, s in enumerate(sched):
        route = [O01] + s["route"] + [O01]
        xs = [sc.node_xy[n][0] for n in route]
        ys = [sc.node_xy[n][1] for n in route]
        ax.plot(xs, ys, color=PALETTE["blue_secondary"], linewidth=0.7,
                alpha=0.55, zorder=3)
    areas = sc.areas
    ax.scatter([a["lon"] for a in areas], [a["lat"] for a in areas], s=24,
               marker="o", facecolor="white", edgecolor=PALETTE["black"],
               linewidths=0.8, zorder=6, label="服务区")
    for a in areas:
        ax.annotate(a["id"], (a["lon"], a["lat"]), textcoords="offset points",
                    xytext=(4.0, 3.0), fontsize=6.1, color="#1A1A1A", zorder=8)
    ax.scatter([sc.center["lon"]], [sc.center["lat"]], s=115, marker="*",
               facecolor=PALETTE["gold_main"], edgecolor="black", linewidths=0.8,
               zorder=9, label="调度中心 O01（固定网关）")

    # 中继悬停位置与回传链路
    for i, h in enumerate(hovers):
        ax.scatter([h["lon"]], [h["lat"]], s=132, marker="^",
                   facecolor=PALETTE["red_strong"], edgecolor="white",
                   linewidths=0.9, zorder=10,
                   label="中继悬停位置" if i == 0 else None)
        ax.plot([h["lon"], sc.center["lon"]], [h["lat"], sc.center["lat"]],
                color=PALETTE["red_strong"], linewidth=1.0, linestyle="--",
                alpha=0.85, zorder=5,
                label="中继—网关回传链路" if i == 0 else None)
        ax.annotate(f"{h['hover_h']:.0f} m", (h["lon"], h["lat"]),
                    textcoords="offset points", xytext=(6.0, -9.0), fontsize=6.2,
                    color=PALETTE["red_strong"], zorder=11)
    ax.set_xlabel("经度（°）")
    ax.set_ylabel("纬度（°）")
    ax.set_xlim(float(min(a["lon"] for a in areas)) - 0.016,
                float(max(a["lon"] for a in areas)) + 0.016)
    ax.set_ylim(float(min(a["lat"] for a in areas)) - 0.014,
                float(max(a["lat"] for a in areas)) + 0.016)
    ax.tick_params(labelsize=7)
    ax.set_aspect("equal", adjustable="box")
    hs, ls = ax.get_legend_handles_labels()
    seen, hh, ll = set(), [], []
    for a, b in zip(hs, ls):
        if b in seen:
            continue
        seen.add(b)
        hh.append(a)
        ll.append(b)
    ax.legend(hh, ll, loc="upper left", fontsize=6.8, handletextpad=0.4,
              borderpad=0.35, labelspacing=0.32)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q3_relay_layout"),
                             dpi=320, profile="competition_cn")
    print("图9 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q3_relay_layout"),
                                    profile="competition_cn").passed)

    # ---------------- 图10：直连链路余量分布（distribution_2d） ----------------
    # 在 15 个服务区投送作业高度上采样直连链路余量
    dir_margins = []
    for a in areas:
        pt = (a["lon"], a["lat"], a["alt"] + 30.0)
        dir_margins.append(margin(sc, pt, GW, "uav", "gateway"))
    dir_margins = np.array(dir_margins)

    # 中继接入链路余量（对选中悬停位置）
    relay_margins = []
    for h in hovers:
        rp = (h["lon"], h["lat"], h["alt"])
        for a in areas:
            pt = (a["lon"], a["lat"], a["alt"] + 30.0)
            m = margin(sc, pt, rp, "uav", "relay_acc")
            if m > -40:
                relay_margins.append(m)
    relay_margins = np.array(relay_margins) if relay_margins else np.array([0.0])

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    allv = np.concatenate([dir_margins, relay_margins])
    bins = np.linspace(min(allv.min(), -60), max(allv.max(), 10), 26)
    ax.hist(dir_margins, bins=bins, color=PALETTE["red_soft"],
            edgecolor=PALETTE["red_strong"], linewidth=0.7, alpha=0.9,
            label=f"运输无人机—固定网关直连（{len(dir_margins)} 个服务区）")
    ax.hist(relay_margins, bins=bins, color=PALETTE["blue_secondary"],
            edgecolor=PALETTE["blue_main"], linewidth=0.7, alpha=0.62,
            label=f"运输无人机—中继接入链路（{len(relay_margins)} 条组合）")
    ax.axvline(0.0, color=PALETTE["black"], linewidth=1.4, linestyle="-", zorder=6)
    ax.text(1.2, ax.get_ylim()[1] * 0.94, "可用门限（余量 = 0）", fontsize=6.9,
            color=PALETTE["black"], ha="left", va="top", zorder=8)
    n_ok = int((dir_margins > 0).sum())
    ax.text(0.985, 0.62,
            f"直连可用服务区 {n_ok}/{len(dir_margins)}\n"
            f"直连余量中位数 {np.median(dir_margins):.1f} dB\n"
            f"中继接入余量中位数 {np.median(relay_margins):.1f} dB",
            transform=ax.transAxes, ha="right", va="top", fontsize=7.0,
            bbox=dict(boxstyle="round,pad=0.32", facecolor="white",
                      edgecolor=PALETTE["neutral_light"], linewidth=0.7), zorder=9)
    ax.set_xlabel("链路余量（dB，正值为可用）")
    ax.set_ylabel("样本数")
    ax.tick_params(labelsize=7)
    ax.legend(loc="upper left", fontsize=7.0, handletextpad=0.5, borderpad=0.4)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q3_link_margin"),
                             dpi=320, profile="competition_cn")
    print("图10 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q3_link_margin"),
                                     profile="competition_cn").passed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())