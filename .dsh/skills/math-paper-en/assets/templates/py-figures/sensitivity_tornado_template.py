from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (  # noqa: E402
    PALETTE,
    make_tornado_plot,

    apply_py_nature_style,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt  # noqa: E402

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: tornado - parameter sensitivity ranking."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    labels = ["Demand growth", "Unit cost", "Storage limit", "Service level", "Lead time"]
    impacts = [0.18, -0.14, 0.11, 0.07, -0.05]

    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    make_tornado_plot(ax, labels, impacts)
    ax.set_title("Sensitivity of the total cost", pad=6)
    save_py_nature_figure(fig, Path(output_dir) / "sensitivity_tornado", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
