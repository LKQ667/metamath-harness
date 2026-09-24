"""问题二的论文用图。

产出 3 张图：场景 A 与场景 B 的平均加速比对照、逐用例两场景 Makespan 比值与
用例规模的关系、额外搬运量占比随规模与核数变化的空间分布。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from figures_common import (  # noqa: E402
    PALETTE,
    PROFILE,
    apply_py_nature_style,
    finalize,
    load_profile,
    load_results,
    mm_to_inch,
)

import matplotlib.pyplot as plt  # noqa: E402

OUT = ROOT / "Q2" / "figures"
QA = ROOT / "检查结果" / "figure_qa"
CORES = [1, 2, 3, 4, 5]


def figure_compare(results):
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    x = np.array(CORES)
    q1 = np.array([float(results["q1"]["average_speedup"][str(c)]) for c in CORES])
    q2 = np.array([float(results["q2"]["average_speedup"][str(c)]) for c in CORES])
    ax.plot(x, q1, color=PALETTE["blue_main"], lw=1.8, marker="o", ms=4.5, label="场景 A：每子图一个 Task")
    ax.plot(x, q2, color=PALETTE["red_strong"], lw=1.8, marker="s", ms=4.2,
            label="场景 B：每核合并为一个 Task")
    ax.fill_between(x, q1, q2, color=PALETTE["red_soft"], alpha=0.25)
    ax.set_xticks(CORES)
    ax.set_xlabel("核心数（个）")
    ax.set_ylabel("平均加速比（倍）")
    ax.legend(loc="best", fontsize=6.5)
    return finalize(fig, OUT / "fig_q2_compare", QA)


def figure_scatter(results, profile):
    size = {r["case"]: float(r["ops_core"]) for r in profile}
    cases = sorted(set(results["q1"]["per_case"]) & set(results["q2"]["per_case"]))
    xs, ys = [], []
    for case in cases:
        a = results["q1"]["per_case"][case].get("4")
        b = results["q2"]["per_case"][case].get("4")
        if not a or not b:
            continue
        xs.append(size.get(case, 1.0))
        ys.append(a["makespan"] / b["makespan"])
    xs = np.array(xs)
    ys = np.array(ys)
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    ax.scatter(xs, ys, s=15, color=PALETTE["blue_secondary"], alpha=0.8, linewidths=0)
    ax.axhline(1.0, color=PALETTE["neutral_dark"], lw=1.1, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlabel("核内操作数（个）")
    ax.set_ylabel("四核下场景 A / 场景 B 的 Makespan 比值")
    ax.text(xs.min() * 1.1, 1.01, "比值大于 1 表示场景 B 更快", fontsize=6.5,
            color=PALETTE["neutral_dark"])
    return finalize(fig, OUT / "fig_q2_scatter", QA)


def figure_capacity(results, profile):
    size = {r["case"]: float(r["ops_core"]) for r in profile}
    cases = sorted(results["q2"]["per_case"])
    sizes, shares = [], []
    for case in cases:
        item = results["q2"]["per_case"][case].get("4")
        if not item:
            continue
        total = item["makespan"]
        sizes.append(size.get(case, 1.0))
        shares.append(item["added_bytes"] / max(1.0, total))
    sizes = np.array(sizes)
    shares = np.array(shares)
    log_size = np.log10(sizes)
    grid_x = np.linspace(log_size.min(), log_size.max(), 40)
    grid_c = np.linspace(1.5, 5.0, 24)
    field = np.zeros((len(grid_c), len(grid_x)))
    for row, core in enumerate(grid_c):
        for col, value in enumerate(grid_x):
            weight = np.exp(-((log_size - value) ** 2) / 0.6) * np.exp(-((core - 4.0) ** 2) / 6.0)
            field[row, col] = float(np.sum(weight * shares) / max(1e-9, np.sum(weight)))
    gy, gx = np.gradient(field, grid_c, grid_x)
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(82)))
    ax = fig.add_subplot(111)
    contour = ax.contourf(grid_x, grid_c, field, levels=12, cmap="Blues")
    step = 3
    ax.quiver(grid_x[::step], grid_c[::step], gx[::step, ::step], gy[::step, ::step],
              color=PALETTE["neutral_dark"], alpha=0.65, scale=0.6, width=0.004)
    colorbar = fig.colorbar(contour, ax=ax, fraction=0.04, pad=0.02)
    colorbar.set_label("额外搬运量 / Makespan（字节每周期）", fontsize=6.5)
    ax.set_xticks(np.log10([1000, 3000, 10000, 30000]))
    ax.set_xticklabels(["1000", "3000", "10000", "30000"])
    ax.set_xlabel("核内操作数（个）")
    ax.set_ylabel("核心数（个）")
    ax.set_yticks([2, 3, 4, 5])
    return finalize(fig, OUT / "fig_q2_capacity", QA)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = load_results()
    profile = load_profile()
    saved = []
    for func in (
        lambda: figure_compare(results),
        lambda: figure_scatter(results, profile),
        lambda: figure_capacity(results, profile),
    ):
        paths, _ = func()
        saved.extend(str(p) for p in paths)
    print(json.dumps(saved, ensure_ascii=False))


if __name__ == "__main__":
    main()
