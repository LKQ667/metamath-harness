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
    make_tornado_plot,
    make_network_topology,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: hero_support - one hero panel plus supporting evidence panels."""
    apply_py_nature_style(font_size=6.5, profile=PROFILE)
    fig, axes = compose_multi_panel("hero_top_support_bottom")

    make_network_topology(axes["hero"])
    axes["hero"].set_title("Multi-layer supply network and critical nodes", pad=6)
    add_panel_label(axes["hero"], "a")

    x = np.arange(1, 13)
    axes["support_1"].plot(x, 0.62 + 0.03 * x + 0.02 * np.sin(x / 1.5),
                           color=PALETTE["blue_main"], lw=1.8)
    axes["support_1"].set_title("Convergence", fontsize=7)
    axes["support_1"].set_xlabel("Iteration")
    add_panel_label(axes["support_1"], "b")

    make_tornado_plot(axes["support_2"], ["Demand", "Delay", "Capacity", "Threshold"], [0.14, -0.11, 0.08, -0.05])
    axes["support_2"].set_title("Sensitivity", fontsize=7)
    add_panel_label(axes["support_2"], "c")

    axes["support_3"].scatter([0.70, 0.75, 0.80, 0.84], [58, 52, 47, 42], s=26, color=PALETTE["orange_main"])
    axes["support_3"].plot([0.70, 0.84], [58, 42], color=PALETTE["orange_main"], lw=1.6)
    axes["support_3"].set_title("Trade-off", fontsize=7)
    axes["support_3"].set_xlabel("Robustness")
    axes["support_3"].set_ylabel("Cost")
    add_panel_label(axes["support_3"], "d")

    axes["legend"].axis("off")
    save_py_nature_figure(fig, Path(output_dir) / "multi_panel_hero_support", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
