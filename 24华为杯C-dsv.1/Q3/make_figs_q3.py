"""问题三入文图：相关性结构、协同矩阵、三问对比与约束合规。"""

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
Q2 = BASE / "Q2"
Q3 = BASE / "Q3"
YEARS = list(range(2024, 2031))
FAMILIES = ["粮食", "粮食（豆类）", "蔬菜", "蔬菜（豆类）", "食用菌"]


def metrics3():
    return fb.load_json(Q3 / "q3_metrics.json")


def metrics2():
    return fb.load_json(Q2 / "q2_metrics.json")


def metrics1():
    return fb.load_json(Q1 / "q1_metrics.json")


def figure12():
    fb.style()
    data = metrics3()
    corr = np.array(data["correlation"])
    names = ["粮食", "豆类", "蔬菜", "食用菌"]
    fig = plt.figure(figsize=(183 / 25.4, 82 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.15], wspace=0.40)

    ax = fig.add_subplot(grid[0, 0])
    image = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(len(names)):
        for j in range(len(names)):
            ax.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", fontsize=6.8,
                    color="white" if abs(corr[i, j]) > 0.55 else fb.CLR["ink"])
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, fontsize=7.0)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=7.0)
    ax.set_title("作物组间相关系数矩阵", fontsize=8.4, pad=8)
    bar = fig.colorbar(image, ax=ax, shrink=0.72, pad=0.03, fraction=0.046)
    bar.ax.tick_params(labelsize=6.2)
    fb.panel(ax, "a", x=-0.34)

    ax2 = fig.add_subplot(grid[0, 1])
    shocks = np.array(data["group_shocks"]) * 100
    palette = [fb.CLR["blue"], fb.CLR["green"], fb.CLR["orange"], fb.CLR["teal"]]
    for index, name in enumerate(names):
        ax2.plot(range(len(shocks)), shocks[:, index], color=palette[index],
                 lw=1.6, marker="o", ms=3.0, label=name)
    ax2.axhline(0, color=fb.CLR["grey"], lw=0.9, linestyle="--")
    ax2.set_xticks(range(len(shocks)))
    ax2.set_xticklabels([f"S{i+1}" for i in range(len(shocks))], fontsize=6.6)
    ax2.set_xlabel("情景编号")
    ax2.set_ylabel("组冲击强度 / %")
    ax2.set_title("八情景下的四个组冲击", fontsize=8.4, pad=8)
    ax2.legend(fontsize=6.0, ncol=2, loc="lower left", handletextpad=0.35, columnspacing=0.8)
    fb.panel(ax2, "b", x=-0.22)

    ax3 = fig.add_subplot(grid[0, 2])
    elasticity = data["elasticity"]
    groups = ["蔬菜", "食用菌", "豆类", "粮食"]
    values = [float(elasticity[name]) for name in groups]
    ypos = np.arange(len(groups))[::-1]
    ax3.hlines(ypos, 0, values, color=fb.CLR["teal"], lw=2.6, alpha=0.85)
    ax3.scatter(values, ypos, s=30, color=fb.CLR["blue"], zorder=3)
    for index, value in enumerate(values):
        ax3.text(value + 0.012, ypos[index], f"{value:.2f}", va="center", fontsize=6.8)
    ax3.set_yticks(ypos)
    ax3.set_yticklabels(groups, fontsize=7.0)
    ax3.set_xlim(0, max(values) * 1.35)
    ax3.set_xlabel("量价弹性系数")
    ax3.set_title("各组销量对价格的抑制强度", fontsize=8.4, pad=8)
    fb.panel(ax3, "c", x=-0.24)
    fb.save(fig, 3, "fig12_q3_corr")


def figure13():
    fb.style()
    data = metrics3()
    scan = []
    for risk in (0.0, 1.0, 3.0):
        pass
    frontier = data["frontier"]
    fig = plt.figure(figsize=(183 / 25.4, 84 / 25.4))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.3, 1.0], wspace=0.32)

    ax = fig.add_subplot(grid[0, 0], projection="3d")
    means = np.array([row["mean_profit"] for row in frontier]) / 1e4
    stds = np.array([row["std_profit"] for row in frontier]) / 1e4
    cvars = np.array([row["cvar"] for row in frontier]) / 1e4
    risks = [row["risk"] for row in frontier]
    ax.plot(stds, cvars, means, color=fb.CLR["blue"], lw=1.8, marker="o", ms=5)
    for index in range(len(risks)):
        ax.text(stds[index], cvars[index], means[index] + 40, f"λ={risks[index]:g}", fontsize=6.6, color=fb.CLR["dark"])
    ax.set_xlabel("利润标准差 / 万元", fontsize=7.2, labelpad=4)
    ax.set_ylabel("尾部收益 CVaR / 万元", fontsize=7.2, labelpad=4)
    ax.set_zlabel("利润均值 / 万元", fontsize=7.2, labelpad=0)
    ax.view_init(elev=22, azim=-56)
    ax.set_title("收益-风险-尾部三元协同曲面", fontsize=8.8, pad=0)
    fig.subplots_adjust(left=0.02, right=0.90, top=1.0, bottom=0.06)
    fb.panel(ax, "a", x=-0.04)

    ax2 = fig.add_subplot(grid[0, 1])
    labels = ["问题二 中性", "问题二 稳健", "问题三 中性", "问题三 稳健"]
    q2 = metrics2()
    values = [
        q2["plans"]["neutral"]["evaluation"]["mean"] / 1e4,
        q2["plans"]["robust"]["evaluation"]["mean"] / 1e4,
        data["plans"]["neutral"]["evaluation"]["mean"] / 1e4,
        data["plans"]["robust"]["evaluation"]["mean"] / 1e4,
    ]
    colors = [fb.CLR["blue2"], fb.CLR["blue"], fb.CLR["orange"], fb.CLR["red"]]
    ypos = np.arange(len(labels))[::-1]
    for index, value in enumerate(values):
        ax2.hlines(ypos[index], 0, value, color=colors[index], lw=3.0, alpha=0.85)
        ax2.scatter([value], [ypos[index]], s=28, color=colors[index], zorder=3)
        ax2.text(value * 0.02, ypos[index] + 0.16, f"{value:,.0f} 万元", fontsize=6.4, va="bottom")
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(labels, fontsize=6.8)
    ax2.set_xlim(0, max(values) * 1.3)
    ax2.set_xlabel("情景平均七年利润 / 万元")
    ax2.set_title("两类相关性口径下的方案收益", fontsize=8.6, pad=8)
    fb.panel(ax2, "b", x=-0.28)
    fb.save(fig, 3, "fig13_q3_synergy")


def figure14():
    fb.style()
    m1 = metrics1()
    m2 = metrics2()
    m3 = metrics3()
    fig = plt.figure(figsize=(183 / 25.4, 84 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.1, 1.05], wspace=0.36)

    ax = fig.add_subplot(grid[0, 0])
    series = [
        ("问题一 情形一", np.array([m1["case1"]["profit_by_year"][str(y)] for y in YEARS]) / 1e4, fb.CLR["blue"]),
        ("问题二 中性", np.array([m2["plans"]["neutral"]["profit_by_year"].get(str(y), 0.0) for y in YEARS]) / 1e4, fb.CLR["teal"]),
        ("问题三 中性", np.array([m3["plans"]["neutral"]["profit_by_year"].get(str(y), 0.0) for y in YEARS]) / 1e4, fb.CLR["orange"]),
    ]
    for name, values, color in series:
        ax.plot(YEARS, values, color=color, lw=1.7, marker="o", ms=3.0, label=name)
    ax.set_xlabel("年份")
    ax.set_ylabel("年度利润 / 万元")
    ax.set_title("三套方案的逐年利润轨迹", fontsize=8.6, pad=8)
    ax.legend(fontsize=6.2, loc="lower left")
    fb.panel(ax, "a")

    ax2 = fig.add_subplot(grid[0, 1])
    entries = [
        ("情景均值", [m1["case1"]["profit_value_yuan"] / 1e4, m2["frontier"][0]["mean_profit"] / 1e4,
                     m3["frontier"][0]["mean_profit"] / 1e4]),
        ("尾部收益", [m1["case1"]["profit_value_yuan"] / 1e4, m2["frontier"][0]["cvar"] / 1e4,
                     m3["frontier"][0]["cvar"] / 1e4]),
        ("利润标准差", [0.0, m2["frontier"][0]["std_profit"] / 1e4, m3["frontier"][0]["std_profit"] / 1e4]),
    ]
    ypos = np.arange(len(entries))[::-1]
    offsets = np.linspace(-0.22, 0.22, 3)
    colors3 = [fb.CLR["blue"], fb.CLR["teal"], fb.CLR["orange"]]
    for group_index, (name, values) in enumerate(entries):
        for index, value in enumerate(values):
            y = ypos[group_index] + offsets[index]
            ax2.plot([0, value], [y, y], color=colors3[index], lw=1.7)
            ax2.scatter([value], [y], s=22, color=colors3[index], zorder=3)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels([item[0] for item in entries], fontsize=7.0)
    ax2.set_xlabel("金额 / 万元")
    ax2.set_title("三套方案的收益与风险指标", fontsize=8.6, pad=8)
    ax2.legend(handles=[Line2D([0], [0], color=colors3[i], lw=2.6, label=name)
                        for i, name in enumerate(["问题一", "问题二", "问题三"])],
               fontsize=6.2, loc="lower right")
    fb.panel(ax2, "b", x=-0.22)

    ax3 = fig.add_subplot(grid[0, 2])
    crops = pd.read_csv(BASE / "data" / "派生" / "crops.csv").set_index("crop_id")["family"].to_dict()
    for key, frame, color, label in (
        ("问题一", pd.DataFrame(fb.load_json(Q1 / "q1_plan_case1.json")), fb.CLR["blue"], "问题一"),
        ("问题二", pd.DataFrame(fb.load_json(Q2 / "q2_plan_neutral.json")), fb.CLR["teal"], "问题二"),
        ("问题三", pd.DataFrame(fb.load_json(Q3 / "q3_plan_neutral.json")), fb.CLR["orange"], "问题三"),
    ):
        frame["family"] = frame["crop_id"].map(crops)
        share = frame.groupby("family")["area"].sum()
        share = share / share.sum() * 100
        ax3.plot(range(len(FAMILIES)), [float(share.get(name, 0.0)) for name in FAMILIES],
                 color=color, lw=1.7, marker="o", ms=3.2, label=label)
    ax3.set_xticks(range(len(FAMILIES)))
    ax3.set_xticklabels(FAMILIES, fontsize=6.6, rotation=20, ha="right")
    ax3.set_ylabel("种植面积份额 / %")
    ax3.set_title("三套方案的作物结构差异", fontsize=8.6, pad=8)
    ax3.legend(fontsize=6.2, loc="upper right")
    fb.panel(ax3, "c")
    fb.save(fig, 3, "fig14_q3_compare")


def figure16():
    fb.style()
    data = metrics3()
    plan = pd.DataFrame(fb.load_json(Q3 / "q3_plan_neutral.json"))
    plots = pd.read_csv(BASE / "data" / "派生" / "plots.csv")
    area_map = dict(zip(plots["plot"], plots["area"]))
    plan["intensity"] = plan["area"] / plan["plot"].map(area_map)
    kinds = ["平旱地", "梯田", "山坡地", "水浇地", "普通大棚", "智慧大棚"]

    fig = plt.figure(figsize=(183 / 25.4, 84 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.1, 1.0, 1.0], wspace=0.38)

    ax = fig.add_subplot(grid[0, 0])
    group = plan.groupby(["kind", "year"])["intensity"].mean().unstack(fill_value=0.0).reindex(kinds)
    offset = np.linspace(-0.3, 0.3, len(kinds))
    for index, kind in enumerate(kinds):
        values = [float(group.loc[kind, y]) if y in group.columns else 0.0 for y in YEARS]
        ax.plot(np.array(YEARS) + offset[index], values, color=list(fb.CLR.values())[index], lw=1.5,
                marker="o", ms=2.6, label=kind)
    ax.set_xticks(YEARS)
    ax.set_xticklabels(YEARS, fontsize=6.4, rotation=30)
    ax.set_ylabel("平均季次利用强度")
    ax.set_xlabel("年份")
    ax.set_title("问题三方案的逐年利用强度", fontsize=8.6, pad=8)
    ax.legend(fontsize=5.6, ncol=2, loc="lower right")
    fb.panel(ax, "a", x=-0.20)

    ax2 = fig.add_subplot(grid[0, 1])
    checks = ["重茬违规", "豆类窗口违规", "容量越界", "低于最小面积"]
    q2 = metrics2()
    q3 = data
    values2 = [q2["plans"]["neutral"]["summary"]["audit"].get(key, 0) for key in
               ("repeat_count", "bean_window_fail", "over_capacity", "undersize_count")]
    values3 = [q3["plans"]["neutral"]["summary"]["audit"].get(key, 0) for key in
               ("repeat_count", "bean_window_fail", "over_capacity", "undersize_count")]
    ypos = np.arange(len(checks))[::-1]
    for index, name in enumerate(checks):
        ax2.scatter([values2[index]], [ypos[index] + 0.16], s=60, color=fb.CLR["teal"], marker="o", zorder=3)
        ax2.scatter([values3[index]], [ypos[index] - 0.16], s=60, color=fb.CLR["orange"], marker="s", zorder=3)
        ax2.text(0.4, ypos[index] + 0.16, f"{values2[index]}", fontsize=6.6, va="center", color=fb.CLR["teal"])
        ax2.text(0.4, ypos[index] - 0.16, f"{values3[index]}", fontsize=6.6, va="center", color=fb.CLR["orange"])
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(checks, fontsize=7.0)
    ax2.set_xlim(-0.2, 1.6)
    ax2.set_xticks([0, 1])
    ax2.set_xlabel("违规记录数")
    ax2.set_title("结构约束合规回检", fontsize=8.6, pad=8)
    ax2.legend(handles=[Line2D([0], [0], color=fb.CLR["teal"], marker="o", lw=0, ms=6, label="问题二方案"),
                        Line2D([0], [0], color=fb.CLR["orange"], marker="s", lw=0, ms=6, label="问题三方案")],
               fontsize=6.2, loc="center right")
    fb.panel(ax2, "b", x=-0.26)

    ax3 = fig.add_subplot(grid[0, 2])
    frontier = data["frontier"]
    risks = [row["risk"] for row in frontier]
    gains = [row["mean_profit_no_elastic"] - row["mean_profit"] for row in frontier]
    cvars = [row["cvar"] for row in frontier]
    ax3.hlines(risks, cvars, [row["mean_profit"] for row in frontier], color=fb.CLR["grey2"], lw=2.0)
    for index, risk in enumerate(risks):
        ax3.scatter([cvars[index]], [risk], s=30, color=fb.CLR["red"], marker="s", zorder=3)
        ax3.scatter([frontier[index]["mean_profit"]], [risk], s=30, color=fb.CLR["blue"], zorder=3)
    ax3.set_yticks(risks)
    ax3.set_yticklabels([f"λ={risk:g}" for risk in risks], fontsize=7.0)
    ax3.set_xlabel("七年利润 / 元")
    ax3.set_title("问题三的均值-尾部区间", fontsize=8.6, pad=8)
    fb.panel(ax3, "c", x=-0.22)
    fb.save(fig, 3, "fig16_q3_audit")


if __name__ == "__main__":
    figure12()
    figure13()
    figure14()
    figure16()
    print("fig12, fig13, fig14, fig16 done")
