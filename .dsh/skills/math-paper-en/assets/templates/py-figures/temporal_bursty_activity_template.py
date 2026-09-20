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
    make_bursty_activity,
    make_inter_event_ccdf,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: bursty_activity - event process plus its inter-event distribution."""
    apply_py_nature_style(font_size=6.5, profile=PROFILE)
    fig, axes = compose_multi_panel("single_row_with_legend", ["timeline", "distribution"])
    ax1, ax2 = axes["panel_1"], axes["panel_2"]

    spikes = make_bursty_activity(ax1)
    for point in spikes[:3]:
        ax1.axvline(point, color=PALETTE["gold_main"], lw=0.8, alpha=0.85)
    add_panel_label(ax1, "a")

    make_inter_event_ccdf(ax2)
    ax2.legend(loc="upper right", fontsize=6)
    add_panel_label(ax2, "b")

    axes["legend"].set_axis_off()
    save_py_nature_figure(fig, Path(output_dir) / "temporal_bursty_activity", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
