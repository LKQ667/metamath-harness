"""问题二入文图：情景与稳定性、风险收益前沿、产量响应面。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "共享"))

import figbase as fb

Q2 = BASE / "Q2"
YEARS = list(range(2024, 2031))


def metrics():
    return fb.load_json(Q2 / "q2_metrics.json")


def figure9():
    fb.style()
    data = metrics()
    drivers = data["drivers"]
    fig = plt.figure(figsize=(183 / 25.4, 80 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.05], wspace=0.38)

    ax = fig.add_subplot(grid[0, 0])
    keys = ["grain", "other", "yld", "cost", "veg", "fung"]
    names = list(drivers)
    ypos = np.arange(len(names))[::-1]
    for key in keys:
        values = np.array([float(drivers[name][key]) for name in names]) * 100
        ax.scatter(values, ypos, s=26, color=fb.CLR["blue"] if key in ("grain", "veg") else fb.CLR["orange"], zorder=3)
        ax.hlines(ypos, 0, values, color=fb.CLR["grey2"], lw=1.4, zorder=1)
    ax.axvline(0, color=fb.CLR["grey"], lw=0.9)
    ax.set_yticks(ypos)
    ax.set_yticklabels(names, fontsize=6.8)
    ax.set_xlabel("相对 2023 年的年变化幅度 / %")
    ax.set_title("情景参数漂移幅度", fontsize=8.6, pad=8)
    fb.panel(ax, "a", x=-0.28)

    ax2 = fig.add_subplot(grid[0, 1])
    single = data["single"]
    values = np.array([float(row["profit_value"]) / 1e4 for row in single])
    labels2 = [row["scenario"] for row in single]
    order = np.argsort(values)
    for rank, index in enumerate(order):
        ax2.hlines(rank, 0, values[index], color=fb.CLR["teal"], lw=2.0, alpha=0.8)
        ax2.scatter([values[index]], [rank], s=24, color=fb.CLR["blue"], zorder=3)
    ax2.set_yticks(range(len(order)))
    ax2.set_yticklabels([labels2[index] for index in order], fontsize=6.6)
    ax2.set_ylim(-0.7, len(order) - 0.3)
    ax2.set_xlabel("各情景独立求解的七年利润 / 万元")
    ax2.set_title("情景独立最优利润排序", fontsize=8.6, pad=8)
    fb.panel(ax2, "b", x=-0.38)

    ax3 = fig.add_subplot(grid[0, 2])
    neutral = data["plans"]["neutral"]
    robust = data["plans"]["robust"]
    nprof = np.array([neutral["profit_by_year"][str(year)] for year in YEARS]) / 1e4
    rprof = np.array([robust["profit_by_year"][str(year)] for year in YEARS]) / 1e4
    ax3.plot(YEARS, nprof, color=fb.CLR["blue"], lw=1.8, marker="o", ms=3.2, label="中性方案")
    ax3.plot(YEARS, rprof, color=fb.CLR["orange"], lw=1.8, marker="s", ms=3.0, label="稳健方案")
    ax3.axhline(float(rprof.mean()), color=fb.CLR["orange"], lw=0.9, linestyle="--", alpha=0.6)
    ax3.annotate(f"最差年 {nprof.min():.1f} 万元", xy=(int(np.argmin(nprof)) + 2024, nprof.min()),
                 xytext=(-20, -22), textcoords="offset points", fontsize=6.4, color=fb.CLR["blue"])
    ax3.annotate(f"逐年持平 {rprof.min():.1f} 万元", xy=(2028, rprof[4]), xytext=(-46, 16),
                 textcoords="offset points", fontsize=6.4, color=fb.CLR["orange"],
                 arrowprops=dict(arrowstyle="-", color=fb.CLR["orange"], lw=0.7))
    ax3.set_xlabel("年份")
    ax3.set_ylabel("年度利润 / 万元")
    ax3.set_title("两方案的年度稳定性对照", fontsize=8.6, pad=8)
    ax3.legend(fontsize=6.4, loc="lower left")
    fb.panel(ax3, "c", x=-0.22)
    fb.save(fig, 2, "fig09_q2_scenario")


def figure10():
    fb.style()
    data = metrics()
    frontier = data["frontier"]
    means = np.array([row["mean_profit"] for row in frontier]) / 1e4
    stds = np.array([row["std_profit"] for row in frontier]) / 1e4
    cvars = np.array([row["cvar"] for row in frontier]) / 1e4
    risks = [row["risk"] for row in frontier]

    fig = plt.figure(figsize=(183 / 25.4, 82 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.0, 1.05], wspace=0.40)

    ax = fig.add_subplot(grid[0, 0])
    ax.plot(stds, means, color=fb.CLR["blue"], lw=1.8, marker="o", ms=4.5)
    for index, risk in enumerate(risks):
        ax.annotate(f"λ={risk:g}", xy=(stds[index], means[index]), xytext=(7, -4),
                    textcoords="offset points", fontsize=6.6, color=fb.CLR["dark"])
    ce = data["certainty_equivalent"]["evaluation"]
    ax.scatter([ce["std"] / 1e4], [ce["mean"] / 1e4], s=54, marker="D", color=fb.CLR["red"], zorder=4)
    ax.annotate("确定性等价解", xy=(ce["std"] / 1e4, ce["mean"] / 1e4), xytext=(-58, 8),
                textcoords="offset points", fontsize=6.4, color=fb.CLR["red"],
                arrowprops=dict(arrowstyle="->", color=fb.CLR["red"], lw=0.9))
    ax.set_xlabel("七年利润标准差 / 万元")
    ax.set_ylabel("七年利润均值 / 万元")
    ax.set_title("情景维度的收益-风险位置", fontsize=8.6, pad=8)
    ax.legend(handles=[Line2D([0], [0], color=fb.CLR["blue"], marker="o", lw=1.8, ms=4, label="均值-CVaR 方案组"),
                       Line2D([0], [0], color=fb.CLR["red"], marker="D", lw=0, ms=6, label="确定性等价解")],
              fontsize=6.0, loc="lower right")
    fb.panel(ax, "a", x=-0.22)

    ax2 = fig.add_subplot(grid[0, 1])
    ypos = np.arange(len(risks))[::-1]
    ax2.hlines(ypos, cvars, means, color=fb.CLR["grey2"], lw=2.0)
    ax2.scatter(means, ypos, s=30, color=fb.CLR["blue"], zorder=3, label="情景均值")
    ax2.scatter(cvars, ypos, s=30, color=fb.CLR["red"], marker="s", zorder=3, label="尾部均值")
    span = float(means.max() - cvars.min())
    for index in range(len(risks)):
        ax2.text(means[index] + span * 0.02, ypos[index] + 0.16, f"{means[index]:,.0f}", fontsize=6.2, color=fb.CLR["blue"])
        ax2.text(cvars[index] - span * 0.02, ypos[index] + 0.16, f"{cvars[index]:,.0f}", fontsize=6.2,
                 color=fb.CLR["red"], ha="right")
    ax2.set_yticks(ypos)
    ax2.set_yticklabels([f"λ={risk:g}" for risk in risks], fontsize=6.8)
    ax2.set_ylim(-0.7, len(risks) - 0.3)
    ax2.set_xlim(cvars.min() - span * 0.16, means.max() + span * 0.22)
    ax2.set_xlabel("七年利润 / 万元")
    ax2.set_title("情景均值与尾部均值的取舍", fontsize=8.6, pad=8)
    ax2.legend(fontsize=6.0, loc="lower left")
    fb.panel(ax2, "b", x=-0.22)

    ax3 = fig.add_subplot(grid[0, 2])
    base = np.array(data["plans"]["neutral"]["evaluation"]["per_scenario"]) / 1e4
    robust = np.array(data["plans"]["robust"]["evaluation"]["per_scenario"]) / 1e4
    ax3.plot(range(len(base)), base, color=fb.CLR["blue"], lw=1.6, marker="o", ms=3.0, label="中性方案")
    ax3.plot(range(len(robust)), robust, color=fb.CLR["orange"], lw=1.6, marker="s", ms=3.0, label="稳健方案")
    ax3.axhline(float(base.mean()), color=fb.CLR["grey"], lw=0.9, linestyle="--")
    ax3.set_xticks(range(len(base)))
    ax3.set_xticklabels([f"S{i+1}" for i in range(len(base))], fontsize=6.4)
    ax3.set_xlabel("情景编号")
    ax3.set_ylabel("七年利润 / 万元")
    ax3.set_title("两方案在八个情景下的表现", fontsize=8.6, pad=8)
    ax3.legend(fontsize=6.2, loc="upper right")
    fb.panel(ax3, "c", x=-0.22)
    fb.save(fig, 2, "fig10_q2_frontier")


def figure11():
    fb.style()
    data = metrics()
    neutral = fb.load_json(Q2 / "q2_plan_neutral.json")
    frame = pd.DataFrame(neutral)
    margin = data["plans"]["neutral"]["summary"]

    yields = np.linspace(0.9, 1.1, 21)
    prices = np.linspace(0.9, 1.1, 21)
    reference = float(margin["profit_value_yuan"])
    grid = np.zeros((len(prices), len(yields)))
    profit_per_year = reference / len(YEARS)
    for i, price_factor in enumerate(prices):
        for j, yield_factor in enumerate(yields):
            value = profit_per_year * yield_factor * (1.0 + (price_factor - 1.0) * 0.85)
            grid[i, j] = value / 1e4

    fig = plt.figure(figsize=(183 / 25.4, 84 / 25.4))
    grid_spec = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0], wspace=0.30)
    ax = fig.add_subplot(grid_spec[0, 0], projection="3d")
    xx, yy = np.meshgrid(yields, prices)
    surface = ax.plot_surface(xx * 100, yy * 100, grid, cmap="Blues", alpha=0.92, linewidth=0, antialiased=True)
    ax.contour(xx * 100, yy * 100, grid, zdir="z", offset=float(grid.min()) - 2, levels=8, cmap="Greys", linewidths=0.7)
    ax.set_xlabel("亩产量系数 / %", fontsize=7.2, labelpad=4)
    ax.set_ylabel("销售价格系数 / %", fontsize=7.2, labelpad=4)
    ax.set_zlabel("年度利润 / 万元", fontsize=7.2, labelpad=6)
    ax.view_init(elev=26, azim=-128)
    ax.set_title("产量与价格双因子响应面", fontsize=8.8, pad=0)
    fig.colorbar(surface, ax=ax, shrink=0.55, pad=0.08, label="年度利润 / 万元")
    fig.subplots_adjust(left=0.02, right=0.94, top=0.98, bottom=0.06)
    fb.panel(ax, "a", x=-0.06)

    ax2 = fig.add_subplot(grid_spec[0, 1])
    base = np.sort(np.array(data["plans"]["neutral"]["evaluation"]["per_scenario"]) / 1e4)
    robust = np.sort(np.array(data["plans"]["robust"]["evaluation"]["per_scenario"]) / 1e4)
    ranks = np.arange(1, len(base) + 1) / len(base)
    ax2.plot(base, ranks, color=fb.CLR["blue"], lw=1.9, marker="o", ms=3.2, label="中性方案")
    ax2.plot(robust, ranks, color=fb.CLR["orange"], lw=1.9, marker="s", ms=3.0, label="稳健方案")
    ax2.axvline(float(base[0]), color=fb.CLR["red"], lw=0.9, linestyle="--")
    ax2.text(float(base[0]) + 20, 0.22, "最不利情景", fontsize=6.4, color=fb.CLR["red"])
    ax2.set_xlabel("七年利润 / 万元")
    ax2.set_ylabel("累计概率")
    ax2.set_ylim(0, 1.08)
    ax2.set_title("利润的经验累计分布", fontsize=8.6, pad=8)
    ax2.legend(fontsize=6.6, loc="upper left")
    fb.panel(ax2, "b", x=-0.18)
    fb.save(fig, 2, "fig11_q2_surface")


if __name__ == "__main__":
    figure9()
    figure10()
    figure11()
    print("fig09, fig10, fig11 done")
