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
    """chart_family: dendrogram - hierarchical grouping of the objects."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    leaves = ["A1", "A2", "B1", "B2", "C1", "C2"]
    merges = [(0, 1, 0.28), (3, 4, 0.34), (2, 6, 0.52), (5, 7, 0.61), (8, 9, 0.88)]

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    centre = {index: float(index) for index in range(len(leaves))}
    height = {index: 0.0 for index in range(len(leaves))}
    for index, (left, right, level) in enumerate(merges, start=len(leaves)):
        x0, x1 = centre[left], centre[right]
        ax.plot([x0, x0, x1, x1], [height[left], level, level, height[right]], color=PALETTE["slate_dark"], lw=1.1)
        centre[index] = 0.5 * (x0 + x1)
        height[index] = level

    ax.set_xticks(range(len(leaves)))
    ax.set_xticklabels(leaves)
    ax.set_ylabel("Cluster distance")
    ax.spines["top"].set_visible(False)
    save_py_nature_figure(fig, Path(output_dir) / "cluster_dendrogram", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
