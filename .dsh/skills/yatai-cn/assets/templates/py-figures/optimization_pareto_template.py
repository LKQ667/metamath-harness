from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import apply_py_nature_style, make_pareto_plot, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    points = np.array([
        [68, 52], [71, 48], [73, 44], [75, 41], [78, 38],
        [69, 58], [72, 54], [77, 45], [81, 42], [84, 39],
    ])
    frontier = [False, True, True, True, True, False, False, False, True, True]
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    make_pareto_plot(ax, points, frontier)
    save_py_nature_figure(fig, Path(output_dir) / "optimization_pareto")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
