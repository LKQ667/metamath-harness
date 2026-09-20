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
    """chart_family: bubble_scatter - three variables in one view."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    rng = np.random.default_rng(31)
    x = rng.uniform(10, 90, 45)
    y = 0.35 * x + rng.normal(0, 6.0, x.size)
    size = rng.uniform(20, 320, x.size)
    value = 0.4 * x + rng.normal(0, 12.0, x.size)

    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    scatter = ax.scatter(x, y, s=size, c=value, cmap="viridis", alpha=0.78, linewidths=0.3, edgecolors="white")
    ax.set_xlabel("Population density (person/km2)")
    ax.set_ylabel("Per-capita demand (m3)")
    bar = fig.colorbar(scatter, ax=ax, fraction=0.045, pad=0.02)
    bar.set_label("GDP per capita", fontsize=6)
    bar.ax.tick_params(labelsize=6)
    save_py_nature_figure(fig, Path(output_dir) / "relation_bubble_scatter", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
