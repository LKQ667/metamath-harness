from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from py_nature_core import apply_py_nature_style, make_heatmap, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    matrix = np.array([
        [0.31, 0.08, 0.12, 0.15],
        [0.18, 0.26, 0.09, 0.11],
        [0.07, 0.12, 0.28, 0.17],
        [0.13, 0.11, 0.14, 0.25],
    ])
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    make_heatmap(ax, matrix, ["成本", "时效", "风险", "碳排"], ["参数 A", "参数 B", "参数 C", "参数 D"], cmap="magma")
    save_py_nature_figure(fig, Path(output_dir) / "sensitivity_sobol_heatmap")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
