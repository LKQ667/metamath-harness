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
    make_network_topology,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: resilience_curve - topology plus a failure curve."""
    apply_py_nature_style(font_size=6.5, profile=PROFILE)
    fig, axes = compose_multi_panel("single_row_with_legend", ["topology", "curve"])
    ax1, ax2 = axes["panel_1"], axes["panel_2"]

    make_network_topology(ax1)
    add_panel_label(ax1, "a")

    x = np.linspace(0.0, 0.9, 40)
    ax2.plot(x, 0.95 - 0.80 * x ** 1.3, color=PALETTE["neutral_mid"], lw=1.8, label="Random failure")
    ax2.plot(x, 0.96 - 0.62 * x ** 1.05, color=PALETTE["blue_main"], lw=1.8, label="Targeted protection")
    ax2.axvline(0.42, color=PALETTE["red_strong"], ls="--", lw=1.0)
    ax2.set_xlabel("Removed node fraction")
    ax2.set_ylabel("Largest component")
    add_panel_label(ax2, "b")

    handles, labels = ax2.get_legend_handles_labels()
    axes["legend"].legend(handles, labels, loc="center", fontsize=6.5)
    save_py_nature_figure(fig, Path(output_dir) / "network_resilience", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
