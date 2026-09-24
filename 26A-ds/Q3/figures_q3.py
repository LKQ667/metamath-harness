"""问题三的论文用图。

产出 3 张图：只读 Cache 相对无 L2 基线的平均加速比、命中率与加速比的关系、
两种配置下额外搬运量的对照曲线。
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
    load_results,
    mm_to_inch,
)

import matplotlib.pyplot as plt  # noqa: E402

OUT = ROOT / "Q3" / "figures"
QA = ROOT / "检查结果" / "figure_qa"
CORES = [1, 2, 3, 4, 5]


def figure_gain(results):
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    x = np.array(CORES)
    gain = [float(results["q3"]["average_cache_gain"].get(str(c), 1.0)) for c in CORES]
    hit = [float(results["q3"]["average_cache_hit_rate"].get(str(c), 0.0)) for c in CORES]
    ax.plot(x, gain, color=PALETTE["green_strong"], lw=1.8, marker="o", ms=4.5,
            label="只读 Cache 相对无 L2 的加速比")
    ax.axhline(1.0, color=PALETTE["neutral_dark"], lw=1.1, linestyle="--")
    ax.set_xticks(CORES)
    ax.set_xlabel("核心数（个）")
    ax.set_ylabel("平均加速比（倍）")
    twin = ax.twinx()
    twin.plot(x, np.array(hit) * 100.0, color=PALETTE["orange_main"], lw=1.5, marker="^", ms=4.0,
              linestyle="-.", label="平均 Cache 命中率")
    twin.set_ylabel("平均命中率（%）")
    lines = ax.get_lines()[:2] + twin.get_lines()[:1]
    ax.legend(lines, [line.get_label() for line in lines], loc="best", fontsize=6.5)
    return finalize(fig, OUT / "fig_q3_cache_gain", QA)


def figure_hit(results):
    xs, ys = [], []
    for case, entry in results["q3"]["per_case"].items():
        item = entry.get("4")
        if not item:
            continue
        accesses = item.get("cache_accesses", 0)
        if not accesses:
            continue
        xs.append(item["cache_hits"] / accesses)
        ys.append(item.get("cache_gain", 1.0))
    xs = np.array(xs)
    ys = np.array(ys)
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    ax.scatter(xs * 100.0, ys, s=15, color=PALETTE["teal_main"], alpha=0.8, linewidths=0,
               label="四核配置下的 100 个用例")
    if len(xs) > 3:
        order = np.argsort(xs)
        coefficient = np.polyfit(xs[order], ys[order], 1)
        line_x = np.linspace(xs.min(), xs.max(), 50)
        ax.plot(line_x * 100.0, np.polyval(coefficient, line_x), color=PALETTE["red_strong"],
                lw=1.5, label="最小二乘趋势线")
    ax.axhline(1.0, color=PALETTE["neutral_dark"], lw=1.1, linestyle="--")
    ax.set_xlabel("Cache 命中率（%）")
    ax.set_ylabel("只读 Cache 相对无 L2 的加速比（倍）")
    ax.legend(loc="best", fontsize=6.5)
    return finalize(fig, OUT / "fig_q3_hit", QA)


def figure_traffic(results):
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    x = np.array(CORES)
    nol2 = []
    withl2 = []
    for cores in CORES:
        a, b = [], []
        for entry in results["q3"]["per_case"].values():
            item = entry.get(str(cores))
            if not item:
                continue
            a.append(item.get("nol2_added_bytes", 0))
            b.append(item.get("l2_added_bytes", 0))
        nol2.append(float(np.mean(a)) if a else 0.0)
        withl2.append(float(np.mean(b)) if b else 0.0)
    ax.plot(x, np.array(nol2) / 1024.0, color=PALETTE["blue_main"], lw=1.8, marker="o", ms=4.5,
            label="无 L2 配置")
    ax.plot(x, np.array(withl2) / 1024.0, color=PALETTE["green_strong"], lw=1.8, marker="s", ms=4.2,
            label="只读 Cache 配置")
    ax.set_xticks(CORES)
    ax.set_xlabel("核心数（个）")
    ax.set_ylabel("逐用例平均额外搬运量（KB）")
    ax.legend(loc="best", fontsize=6.5)
    return finalize(fig, OUT / "fig_q3_traffic", QA)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = load_results()
    saved = []
    for func in (
        lambda: figure_gain(results),
        lambda: figure_hit(results),
        lambda: figure_traffic(results),
    ):
        paths, _ = func()
        saved.extend(str(p) for p in paths)
    print(json.dumps(saved, ensure_ascii=False))


if __name__ == "__main__":
    main()
