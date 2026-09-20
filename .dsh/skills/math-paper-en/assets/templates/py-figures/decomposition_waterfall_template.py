from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import PALETTE, apply_py_nature_style, save_py_nature_figure
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: waterfall - how each component moves the total (segment form)."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    labels = ["Baseline", "Demand", "Unit cost", "Lead time", "Subsidy", "Final"]
    deltas = [0.0, 12.4, -6.1, -3.5, 8.2, 0.0]
    start = 100.0
    running = start
    lefts, bottoms = [], []
    for delta in deltas:
        lefts.append(running if delta >= 0 else running + delta)
        bottoms.append(abs(delta))
        running += delta

    fig, ax = plt.subplots(figsize=(3.8, 2.6))
    xs = np.arange(len(labels))
    for index, (x, bottom, height, delta) in enumerate(zip(xs, lefts, bottoms, deltas)):
        if index in (0, len(labels) - 1):
            color = PALETTE["slate_dark"]
        else:
            color = PALETTE["green_strong"] if delta > 0 else PALETTE["red_strong"]
        ax.hlines(bottom, x - 0.28, x + 0.28, color=color, lw=7.0, alpha=0.9)
        if index < len(labels) - 1:
            next_bottom = bottoms[index + 1]
            ax.hlines(bottom if index else bottom + height, x, x + 1, color=PALETTE["neutral_mid"], lw=0.7, ls=":")
        if index not in (0, len(labels) - 1):
            ax.text(x, max(bottom + height, bottom + 1.2), f"{delta:+.1f}", ha="center", fontsize=6)

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=18, ha="right")
    ax.set_ylabel("Total cost (10k CNY)")
    ax.set_ylim(90, 125)
    save_py_nature_figure(fig, Path(output_dir) / "decomposition_waterfall", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
