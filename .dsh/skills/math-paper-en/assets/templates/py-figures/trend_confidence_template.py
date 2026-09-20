from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (  # noqa: E402
    PALETTE,
    make_trend_with_band,

    apply_py_nature_style,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt  # noqa: E402

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: line_band - evolution of a metric with an uncertainty band."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    x = np.arange(1, 25)
    rng = np.random.default_rng(7)
    baseline = np.vstack([0.52 + 0.006 * x + rng.normal(0, 0.012, x.size) for _ in range(4)])
    robust = np.vstack([0.55 + 0.011 * x + rng.normal(0, 0.012, x.size) for _ in range(4)])
    adaptive = np.vstack([0.58 + 0.015 * x + rng.normal(0, 0.012, x.size) for _ in range(4)])

    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    make_trend_with_band(
        ax,
        x,
        [baseline, robust, adaptive],
        ["Baseline policy", "Robust policy", "Adaptive policy"],
        [PALETTE["neutral_mid"], PALETTE["teal_main"], PALETTE["blue_main"]],
        "Iteration",
        "Objective value",
    )
    ax.legend(loc="lower right", fontsize=6)
    save_py_nature_figure(fig, Path(output_dir) / "trend_confidence", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
