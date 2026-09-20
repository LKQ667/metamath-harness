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
    """chart_family: slope_bump - rank changes between planning stages."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    stages = ["Current", "After policy", "Target"]
    schemes = {"Scheme A": [5, 2, 1], "Scheme B": [1, 4, 3], "Scheme C": [3, 1, 4],
               "Scheme D": [2, 5, 2], "Scheme E": [4, 3, 5]}
    colors = [PALETTE["blue_main"], PALETTE["orange_main"], PALETTE["teal_main"],
              PALETTE["violet_main"], PALETTE["neutral_mid"]]

    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    for (name, ranks), color in zip(schemes.items(), colors):
        ax.plot(range(len(stages)), ranks, marker="o", ms=4, lw=1.6, color=color)
        ax.text(-0.08, ranks[0], name, ha="right", va="center", fontsize=6, color=color)
        ax.text(len(stages) - 1 + 0.08, ranks[-1], f"{ranks[-1]}", ha="left", va="center", fontsize=6, color=color)

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(stages)
    ax.invert_yaxis()
    ax.set_ylabel("Rank (1 = best)")
    ax.set_yticks(range(1, 6))
    ax.set_xlim(-1.1, len(stages) - 1 + 0.5)
    save_py_nature_figure(fig, Path(output_dir) / "ranking_slope_bump", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
