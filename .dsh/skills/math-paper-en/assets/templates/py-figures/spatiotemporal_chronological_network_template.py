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
    make_chronological_network_panel,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: chronological_network - space, network and summary in one figure."""
    apply_py_nature_style(font_size=6.5, profile=PROFILE)
    fig, axes = compose_multi_panel("map_network_summary", ["map", "network", "summary"])
    ax_map, ax_network, ax_summary = axes["map"], axes["network"], axes["summary"]

    grid = np.array([
        [0.18, 0.25, 0.33, 0.40],
        [0.24, 0.42, 0.56, 0.61],
        [0.21, 0.38, 0.71, 0.84],
        [0.15, 0.24, 0.52, 0.73],
    ])
    image = ax_map.imshow(grid, cmap="viridis", vmin=0.1, vmax=0.9)
    ax_map.set_xticks(range(4))
    ax_map.set_xticklabels(["x1", "x2", "x3", "x4"])
    ax_map.set_yticks(range(4))
    ax_map.set_yticklabels(["t1", "t2", "t3", "t4"])
    ax_map.set_xlabel("Spatial grid")
    ax_map.set_ylabel("Time layer")
    add_panel_label(ax_map, "a")
    bar = fig.colorbar(image, ax=ax_map, fraction=0.046, pad=0.04)
    bar.set_label("Recurrence strength", fontsize=6)

    make_chronological_network_panel(ax_network)
    ax_network.set_title("Chronnet", fontsize=7, pad=4)
    add_panel_label(ax_network, "b")

    x = np.arange(1, 9)
    recurrence = np.array([0.22, 0.29, 0.35, 0.49, 0.53, 0.58, 0.64, 0.69])
    delay = np.array([0.11, 0.14, 0.16, 0.20, 0.18, 0.17, 0.14, 0.12])
    ax_summary.plot(x, recurrence, color=PALETTE["spatial_focus"], lw=1.7, marker="o", ms=3.2, label="Strong-tie share")
    ax_summary.plot(x, delay, color=PALETTE["orange_main"], lw=1.5, marker="s", ms=3.0, label="Time lag")
    ax_summary.set_xlabel("Time window")
    ax_summary.set_ylabel("Indicator")
    ax_summary.legend(loc="upper left", fontsize=6)
    add_panel_label(ax_summary, "c")

    save_py_nature_figure(fig, Path(output_dir) / "spatiotemporal_chronological_network", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
