from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (
    PALETTE,
    add_panel_label,
    apply_py_nature_style,
    compose_multi_panel,
    make_network_curvature_panel,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: network_curvature_multiscale - geometry plus scale curves."""
    apply_py_nature_style(font_size=6.5, profile=PROFILE)
    fig, axes = compose_multi_panel("network_hero_curve_stack", ["network", "gap", "community"])
    hero = axes["hero"]
    support_1 = axes["support_1"]
    support_2 = axes["support_2"]

    collection = make_network_curvature_panel(hero)
    add_panel_label(hero, "a")
    bar = fig.colorbar(collection, ax=hero, fraction=0.046, pad=0.04)
    bar.set_label("Dynamic curvature", fontsize=6)

    t = np.linspace(0.1, 2.0, 10)
    gap = np.array([0.08, 0.11, 0.17, 0.29, 0.35, 0.31, 0.24, 0.20, 0.18, 0.17])
    support_1.plot(t, gap, color=PALETTE["curvature_high"], lw=1.9, marker="o", ms=3.6)
    support_1.axvline(0.9, color=PALETTE["neutral_mid"], ls="--", lw=1.0)
    support_1.annotate("characteristic scale", xy=(0.9, 0.35), xytext=(1.02, 0.39),
                       fontsize=6.2, color=PALETTE["neutral_dark"])
    support_1.set_xlabel("Diffusion time")
    support_1.set_ylabel("Curvature gap")
    add_panel_label(support_1, "b")

    levels = np.array([2, 4, 8, 16, 32])
    modularity = np.array([0.36, 0.45, 0.58, 0.62, 0.56])
    support_2.plot(levels, modularity, color=PALETTE["blue_main"], lw=1.9, marker="s", ms=3.8)
    support_2.fill_between(levels, modularity - 0.03, modularity + 0.03, color=PALETTE["blue_secondary"], alpha=0.16)
    support_2.set_xlabel("Community scale")
    support_2.set_ylabel("Geometric modularity")
    add_panel_label(support_2, "c")

    save_py_nature_figure(fig, Path(output_dir) / "network_curvature_multiscale", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
