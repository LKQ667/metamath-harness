# -*- coding: utf-8 -*-
"""问题二图表：方案—指标权衡矩阵、逐区送达时序、架次载荷利用率分布。

三张图均为单面板（panel_count=1），符合项目锁定的"禁用子图"策略。

运行：python Q2/plot_q2.py
输出：Q2/figures/fig_q2_*.{png,pdf,svg}
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402

from common_d import RESULTS_DIR, build_scenario  # noqa: E402

FIGDIR = os.path.join(ROOT, "Q2", "figures")
METRIC_LABELS = ["加权总延误", "全部任务完成时间", "总运输能耗", "往返架次数"]
METRIC_KEYS = ["tardy", "makespan", "energy", "n_sorties"]


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from plot_common import (PALETTE, apply_py_nature_style, run_py_nature_qa,
                             save_py_nature_figure)
    from label_util import box_of_artist, place_labels

    os.makedirs(FIGDIR, exist_ok=True)
    apply_py_nature_style(font_size=8.0, profile="competition_cn")

    sc = build_scenario()
    data = json.load(open(os.path.join(RESULTS_DIR, "q2_results.json"), encoding="utf-8"))
    plans = data["方案集"]
    names = list(plans.keys())
    main_name = data["主方案"]

    # ---------------- 图6：方案—指标权衡矩阵（heatmap_2d） ----------------
    raw = np.array([[plans[n][k] for k in METRIC_KEYS] for n in names], dtype=float)
    # 列内极差归一化：该指标最好的方案为 0（绿），最差的为 1（红）
    lo = raw.min(axis=0)
    hi = raw.max(axis=0)
    span = np.where(hi - lo > 1e-12, hi - lo, 1.0)
    norm = (raw - lo) / span
    order = np.argsort(norm.sum(axis=1))
    names_o = [names[i] for i in order]
    raw_o = raw[order]
    norm_o = norm[order]

    fig, ax = plt.subplots(figsize=(6.4, 3.5))
    im = ax.imshow(norm_o, cmap="RdYlGn_r", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(METRIC_KEYS)))
    ax.set_xticklabels(METRIC_LABELS, fontsize=7.4)
    ax.set_yticks(range(len(names_o)))
    ylabels = [f"{n}（主方案）" if n == main_name else n for n in names_o]
    ax.set_yticklabels(ylabels, fontsize=7.4)
    for i in range(len(names_o)):
        for j in range(len(METRIC_KEYS)):
            v = raw_o[i, j]
            txt = f"{v:,.0f}" if METRIC_KEYS[j] != "energy" else f"{v:.2f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7.0,
                    color="white" if norm_o[i, j] > 0.62 else "#1A1A1A", zorder=5)
    cb = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.040)
    cb.set_label("列内极差归一化（0 为该指标最优）", fontsize=7.4)
    cb.ax.tick_params(labelsize=6.8)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q2_plan_metrics"),
                             dpi=320, profile="competition_cn")
    print("图6 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q2_plan_metrics"),
                                    profile="competition_cn").passed)

    # ---------------- 图7：逐区送达时序与首批截止档位（line_2d） ----------------
    boxes = {b["box_id"]: b for b in sc.boxes}
    deliver = data["逐箱送达"]
    areas = [a["id"] for a in sc.areas]

    per_area = {}
    for a in areas:
        ids = [b["box_id"] for b in sc.boxes if b["area_id"] == a]
        ts = sorted(deliver[b] for b in ids)
        first = sorted(deliver[b] for b in ids if boxes[b]["is_first_batch"])
        rest = sorted(deliver[b] for b in ids if not boxes[b]["is_first_batch"])
        per_area[a] = {"all": ts, "first": first, "rest": rest,
                       "deadline": min((boxes[b]["first_deadline"] for b in ids
                                        if boxes[b]["is_first_batch"]), default=None),
                       "expect_max": max(boxes[b]["expect_time"] for b in ids)}

    order_a = sorted(areas, key=lambda a: (per_area[a]["deadline"] or 10 ** 9,
                                           per_area[a]["all"][-1]))
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    ypos = np.arange(len(order_a))
    for tier, ls in ((3600, ":"), (7200, "--"), (10800, "-.")):
        ax.axvline(tier, color=PALETTE["neutral_dark"], linewidth=0.9,
                   linestyle=ls, alpha=0.55, zorder=2)
        ax.text(tier, len(order_a) - 0.35, f"{tier//3600} h", fontsize=6.6,
                color=PALETTE["neutral_dark"], ha="center", va="bottom", zorder=8)
    for i, a in enumerate(order_a):
        d = per_area[a]
        ax.hlines(ypos[i], d["all"][0], d["all"][-1],
                  color=PALETTE["neutral_mid"], linewidth=1.2, zorder=3)
        if d["rest"]:
            ax.scatter(d["rest"], [ypos[i]] * len(d["rest"]), s=17, marker="o",
                       facecolor=PALETTE["blue_secondary"], edgecolor="white",
                       linewidths=0.5, zorder=5)
        if d["first"]:
            ax.scatter(d["first"], [ypos[i]] * len(d["first"]), s=30, marker="D",
                       facecolor=PALETTE["gold_main"], edgecolor=PALETTE["black"],
                       linewidths=0.6, zorder=7)
        if d["deadline"]:
            ax.scatter([d["deadline"]], [ypos[i]], s=46, marker="|",
                       color=PALETTE["red_strong"], linewidths=1.7, zorder=8)
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="D", linestyle="none", markersize=6,
               markerfacecolor=PALETTE["gold_main"], markeredgecolor=PALETTE["black"],
               label="首批保障货箱送达时刻"),
        Line2D([], [], marker="o", linestyle="none", markersize=5,
               markerfacecolor=PALETTE["blue_secondary"], markeredgecolor="white",
               label="其余货箱送达时刻"),
        Line2D([], [], marker="|", linestyle="none", markersize=9,
               color=PALETTE["red_strong"], markeredgewidth=1.7,
               label="该区首批截止时间"),
    ]
    ax.set_yticks(ypos)
    ax.set_yticklabels(order_a, fontsize=7)
    ax.set_xlabel("任务开始后的时刻（s）")
    ax.set_ylabel("服务区（按首批截止时间排序）")
    ax.set_xlim(0, max(per_area[a]["all"][-1] for a in areas) * 1.05)
    ax.set_ylim(-0.7, len(order_a) - 0.1)
    ax.tick_params(labelsize=7)
    ax.legend(handles=handles, loc="lower right", fontsize=7.0,
              handletextpad=0.5, borderpad=0.4)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q2_delivery_timeline"),
                             dpi=320, profile="competition_cn")
    print("图7 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q2_delivery_timeline"),
                                    profile="competition_cn").passed)

    # ---------------- 图8：架次载荷利用率分布（box_2d） ----------------
    sched = data["架次明细"]
    groups = {}
    for r in sched:
        g = r["type_id"]
        cap = sc.types[g]["q_max"]
        groups.setdefault(g, []).append(100.0 * r["load_mass"] / cap)
    gorder = [g for g in ("A", "B", "C") if g in groups]

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    bp = ax.boxplot([groups[g] for g in gorder], positions=range(len(gorder)),
                    widths=0.46, patch_artist=True, showfliers=False,
                    medianprops=dict(color=PALETTE["black"], linewidth=1.3),
                    whiskerprops=dict(color=PALETTE["neutral_dark"], linewidth=0.9),
                    capprops=dict(color=PALETTE["neutral_dark"], linewidth=0.9))
    cols = {"A": PALETTE["blue_main"], "B": PALETTE["teal_main"], "C": PALETTE["red_strong"]}
    for patch, g in zip(bp["boxes"], gorder):
        patch.set_facecolor(cols[g])
        patch.set_alpha(0.42)
        patch.set_edgecolor(PALETTE["neutral_dark"])
        patch.set_linewidth(0.9)
    rng = np.random.default_rng(5)
    for i, g in enumerate(gorder):
        ys = np.array(groups[g])
        xs = i + rng.uniform(-0.13, 0.13, size=len(ys))
        ax.scatter(xs, ys, s=15, facecolor=cols[g], edgecolor="white",
                   linewidths=0.5, zorder=5)
        ax.annotate(f"n={len(ys)}", (i, -3.5), fontsize=6.9, ha="center",
                    color=PALETTE["neutral_dark"])
    ax.axhline(100.0, color=PALETTE["neutral_dark"], linewidth=0.9,
               linestyle="--", zorder=2)
    ax.text(len(gorder) - 0.55, 101.5, "额定载货质量上限", fontsize=6.9,
            color=PALETTE["neutral_dark"], ha="right", va="bottom", zorder=8)
    ax.set_xticks(range(len(gorder)))
    ax.set_xticklabels([f"{g} 型" for g in gorder], fontsize=7.6)
    ax.set_ylabel("架次载荷利用率（载荷 / 额定载货质量，%）")
    ax.set_xlabel("运输机型")
    ax.set_ylim(-8, 112)
    ax.tick_params(labelsize=7)
    ax.set_xlim(-0.6, len(gorder) - 0.4)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q2_load_utilization"),
                             dpi=320, profile="competition_cn")
    print("图8 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q2_load_utilization"),
                                    profile="competition_cn").passed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())