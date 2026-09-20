from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (  # noqa: E402
    PALETTE,
    make_lollipop_plot,

    apply_py_nature_style,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt  # noqa: E402

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: lollipop - ranked point comparison without zero baseline."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    labels = ["City A", "City B", "City C", "City D", "City E", "City F"]
    values = np.array([0.82, 0.77, 0.71, 0.64, 0.55, 0.42])

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    make_lollipop_plot(ax, labels, values)
    ax.set_xlabel("Composite resilience score")
    save_py_nature_figure(fig, Path(output_dir) / "stats_interval_lollipop", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
