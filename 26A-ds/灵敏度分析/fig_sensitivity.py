"""灵敏度分析的论文用图。

产出 2 张图：切分粒度与单核兜底阈值对平均加速比的影响曲线，以及两参数共同
作用下加速比的响应面。
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
    mm_to_inch,
)

import matplotlib.pyplot as plt  # noqa: E402

OUT = ROOT / "灵敏度分析" / "figures"
QA = ROOT / "检查结果" / "figure_qa"
SOURCE = ROOT / "灵敏度分析" / "sensitivity_results.json"


def load_sensitivity():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def figure_parameters(data):
    blocks = sorted(data["level_band"], key=float)
    margins = sorted(data["safety_margin"], key=float)
    block_speed = [data["summary"]["level_band"][b]["average_speedup"] for b in blocks]
    block_low = [data["summary"]["level_band"][b]["min_speedup"] for b in blocks]
    margin_speed = [data["summary"]["safety_margin"][m]["average_speedup"] for m in margins]
    margin_low = [data["summary"]["safety_margin"][m]["min_speedup"] for m in margins]

    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(80)))
    ax = fig.add_subplot(111)
    x = np.arange(len(blocks))
    ax.plot(x, block_speed, color=PALETTE["blue_main"], lw=1.8, marker="o", ms=4.5,
            label="切分粒度：平均加速比")
    ax.fill_between(x, block_low, block_speed, color=PALETTE["blue_secondary"], alpha=0.18)
    ax.plot(x, block_low, color=PALETTE["blue_secondary"], lw=1.2, linestyle="--",
            label="切分粒度：最低加速比")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b}" for b in blocks])
    ax.set_xlabel("分层切分的层带宽度（层）")
    ax.set_ylabel("四核加速比（倍）")

    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    ax2.set_xticks(np.linspace(0, len(blocks) - 1, len(margins)))
    ax2.set_xticklabels([f"{float(m):.2f}" for m in margins])
    ax2.set_xlabel("单核兜底阈值")
    ax.plot(np.linspace(0, len(blocks) - 1, len(margins)), margin_speed,
            color=PALETTE["red_strong"], lw=1.6, marker="s", ms=4.0, linestyle="-.",
            label="兜底阈值：平均加速比")
    ax.plot(np.linspace(0, len(blocks) - 1, len(margins)), margin_low,
            color=PALETTE["red_soft"], lw=1.2, marker="^", ms=3.6, linestyle=":",
            label="兜底阈值：最低加速比")
    ax.legend(loc="best", fontsize=6.2, ncol=2)
    return finalize(fig, OUT / "fig_sensitivity_parameters", QA)


def figure_response(data):
    blocks = sorted(data["level_band"], key=float)
    margins = sorted(data["safety_margin"], key=float)
    grid = np.zeros((len(margins), len(blocks)))
    for i, margin in enumerate(margins):
        for j, block in enumerate(blocks):
            values = []
            for case in data["cases"]:
                a = data["level_band"][block].get(case)
                b = data["safety_margin"][margin].get(case)
                if a and b:
                    values.append(min(a["speedup"], b["speedup"]))
            grid[i, j] = float(np.mean(values)) if values else 1.0
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(120), mm_to_inch(82)))
    ax = fig.add_subplot(111)
    xs = np.arange(len(blocks))
    ys = np.arange(len(margins))
    mesh_x, mesh_y = np.meshgrid(xs, ys)
    ax.scatter(mesh_x.ravel(), mesh_y.ravel(), c=grid.ravel(), s=90, cmap="Blues",
               edgecolors=PALETTE["neutral_dark"], linewidths=0.5, zorder=3)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{b}" for b in blocks])
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{float(m):.2f}" for m in margins])
    ax.set_xlabel("分层切分的层带宽度（层）")
    ax.set_ylabel("单核兜底阈值")
    ax.grid(True, color=PALETTE["neutral_light"], linewidth=0.6)
    best = np.unravel_index(int(np.argmax(grid)), grid.shape)
    ax.scatter([xs[best[1]]], [ys[best[0]]], s=210, facecolors="none",
               edgecolors=PALETTE["red_strong"], linewidths=1.6, zorder=4)
    ax.text(xs[best[1]] + 0.12, ys[best[0]] + 0.10,
            f"最优组合 {grid[best]:.2f}", fontsize=6.5, color=PALETTE["red_strong"])
    colorbar = fig.colorbar(
        plt.cm.ScalarMappable(cmap="Blues", norm=plt.Normalize(grid.min(), grid.max())), ax=ax
    )
    colorbar.set_label("平均加速比（倍）", fontsize=6.5)
    return finalize(fig, OUT / "fig_sensitivity_response", QA)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_sensitivity()
    saved = []
    for func in (lambda: figure_parameters(data), lambda: figure_response(data)):
        paths, _ = func()
        saved.extend(str(p) for p in paths)
    print(json.dumps(saved, ensure_ascii=False))


if __name__ == "__main__":
    main()
