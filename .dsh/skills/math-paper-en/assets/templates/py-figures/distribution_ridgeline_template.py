from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import PALETTE, apply_py_nature_style, save_py_nature_figure
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: ridgeline - stacked densities of many groups."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    rng = np.random.default_rng(23)
    labels = ["2019", "2020", "2021", "2022", "2023", "2024"]
    grid = np.linspace(-4.0, 4.0, 400)

    fig, ax = plt.subplots(figsize=(3.6, 2.9))
    colors = [PALETTE["neutral_mid"], PALETTE["teal_main"], PALETTE["blue_main"],
              PALETTE["orange_main"], PALETTE["red_strong"], PALETTE["violet_main"]]
    for offset, (label, color) in enumerate(zip(labels, colors)):
        centre = 0.25 * offset
        samples = rng.normal(centre, 1.0, 400)
        density = ax.fill_between
        bins = np.histogram(samples, bins=40, range=(-4.0, 5.0), density=True)
        heights = bins[0] * 0.55
        centres = 0.5 * (bins[1][1:] + bins[1][:-1])
        ax.fill_between(centres, offset, offset + heights, color=color, alpha=0.85, linewidth=0)
        ax.plot(centres, offset + heights, color=PALETTE["black"], lw=0.5)
        ax.text(-4.0, offset + 0.06, label, fontsize=6, ha="left", va="bottom")

    ax.set_yticks([])
    ax.set_xlabel("Standardised deviation from the annual mean")
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-4.0, 5.0)
    save_py_nature_figure(fig, Path(output_dir) / "distribution_ridgeline", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
