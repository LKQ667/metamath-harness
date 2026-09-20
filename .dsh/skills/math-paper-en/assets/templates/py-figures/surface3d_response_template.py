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
    """chart_family: surface3d - response surface over two decision variables."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    x = np.linspace(0.0, 1.0, 90)
    y = np.linspace(0.0, 1.0, 90)
    grid_x, grid_y = np.meshgrid(x, y)
    surface = 0.35 + 0.9 * grid_x * np.exp(-1.6 * grid_y) + 0.25 * np.sin(3.1 * grid_x)

    fig = plt.figure(figsize=(3.6, 3.0))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(grid_x, grid_y, surface, cmap="viridis", linewidth=0, antialiased=True, alpha=0.95)
    ax.contour(grid_x, grid_y, surface, zdir="z", offset=surface.min() - 0.15, levels=8, cmap="viridis", linewidths=0.5)
    ax.set_xlabel("Allocation ratio", fontsize=6, labelpad=-4)
    ax.set_ylabel("Retention time", fontsize=6, labelpad=-4)
    ax.set_zlabel("Yield", fontsize=6, labelpad=-6)
    ax.tick_params(labelsize=6, pad=-1)
    ax.view_init(elev=26, azim=-58)
    save_py_nature_figure(fig, Path(output_dir) / "surface3d_response", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
