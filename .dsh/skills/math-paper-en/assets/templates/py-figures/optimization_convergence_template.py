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
    """chart_family: convergence_line - optimizer convergence on a log axis."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    x = np.arange(1, 61)
    rng = np.random.default_rng(5)
    runs = []
    for floor in (1.5e-3, 6.0e-4, 2.0e-4):
        runs.append(np.vstack([floor + 0.9 * np.exp(-0.09 * x) * np.exp(rng.normal(0, 0.12, x.size)) for _ in range(3)]))

    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    make_trend_with_band(
        ax,
        x,
        runs,
        ["GA baseline", "PSO", "Hybrid GA-PSO"],
        [PALETTE["neutral_mid"], PALETTE["violet_main"], PALETTE["blue_main"]],
        "Generation",
        "Best objective (log)",
    )
    ax.set_yscale("log")
    ax.legend(loc="upper right", fontsize=6)
    save_py_nature_figure(fig, Path(output_dir) / "optimization_convergence", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
