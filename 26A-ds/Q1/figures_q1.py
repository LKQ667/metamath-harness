"""问题一的论文用图。

产出 5 张图：1～5 核平均加速比、逐用例加速比与并行宽度的关系、加速比与额外搬运量
的权衡、代表性用例的四核时间线、估算完工时间与实测 Makespan 的一致性。
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
    add_panel_label,
    apply_py_nature_style,
    compose_multi_panel,
    finalize,
    load_profile,
    load_results,
    mm_to_inch,
)

import matplotlib.pyplot as plt  # noqa: E402

OUT = ROOT / "Q1" / "figures"
QA = ROOT / "检查结果" / "figure_qa"
EVAL = ROOT / "results" / "evaluation"
CORES = [1, 2, 3, 4, 5]


def _speedup_curve(results, problem_key):
    block = results[problem_key]["average_speedup"]
    return np.array([float(block[str(c)]) for c in CORES])


def figure_speedup(results):
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    x = np.array(CORES)
    y = _speedup_curve(results, "q1")
    ax.plot(x, y, color=PALETTE["blue_main"], lw=1.8, marker="o", ms=4.5, label="问题一（场景 A）")
    y2 = _speedup_curve(results, "q2")
    ax.plot(x, y2, color=PALETTE["red_strong"], lw=1.6, marker="s", ms=4.0,
            linestyle="--", label="问题二（场景 B）")
    ax.plot(x, x, color=PALETTE["neutral_mid"], lw=1.1, linestyle=":", label="线性理想加速比")
    ax.set_xticks(CORES)
    ax.set_xlabel("核心数（个）")
    ax.set_ylabel("平均加速比（倍）")
    ax.legend(loc="best", fontsize=6.5)
    ax.set_ylim(0.8, 5.4)
    return finalize(fig, OUT / "fig_q1_speedup", QA)


def figure_case_scatter(results, profile):
    width = {r["case"]: float(r["parallel_width"]) for r in profile}
    cases = sorted(results["q1"]["per_case"])
    xs = np.array([width.get(c, 1.0) for c in cases])
    ys = np.array([results["q1"]["per_case"][c]["4"]["speedup"] for c in cases])
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(82)))
    ax = fig.add_subplot(111)
    ax.scatter(xs, ys, s=15, color=PALETTE["blue_main"], alpha=0.75, linewidths=0, label="100 个测试用例")
    order = np.argsort(xs)
    window = max(3, len(xs) // 12)
    smooth_x, smooth_y = [], []
    for index in range(len(xs)):
        lo = max(0, index - window)
        hi = min(len(xs), index + window + 1)
        smooth_x.append(xs[order][index])
        smooth_y.append(float(np.median(ys[order][lo:hi])))
    ax.plot(smooth_x, smooth_y, color=PALETTE["orange_main"], lw=1.6, label="加速比中位数滑动曲线")
    ax.axhline(4.0, color=PALETTE["neutral_mid"], lw=1.0, linestyle=":")
    ax.text(xs.min() * 1.05, 4.06, "四核线性上限", fontsize=6.5, color=PALETTE["neutral_dark"])
    ax.set_xscale("log")
    ax.set_xlabel("并行宽度（总工作量 / 关键路径，倍）")
    ax.set_ylabel("四核加速比（倍）")
    ax.legend(loc="best", fontsize=6.5)
    return finalize(fig, OUT / "fig_q1_case_scatter", QA)


def figure_pareto(results):
    cases = sorted(results["q1"]["per_case"])
    gains = []
    traffic = []
    for case in cases:
        entry = results["q1"]["per_case"][case]
        item = entry.get("4")
        if not item:
            continue
        single = entry["singlecore_makespan"]
        gains.append(item["speedup"])
        traffic.append(item["added_bytes"] / max(1.0, single))
    gains = np.array(gains)
    traffic = np.array(traffic)
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(82)))
    ax = fig.add_subplot(111)
    frontier = np.ones(len(gains), dtype=bool)
    order = np.argsort(-gains)
    best = -np.inf
    for index in order:
        if traffic[index] > best:
            best = traffic[index]
        else:
            frontier[index] = False
    ax.scatter(traffic[~frontier], gains[~frontier], s=14, color=PALETTE["neutral_mid"],
               alpha=0.7, linewidths=0, label="一般用例")
    ax.scatter(traffic[frontier], gains[frontier], s=20, color=PALETTE["red_strong"],
               linewidths=0, label="加速比—搬运量前沿")
    ax.set_xlabel("额外搬运量 / 单核工作量（无量纲）")
    ax.set_ylabel("四核加速比（倍）")
    ax.legend(loc="best", fontsize=6.5)
    return finalize(fig, OUT / "fig_q1_pareto", QA)


def figure_timeline(case="case_002", cores=4):
    path = EVAL / f"{case}_p1_n{cores}_res.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig, axes = compose_multi_panel(
        "matrix_2x2",
        panel_specs=["p1", "p2", "p3", "p4"],
        width_mm=150,
        height_mm=96,
    )
    timeline = {entry["core_id"]: entry for entry in data["per_core_timeline"]}
    makespan = data["makespan"]
    for core in range(cores):
        ax = axes[f"panel_{core + 1}"]
        spans = timeline.get(core, {}).get("subgraphs", [])
        for index, span in enumerate(spans):
            start = span["start"] / makespan * 100.0
            end = span["end"] / makespan * 100.0
            ax.hlines(0, start, end, color=PALETTE["blue_main"], linewidth=4.0, alpha=0.9)
            ax.scatter([start, end], [0, 0], s=6, color=PALETTE["blue_main"], zorder=3)
        ax.set_xlim(0, 100)
        ax.set_ylim(-0.6, 0.6)
        ax.set_yticks([])
        ax.set_xlabel("相对 Makespan 的时间位置（%）")
        ax.set_title(f"核心 {core}", fontsize=7.0, pad=2)
        add_panel_label(ax, f"({'abcd'[core]})", x=-0.10, y=1.10)
    return finalize(fig, OUT / "fig_q1_timeline", QA)


def figure_estimator(results, profile):
    """估算完工时间与实测 Makespan 的一致性检查。"""
    cases = sorted(results["q1"]["per_case"])
    measured = []
    estimated = []
    for case in cases:
        item = results["q1"]["per_case"][case].get("4")
        if not item or "estimate" not in item:
            continue
        measured.append(item["makespan"])
        estimated.append(item["estimate"])
    measured = np.array(measured, dtype=float)
    estimated = np.array(estimated, dtype=float)
    ratio = estimated / measured
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    ax.scatter(measured, ratio, s=15, color=PALETTE["teal_main"], alpha=0.8, linewidths=0)
    ax.axhline(1.0, color=PALETTE["neutral_dark"], lw=1.1, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlabel("实测 Makespan（周期）")
    ax.set_ylabel("估算值 / 实测值（倍）")
    median = float(np.median(ratio))
    ax.text(measured.min() * 1.1, median + 0.03, f"中位数 {median:.2f}", fontsize=6.5,
            color=PALETTE["neutral_dark"])
    return finalize(fig, OUT / "fig_q1_estimator", QA)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = load_results()
    profile = load_profile()
    saved = []
    for func in (
        lambda: figure_speedup(results),
        lambda: figure_case_scatter(results, profile),
        lambda: figure_pareto(results),
        lambda: figure_timeline(),
        lambda: figure_estimator(results, profile),
    ):
        paths, _ = func()
        saved.extend(str(p) for p in paths)
    print(json.dumps(saved, ensure_ascii=False))


if __name__ == "__main__":
    main()
