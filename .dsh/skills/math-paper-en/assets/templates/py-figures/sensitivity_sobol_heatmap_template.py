from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (  # noqa: E402
    PALETTE,
    make_heatmap,

    apply_py_nature_style,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt  # noqa: E402

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: heatmap - two-way interaction sensitivity (at most one per paper)."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    rng = np.random.default_rng(11)
    matrix = np.abs(rng.normal(0.12, 0.04, size=(5, 6))).round(3)

    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    make_heatmap(ax, matrix, [f"P{j}" for j in range(1, 7)], [f"Q{i}" for i in range(1, 6)], cmap="magma")
    ax.set_title("Second-order Sobol indices", pad=6)
    save_py_nature_figure(fig, Path(output_dir) / "sensitivity_sobol_heatmap", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
