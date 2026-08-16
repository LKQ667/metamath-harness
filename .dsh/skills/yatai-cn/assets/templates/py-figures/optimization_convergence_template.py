from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import PALETTE, apply_py_nature_style, make_trend_with_band, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    x = np.arange(1, 41)
    rng = np.random.default_rng(42)
    ga = np.vstack([95 - 12 * np.log1p(x) + rng.normal(0, 0.8, len(x)) for _ in range(5)])
    pso = np.vstack([93 - 11 * np.log1p(x) + rng.normal(0, 0.7, len(x)) for _ in range(5)])
    hybrid = np.vstack([96 - 13 * np.log1p(x) + rng.normal(0, 0.6, len(x)) for _ in range(5)])
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    make_trend_with_band(ax, x, [ga, pso, hybrid], ["GA", "PSO", "Hybrid"], [PALETTE["neutral_mid"], PALETTE["teal_main"], PALETTE["blue_main"]], "迭代次数", "目标值")
    ax.legend(loc="upper right")
    save_py_nature_figure(fig, Path(output_dir) / "optimization_convergence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
