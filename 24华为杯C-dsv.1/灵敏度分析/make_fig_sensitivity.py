"""灵敏度分析入文图：单因素响应、排序与三维响应结构。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "共享"))

import figbase as fb

SRC = BASE / "灵敏度分析" / "sensitivity_metrics.json"
NAMES = {"yield": "亩产量", "cost": "种植成本", "price": "销售价格", "demand": "预期销售量"}
COLORS = {"yield": fb.CLR["teal"], "cost": fb.CLR["orange"], "price": fb.CLR["blue"], "demand": fb.CLR["violet"]}


def main():
    fb.style()
    data = fb.load_json(SRC)
    levels = data["levels"]
    cases = data["cases"]
    base = float(data["base_profit"])
    factors = data["factors"]

    fig = plt.figure(figsize=(183 / 25.4, 84 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.15, 1.15], wspace=0.38)

    ax = fig.add_subplot(grid[0, 0])
    impact = []
    for factor in factors:
        picked = [item for item in cases if item["factor"] == factor]
        low = next(item for item in picked if item["level"] == min(levels))
        high = next(item for item in picked if item["level"] == max(levels))
        impact.append((NAMES[factor], (low["profit"] - base) / base * 100, (high["profit"] - base) / base * 100, factor))
    impact.sort(key=lambda item: abs(item[2] - item[1]))
    ypos = np.arange(len(impact))
    for index, (name, down, up, factor) in enumerate(impact):
        ax.hlines(ypos[index], down, up, color=COLORS[factor], lw=2.6, alpha=0.9)
        ax.scatter([down], [ypos[index]], s=26, color=COLORS[factor], marker="v", zorder=3)
        ax.scatter([up], [ypos[index]], s=26, color=COLORS[factor], marker="^", zorder=3)
        ax.text(up + 0.6, ypos[index], f"{up:+.1f}%", fontsize=6.6, va="center", color=COLORS[factor])
        ax.text(down - 0.6, ypos[index], f"{down:+.1f}%", fontsize=6.6, va="center", ha="right", color=COLORS[factor])
    ax.axvline(0, color=fb.CLR["grey"], lw=0.9)
    ax.set_yticks(ypos)
    ax.set_yticklabels([item[0] for item in impact], fontsize=7.0)
    ax.set_xlim(min(item[1] for item in impact) - 5, max(item[2] for item in impact) + 5)
    ax.set_xlabel("七年利润相对基准的变化 / %")
    ax.set_title("±20% 扰动的利润影响排序", fontsize=8.6, pad=8)
    ax.legend(handles=[Line2D([0], [0], color=fb.CLR["grey"], marker="v", lw=0, ms=6, label="下浮 20%"),
                       Line2D([0], [0], color=fb.CLR["grey"], marker="^", lw=0, ms=6, label="上浮 20%")],
              fontsize=6.0, loc="lower right")
    fb.panel(ax, "a", x=-0.30)

    ax2 = fig.add_subplot(grid[0, 1])
    for factor in factors:
        picked = sorted([item for item in cases if item["factor"] == factor], key=lambda item: item["level"])
        xs = [item["level"] * 100 for item in picked]
        ys = [(item["profit"] - base) / base * 100 for item in picked]
        ax2.plot(xs, ys, color=COLORS[factor], lw=1.7, marker="o", ms=3.2, label=NAMES[factor])
    ax2.axhline(0, color=fb.CLR["grey"], lw=0.9, linestyle="--")
    ax2.axvline(0, color=fb.CLR["grey"], lw=0.9, linestyle="--")
    ax2.set_xlabel("参数扰动幅度 / %")
    ax2.set_ylabel("七年利润相对基准的变化 / %")
    ax2.set_title("单因素响应曲线", fontsize=8.6, pad=8)
    ax2.legend(fontsize=6.2, loc="upper left")
    fb.panel(ax2, "b", x=-0.18)

    ax3 = fig.add_subplot(grid[0, 2], projection="3d")
    for index, factor in enumerate(factors):
        picked = sorted([item for item in cases if item["factor"] == factor], key=lambda item: item["level"])
        xs = [item["level"] * 100 for item in picked]
        zs = [(item["profit"] - base) / base * 100 for item in picked]
        ys = np.full(len(xs), index, dtype=float)
        ax3.plot(xs, ys, zs, color=COLORS[factor], lw=1.6, marker="o", ms=3.0)
        for x, y, z in zip(xs, ys, zs):
            ax3.plot([x, x], [y, y], [0, z], color=COLORS[factor], lw=0.8, alpha=0.6)
    ax3.set_xticks([value * 100 for value in levels])
    ax3.set_yticks(range(len(factors)))
    ax3.set_yticklabels([NAMES[factor] for factor in factors], fontsize=6.6)
    ax3.set_xlabel("扰动幅度 / %", fontsize=7.2, labelpad=4)
    ax3.set_ylabel("参数", fontsize=7.2, labelpad=4)
    ax3.set_zlabel("利润变化 / %", fontsize=7.2, labelpad=2)
    ax3.view_init(elev=24, azim=-62)
    ax3.set_title("四个参数的三维响应结构", fontsize=8.6, pad=0)
    fig.subplots_adjust(left=0.02, right=0.90, top=0.98, bottom=0.06)
    fb.panel(ax3, "c", x=-0.06)
    fb.save(fig, 1, "fig15_sensitivity")
    print("fig15 done")


if __name__ == "__main__":
    main()
