from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (  # noqa: E402
    PALETTE,
    make_pareto_plot,

    apply_py_nature_style,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt  # noqa: E402

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: pareto - trade-off between two conflicting objectives."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    points = np.array([
        [68, 52], [71, 48], [73, 44], [75, 41], [78, 38], [80, 36],
        [69, 58], [72, 54], [77, 45], [81, 42], [84, 39], [74, 56],
    ])
    frontier = np.array([False, True, True, True, True, True,
                         False, False, False, False, False, False])

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    make_pareto_plot(ax, points, frontier)
    ax.set_xlabel("Robustness index")
    ax.set_ylabel("Total cost (10k CNY)")
    save_py_nature_figure(fig, Path(output_dir) / "optimization_pareto", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
