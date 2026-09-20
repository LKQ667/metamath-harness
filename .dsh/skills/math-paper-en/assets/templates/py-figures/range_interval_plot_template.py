from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (  # noqa: E402
    PALETTE,
    make_interval_plot,

    apply_py_nature_style,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt  # noqa: E402

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: interval_plot - estimates with uncertainty intervals."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    labels = ["Case 1", "Case 2", "Case 3", "Case 4", "Case 5"]
    centers = np.array([12.4, 9.8, 15.1, 11.2, 13.6])
    lows = centers - np.array([1.2, 0.8, 1.7, 1.0, 1.4])
    highs = centers + np.array([1.5, 1.1, 2.0, 1.3, 1.6])

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    make_interval_plot(ax, labels, centers, lows, highs)
    ax.set_ylabel("Peak load (MW)")
    save_py_nature_figure(fig, Path(output_dir) / "range_interval_plot", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
