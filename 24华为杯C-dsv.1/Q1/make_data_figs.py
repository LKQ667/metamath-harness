"""论文图 1、2：土地与作物结构、调研数据分布。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "共享"))

import figbase as fb

DATA = BASE / "data" / "派生"
ORDER = ["平旱地", "梯田", "山坡地", "水浇地", "普通大棚", "智慧大棚"]
COLOR = {
    "平旱地": "#3775BA",
    "梯田": "#0F4D92",
    "山坡地": "#42949E",
    "水浇地": "#3F8EFC",
    "普通大棚": "#E28E2C",
    "智慧大棚": "#B64342",
}
SEASONS = {"平旱地": 1, "梯田": 1, "山坡地": 1, "水浇地": 2, "普通大棚": 2, "智慧大棚": 2}


def figure1():
    fb.style()
    plots = pd.read_csv(DATA / "plots.csv")
    crops = pd.read_csv(DATA / "crops.csv")
    crops["space_list"] = crops["space_list"].astype(str)
    fig = plt.figure(figsize=(183 / 25.4, 104 / 25.4))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], width_ratios=[1.5, 1.0], hspace=0.60, wspace=0.26)

    ax = fig.add_subplot(grid[0, 0])
    counts = plots["plot_type"].value_counts().reindex(ORDER)
    areas = plots.groupby("plot_type")["area"].sum().reindex(ORDER)
    total = float(areas.sum())
    left = 0.0
    for name in ORDER:
        width = float(areas[name])
        ax.add_patch(Rectangle((left, 0.16), width, 0.46, facecolor=COLOR[name], edgecolor="white", linewidth=1.1))
        if width / total > 0.09:
            ax.text(left + width / 2, 0.39, f"{name}\n{width:.0f} 亩 · {int(counts[name])} 块", ha="center", va="center",
                    fontsize=7.6, color="white", linespacing=1.4)
        left += width
    cursor = 0.0
    notes = []
    for name in ORDER:
        width = float(areas[name])
        if width / total <= 0.09:
            notes.append((cursor + width / 2, name, width))
        cursor += width
    for index, (center, name, width) in enumerate(notes):
        ax.annotate(f"{name} {width:.1f} 亩 · {int(counts[name])} 块", xy=(center, 0.62),
                    xytext=(1120, 1.04 - index * 0.10), fontsize=6.9, ha="right", va="center",
                    color=fb.CLR["dark"],
                    arrowprops=dict(arrowstyle="-", color=fb.CLR["grey"], lw=0.7, shrinkA=0, shrinkB=2))
    ax.set_xlim(-8, total + 8)
    ax.set_ylim(0, 1.18)
    ax.set_yticks([])
    ax.set_xlabel("耕地面积 / 亩")
    ax.set_title("六类耕地的面积构成与地块数量", fontsize=8.8, pad=6)
    ax.spines["left"].set_visible(False)
    fb.panel(ax, "a", x=-0.05)

    ax2 = fig.add_subplot(grid[0, 1])
    for index, name in enumerate(ORDER):
        for slot in range(SEASONS[name]):
            ax2.add_patch(Rectangle((index - 0.36, 0.22 + slot * 0.34), 0.72, 0.26,
                                    facecolor=COLOR[name], alpha=0.88, edgecolor="white", linewidth=0.8))
    ax2.set_xlim(-0.7, len(ORDER) - 0.3)
    ax2.set_ylim(0, 1.0)
    ax2.set_xticks(range(len(ORDER)))
    ax2.set_xticklabels(ORDER, fontsize=7.0, rotation=22, ha="right")
    ax2.set_yticks([0.35, 0.69])
    ax2.set_yticklabels(["第一季", "第二季"], fontsize=7.4)
    ax2.set_title("各类地块的季次容量", fontsize=8.8, pad=6)
    for spine in ax2.spines.values():
        spine.set_visible(False)
    fb.panel(ax2, "b", x=-0.10)

    ax3 = fig.add_subplot(grid[1, :])
    families = ["粮食", "粮食（豆类）", "蔬菜", "蔬菜（豆类）", "食用菌"]
    for row, family in enumerate(families):
        y = len(families) - row - 1
        subset = crops[crops["family"] == family]
        for column, space in enumerate(ORDER):
            names = subset[subset["space_list"].str.contains(space, regex=False)]["crop"].tolist()
            if not names:
                continue
            shade = 0.18 + 0.75 * (len(names) / 16.0)
            ax3.add_patch(Rectangle((column - 0.46, y - 0.42), 0.92, 0.84,
                                    facecolor=fb.FAMILY[family], alpha=min(shade, 0.92), edgecolor="white", linewidth=0.8))
            text = f"{len(names)} 种"
            ax3.text(column, y + 0.13, text, ha="center", va="center", fontsize=7.4, fontweight="bold",
                     color="white" if shade > 0.55 else fb.CLR["ink"])
            ax3.text(column, y - 0.16, "、".join(names[:3]) + ("…" if len(names) > 3 else ""), ha="center", va="center",
                     fontsize=5.9, color="white" if shade > 0.55 else fb.CLR["dark"])
    ax3.set_xticks(range(len(ORDER)))
    ax3.set_xticklabels(ORDER, fontsize=7.6)
    ax3.set_yticks(range(len(families)))
    ax3.set_yticklabels(families[::-1], fontsize=7.6)
    ax3.set_xlim(-0.6, len(ORDER) - 0.4)
    ax3.set_ylim(-0.6, len(families) - 0.4)
    ax3.set_title("作物类型与可种空间的匹配：单元格为可种作物种类数，色深与数量同向", fontsize=8.8, pad=6)
    for spine in ax3.spines.values():
        spine.set_visible(False)
    fb.panel(ax3, "c", x=-0.05)
    fb.save(fig, 1, "fig01_land_crop")


def figure2():
    fb.style()
    params = pd.read_csv(DATA / "params.csv")
    crops = pd.read_csv(DATA / "crops.csv")
    merged = params.merge(crops[["crop_id", "family"]], on="crop_id", how="left")
    pick = merged[merged["plot_type"].isin(["平旱地", "水浇地", "普通大棚"])].copy()
    pick = pick.drop_duplicates(subset=["crop_id", "plot_type", "season"])

    fig = plt.figure(figsize=(183 / 25.4, 92 / 25.4))
    grid = fig.add_gridspec(2, 3, width_ratios=[1.10, 1.0, 1.0], hspace=0.52, wspace=0.36)

    ax = fig.add_subplot(grid[:, 0])
    scale = pick["price_mid"].max()
    for family, group in pick.groupby("family"):
        ax.scatter(group["yield_jin"], group["cost_yuan"],
                   s=12 + 54 * (group["price_mid"] / scale),
                   facecolor=fb.FAMILY.get(family, fb.CLR["grey"]), edgecolor="white", linewidth=0.5,
                   alpha=0.88, label=family)
    ax.set_xscale("log")
    ax.set_xlabel("亩产量 / 斤（对数轴）")
    ax.set_ylabel("种植成本 /（元/亩）")
    ax.set_title("亩产量与种植成本的联合分布\n点面积正比于名义单价", fontsize=8.6, pad=6)
    ax.legend(fontsize=6.4, loc="upper left", handletextpad=0.35, labelspacing=0.3)
    fb.panel(ax, "a")

    ax2 = fig.add_subplot(grid[0, 1])
    bins = np.linspace(0, 16, 17)
    ax2.hist(pick["price_mid"], bins=bins, color=fb.CLR["blue2"], alpha=0.78, edgecolor="white", linewidth=0.6)
    ax2.set_xlabel("名义销售单价 /（元/斤）")
    ax2.set_ylabel("参数条目数")
    ax2.set_title("销售单价名义值分布", fontsize=8.6, pad=6)
    fb.panel(ax2, "b")

    ax3 = fig.add_subplot(grid[0, 2])
    families = ["粮食", "粮食（豆类）", "蔬菜", "蔬菜（豆类）", "食用菌"]
    values = [int((crops["family"] == name).sum()) for name in families]
    y = np.arange(len(families))[::-1]
    ax3.hlines(y, 0, values, color=fb.CLR["grey2"], linewidth=5.0)
    for index, (name, value) in enumerate(zip(families, values)):
        ax3.scatter([value], [y[index]], s=44, color=fb.FAMILY[name], zorder=3)
        ax3.text(value + 0.4, y[index], str(value), va="center", fontsize=7.2)
    ax3.set_yticks(y)
    ax3.set_yticklabels(families, fontsize=7.2)
    ax3.set_xlim(0, max(values) + 3)
    ax3.set_xlabel("作物种类数")
    ax3.set_title("作物类型的数量结构", fontsize=8.6, pad=6)
    fb.panel(ax3, "c")

    ax4 = fig.add_subplot(grid[1, 1:])
    best = (
        pick.assign(gross=pick["yield_jin"] * pick["price_mid"] - pick["cost_yuan"])
        .sort_values("gross", ascending=False)
        .drop_duplicates(subset=["crop_id"])
        .head(11)
    )
    names = best["crop"].astype(str).tolist()
    diff = (best["yield_jin"] * best["price_mid"] - best["cost_yuan"]).to_numpy()
    base = best["cost_yuan"].to_numpy()
    ypos = np.arange(len(names))[::-1]
    ax4.hlines(ypos, base, base + diff, color=fb.CLR["green"], linewidth=2.4, alpha=0.6)
    ax4.scatter(base, ypos, s=24, color=fb.CLR["grey"], zorder=3, label="种植成本")
    ax4.scatter(base + diff, ypos, s=28, color=fb.CLR["blue"], zorder=3, label="成本 + 亩均毛利")
    ax4.set_yticks(ypos)
    ax4.set_yticklabels([f"{name}（{row}）" for name, row in zip(names, best["plot_type"])], fontsize=6.6)
    ax4.set_xlabel("单位面积金额 /（元/亩）")
    ax4.set_title("亩均毛利空间最大的 11 个作物", fontsize=8.6, pad=6)
    ax4.legend(fontsize=6.6, loc="lower right")
    fb.panel(ax4, "d", x=-0.34)
    fb.save(fig, 1, "fig02_data_survey")


if __name__ == "__main__":
    figure1()
    figure2()
    print("fig01, fig02 done")
