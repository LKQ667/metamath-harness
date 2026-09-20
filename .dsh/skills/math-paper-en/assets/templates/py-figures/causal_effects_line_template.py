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
    """chart_family: multi_line - several methods compared along one axis."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    x = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    rng = np.random.default_rng(3)
    curves = []
    for offset in (0.00, 0.03, 0.06):
        curves.append(np.vstack([offset + 0.42 * x + rng.normal(0, 0.008, x.size) for _ in range(3)]))

    fig, ax = plt.subplots(figsize=(3.5, 2.4))
    make_trend_with_band(
        ax,
        x,
        curves,
        ["Uncontrolled", "Fixed threshold", "Adaptive threshold"],
        [PALETTE["neutral_mid"], PALETTE["orange_main"], PALETTE["blue_main"]],
        "Treatment intensity",
        "Average effect",
    )
    ax.legend(loc="upper left", fontsize=6)
    save_py_nature_figure(fig, Path(output_dir) / "causal_effects_line", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
