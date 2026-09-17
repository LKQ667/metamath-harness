"""问题一入文图：利润构成、两情形对比与种植时空结构。"""

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

Q1 = BASE / "Q1"
YEARS = list(range(2024, 2031))
FAMILY_ORDER = ["粮食", "粮食（豆类）", "蔬菜", "蔬菜（豆类）", "食用菌"]


def load(key):
    return fb.load_json(Q1 / f"q1_plan_{key}.json"), fb.load_json(Q1 / f"q1_sales_{key}.json"), fb.load_json(Q1 / "q1_metrics.json")


def family_of(name, crops):
    return crops.get(name, "粮食")


def figure6():
    fb.style()
    plan1, sales1, metrics = load("case1")
    plan2, sales2, _ = load("case2")
    crop_rows = pd.read_csv(BASE / "data" / "派生" / "crops.csv").to_dict("records")
    crops = {row["crop"]: row["family"] for row in crop_rows}
    frame1 = pd.DataFrame(plan1)
    frame2 = pd.DataFrame(plan2)
    frame1["family"] = frame1["crop"].map(crops)
    frame2["family"] = frame2["crop"].map(crops)

    fig = plt.figure(figsize=(183 / 25.4, 84 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.0, 1.0], wspace=0.36)

    ax = fig.add_subplot(grid[0, 0])
    years = np.array(YEARS)
    profit1 = np.array([metrics["case1"]["profit_by_year"][str(year)] for year in YEARS]) / 1e4
    profit2 = np.array([metrics["case2"]["profit_by_year"][str(year)] for year in YEARS]) / 1e4
    ax.plot(years, profit1, color=fb.CLR["blue"], lw=1.9, marker="o", ms=3.4, label="情形一 超产滞销")
    ax.plot(years, profit2, color=fb.CLR["orange"], lw=1.9, marker="s", ms=3.2, label="情形二 超产降价 50%")
    ax.fill_between(years, profit1, profit2, color=fb.CLR["grey2"], alpha=0.26, linewidth=0)
    low = int(np.argmin(profit1))
    ax.annotate(f"最低 {profit1[low]:.1f} 万元", xy=(years[low], profit1[low]), xytext=(-6, 10),
                textcoords="offset points", fontsize=6.6, ha="right", color=fb.CLR["dark"])
    high = int(np.argmax(profit1))
    gap = abs(profit1 - profit2).max()
    ax.annotate(f"两情形最大差距 {gap:.2f} 万元", xy=(years[high], (profit1[high] + profit2[high]) / 2),
                xytext=(18, -26), textcoords="offset points", fontsize=6.6, color=fb.CLR["dark"],
                arrowprops=dict(arrowstyle="-", color=fb.CLR["grey"], lw=0.7))
    ax.set_xlabel("年份")
    ax.set_ylabel("年度净利润 / 万元")
    ax.set_title("两情形逐年净利润轨迹", fontsize=8.6, pad=8)
    ax.legend(fontsize=6.4, loc="lower left", bbox_to_anchor=(0.02, 0.02))
    ax.set_ylim(min(profit1.min(), profit2.min()) - 3, max(profit1.max(), profit2.max()) + 3)
    fb.panel(ax, "a")

    ax2 = fig.add_subplot(grid[0, 1])
    series1 = frame1.groupby("family")["area"].sum() / len(YEARS)
    series2 = frame2.groupby("family")["area"].sum() / len(YEARS)
    families = [name for name in FAMILY_ORDER if name in series1.index or name in series2.index]
    ypos = np.arange(len(families))[::-1]
    for index, family in enumerate(families):
        left = float(series1.get(family, 0.0))
        right = float(series2.get(family, 0.0))
        ax2.hlines(ypos[index] + 0.16, 0, left, color=fb.CLR["blue"], lw=2.2, alpha=0.85)
        ax2.scatter([left], [ypos[index] + 0.16], s=20, color=fb.CLR["blue"], zorder=3)
        ax2.hlines(ypos[index] - 0.16, 0, right, color=fb.CLR["orange"], lw=2.2, alpha=0.85)
        ax2.scatter([right], [ypos[index] - 0.16], s=20, color=fb.CLR["orange"], zorder=3)
        ax2.text(max(left, right) + 4, ypos[index], f"{left:.0f} / {right:.0f}", va="center", fontsize=6.2)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(families, fontsize=6.8)
    ax2.set_xlim(0, max(series1.max(), series2.max()) * 1.36)
    ax2.set_xlabel("年均种植面积 / 亩")
    ax2.set_title("作物类型年均种植规模\n（情形一 / 情形二）", fontsize=8.4, pad=8)
    fb.panel(ax2, "b", x=-0.40)

    ax3 = fig.add_subplot(grid[0, 2])
    df1 = pd.DataFrame(sales1)
    df2 = pd.DataFrame(sales2)
    total1 = float(df1["sales_jin"].sum()) / 1e4
    total2 = float(df2["sales_jin"].sum()) / 1e4
    surplus1 = float(df1["surplus_jin"].sum()) / 1e4
    surplus2 = float(df2["surplus_jin"].sum()) / 1e4
    for index, (name, total, surplus) in enumerate((("情形一", total1, surplus1), ("情形二", total2, surplus2))):
        pos = 1.0 - index
        ax3.hlines(pos, 0, total, color=fb.CLR["blue"], lw=2.4, alpha=0.9)
        ax3.scatter([total], [pos], s=34, color=fb.CLR["blue"], zorder=3)
        ax3.text(total + 4, pos + 0.07, f"正常销售 {total:.1f} 万斤", va="center", fontsize=6.8)
        ax3.hlines(pos - 0.28, 0, surplus, color=fb.CLR["red"], lw=2.0, alpha=0.9)
        ax3.scatter([surplus], [pos - 0.28], s=28, color=fb.CLR["red"], zorder=3)
        ax3.text(surplus + 4, pos - 0.34, f"超产 {surplus:.2f} 万斤", va="center", fontsize=6.8, color=fb.CLR["red"])
    ax3.set_ylim(-0.55, 1.55)
    ax3.set_yticks([1.0, 0.0])
    ax3.set_yticklabels(["情形一", "情形二"], fontsize=7.4)
    ax3.set_xlim(0, max(total1, total2) * 1.5)
    ax3.set_xlabel("销售量 / 万斤")
    ax3.set_title("正常销售量与超产量", fontsize=8.6, pad=8)
    fb.panel(ax3, "c")
    fb.save(fig, 1, "fig06_q1_profit")


def figure7():
    fb.style()
    plan1, sales1, metrics = load("case1")
    plan2, sales2, _ = load("case2")
    frame1 = pd.DataFrame(sales1)
    frame2 = pd.DataFrame(sales2)
    fig = plt.figure(figsize=(183 / 25.4, 80 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.15, 1.0], wspace=0.34)

    ax = fig.add_subplot(grid[0, 0])
    base1 = np.array([metrics["case1"]["profit_by_year"][str(year)] for year in YEARS]) / 1e4
    base2 = np.array([metrics["case2"]["profit_by_year"][str(year)] for year in YEARS]) / 1e4
    reference = float(np.mean(base1))
    ax.plot(YEARS, base1 - reference, color=fb.CLR["blue"], lw=1.8, marker="o", ms=3.2, label="情形一 超产滞销")
    ax.plot(YEARS, base2 - reference, color=fb.CLR["orange"], lw=1.8, marker="s", ms=3.0, label="情形二 超产降价 50%")
    ax.axhline(0.0, color=fb.CLR["grey"], lw=0.9, linestyle="--")
    ax.set_xlabel("年份")
    ax.set_ylabel("年度净利润相对七年均值的偏差 / 万元")
    ax.set_title("两情形年度收益的波动形态", fontsize=8.6, pad=8)
    ax.legend(fontsize=6.4, loc="upper right")
    fb.panel(ax, "a")

    ax2 = fig.add_subplot(grid[0, 1])
    first1 = frame1.drop_duplicates(subset=["crop_id"]).sort_values("sales_jin", ascending=False).head(14)
    labels = first1["crop"].astype(str).tolist()
    ypos = np.arange(len(labels))[::-1]
    part1 = first1["sales_jin"].to_numpy() / 1e4
    mapping = frame2.set_index("crop_id")["sales_jin"].to_dict()
    part2 = np.array([float(mapping.get(crop_id, 0.0)) / 1e4 for crop_id in first1["crop_id"]])
    ax2.hlines(ypos + 0.14, 0, part1, color=fb.CLR["blue"], linewidth=2.6, alpha=0.85)
    ax2.hlines(ypos - 0.14, 0, part2, color=fb.CLR["orange"], linewidth=2.6, alpha=0.85)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(labels, fontsize=6.6)
    ax2.set_xlabel("正常销售量 / 万斤")
    ax2.set_title("主要作物的两情形销售量对照", fontsize=8.6, pad=6)
    ax2.legend(handles=[Line2D([0], [0], color=fb.CLR["blue"], lw=2.6, label="情形一"),
                        Line2D([0], [0], color=fb.CLR["orange"], lw=2.6, label="情形二")],
               fontsize=6.6, loc="lower right")
    fb.panel(ax2, "b", x=-0.30)

    ax3 = fig.add_subplot(grid[0, 2])
    kinds = ["平旱地", "梯田", "山坡地", "水浇地", "普通大棚", "智慧大棚"]
    for key, frame, color, marker, label in (("情形一", pd.DataFrame(plan1), fb.CLR["blue"], "o", "情形一"),
                                             ("情形二", pd.DataFrame(plan2), fb.CLR["orange"], "s", "情形二")):
        values = []
        for kind in kinds:
            sub = frame[frame["kind"] == kind]
            area_total = sum(
                row["area"]
                for row in pd.read_csv(BASE / "data" / "派生" / "plots.csv").to_dict("records")
                if row["plot_type"] == kind
            )
            values.append(float(sub["area"].sum()) / area_total / len(YEARS))
        ax3.plot(range(len(kinds)), values, color=color, lw=1.8, marker=marker, ms=3.2, label=label)
    ax3.set_xticks(range(len(kinds)))
    ax3.set_xticklabels(kinds, fontsize=6.8, rotation=22, ha="right")
    ax3.set_ylabel("年均复种指数")
    ax3.set_title("各耕地类型的年均利用强度", fontsize=8.6, pad=6)
    ax3.legend(fontsize=6.8, loc="upper left")
    fb.panel(ax3, "c")
    fb.save(fig, 1, "fig07_q1_compare")


def figure8():
    fb.style()
    plan1, sales1, metrics = load("case1")
    plots = pd.read_csv(BASE / "data" / "派生" / "plots.csv")
    frame = pd.DataFrame(plan1)
    kinds = ["平旱地", "梯田", "山坡地", "水浇地", "普通大棚", "智慧大棚"]
    area_map = dict(zip(plots["plot"], plots["area"]))
    kind_map = dict(zip(plots["plot"], plots["plot_type"]))
    frame["kind"] = frame["plot"].map(kind_map)
    frame["intensity"] = frame["area"] / frame["plot"].map(area_map)
    table = frame.pivot_table(index="kind", columns="year", values="intensity", aggfunc="mean").reindex(kinds)
    table = table.reindex(columns=YEARS).fillna(0.0)

    fig = plt.figure(figsize=(183 / 25.4, 96 / 25.4))
    ax = fig.add_subplot(111, projection="3d")
    xs = np.arange(len(YEARS))
    ys = np.arange(len(kinds))
    for row_index, kind in enumerate(kinds):
        for column_index, year in enumerate(YEARS):
            value = float(table.loc[kind, year])
            if value <= 1e-6:
                continue
            ax.plot([column_index, column_index], [row_index, row_index], [0, value],
                    color=fb.CLR["blue"], lw=1.4, alpha=0.55)
            ax.scatter([column_index], [row_index], [value], s=16, color=fb.CLR["orange"], depthshade=False)
    xx, yy = np.meshgrid(xs, ys)
    zz = np.array([[float(table.loc[kinds[j], YEARS[i]]) for i in range(len(YEARS))] for j in range(len(kinds))])
    ax.plot_surface(xx, yy, zz, cmap="Blues", alpha=0.42, linewidth=0, antialiased=True, vmin=0, vmax=1,
                    rstride=1, cstride=1)
    ax.set_xticks(xs[::2])
    ax.set_xticklabels([str(YEARS[i]) for i in range(0, len(YEARS), 2)], fontsize=6.8)
    ax.set_yticks(ys)
    ax.set_yticklabels(kinds, fontsize=6.8)
    ax.set_zlim(0, 1.05)
    ax.set_zlabel("平均季次利用强度", fontsize=7.2, labelpad=0)
    ax.set_xlabel("年份", fontsize=7.2, labelpad=4)
    ax.set_ylabel("耕地类型", fontsize=7.2, labelpad=4)
    ax.view_init(elev=26, azim=-58)
    ax.set_title("情形一下各类耕地平均季次利用强度的三维曲面", fontsize=8.8, pad=0)
    ax.legend(handles=[Line2D([0], [0], color=fb.CLR["orange"], marker="o", lw=0, ms=4, label="年度实际强度"),
                       Line2D([0], [0], color=fb.CLR["blue"], lw=2.4, label="趋势曲面")],
              fontsize=6.6, loc="upper left", bbox_to_anchor=(-0.08, 1.0))
    fig.subplots_adjust(left=0.02, right=0.86, top=1.0, bottom=0.04)
    fb.save(fig, 1, "fig08_q1_spacetime")


if __name__ == "__main__":
    figure6()
    figure7()
    figure8()
    print("fig06, fig07, fig08 done")
