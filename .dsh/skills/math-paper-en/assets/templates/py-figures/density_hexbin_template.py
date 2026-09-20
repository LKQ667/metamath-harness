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
    """chart_family: hexbin_density - dense bivariate distribution without overplotting."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    rng = np.random.default_rng(37)
    x = np.concatenate([rng.normal(0.0, 0.9, 4000), rng.normal(3.4, 0.7, 1500)])
    y = 0.7 * x + rng.normal(0.0, 1.1, x.size)

    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    mesh = ax.hexbin(x, y, gridsize=34, cmap="cividis", mincnt=1, linewidths=0.1)
    ax.set_xlabel("Standardised rainfall anomaly")
    ax.set_ylabel("Standardised runoff anomaly")
    bar = fig.colorbar(mesh, ax=ax, fraction=0.045, pad=0.02)
    bar.set_label("Count", fontsize=6)
    bar.ax.tick_params(labelsize=6)
    save_py_nature_figure(fig, Path(output_dir) / "density_hexbin", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
