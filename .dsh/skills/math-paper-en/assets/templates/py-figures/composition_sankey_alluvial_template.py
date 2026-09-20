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
    """chart_family: sankey_alluvial - composition and the flows between stages."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    left = [("Residential", 0.42), ("Industrial", 0.33), ("Agriculture", 0.25)]
    right = [("Reuse", 0.38), ("Discharge", 0.62)]
    flows = np.array([[0.20, 0.22], [0.12, 0.21], [0.06, 0.19]])
    colors = [PALETTE["blue_main"], PALETTE["orange_main"], PALETTE["teal_main"]]

    fig, ax = plt.subplots(figsize=(3.8, 2.6))
    curve = np.linspace(0.0, 1.0, 120)
    smooth = curve * curve * (3.0 - 2.0 * curve)
    left_top, right_top = 1.0, 1.0
    right_cursor = 1.0
    for row, (name, weight) in enumerate(left):
        left_top -= weight
        ax.fill_between(curve, left_top, left_top + weight, color=PALETTE["neutral_light"], alpha=0.6, linewidth=0)
        ax.text(-0.03, left_top + weight / 2, name, ha="right", va="center", fontsize=6)
    for column, (name, weight) in enumerate(right):
        node_bottom = right_top - weight
        ax.fill_between([0.97, 1.03], node_bottom, right_top, color=PALETTE["neutral_light"], alpha=0.6, linewidth=0)
        ax.text(1.04, node_bottom + weight / 2, name, ha="left", va="center", fontsize=6)
        right_top = node_bottom

    left_cursor, right_cursor = 1.0, 1.0
    for row, (name, weight) in enumerate(left):
        cursor = left_cursor
        for column in range(len(right)):
            value = flows[row, column]
            y0 = np.linspace(cursor, cursor - value, smooth.size)
            y1 = np.linspace(right_cursor - flows[:row, column].sum() - value, right_cursor - flows[:row, column].sum(), smooth.size)
            ax.fill_between(curve, y0, y1, color=colors[row], alpha=0.35, linewidth=0)
            cursor -= value
        left_cursor -= weight
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(0.0, 1.02)
    ax.axis("off")
    save_py_nature_figure(fig, Path(output_dir) / "composition_sankey_alluvial", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
