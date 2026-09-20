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
    """chart_family: timeline_gantt - schedule drawn with line segments and markers."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    tasks = ["Site survey", "Model calibration", "Field trial", "Policy roll-out", "Review"]
    starts = [0, 3, 7, 12, 18]
    spans = [3, 4, 5, 6, 3]
    owners = [0, 1, 0, 2, 1]
    colors = [PALETTE["blue_main"], PALETTE["orange_main"], PALETTE["teal_main"]]

    fig, ax = plt.subplots(figsize=(3.8, 2.4))
    for index, (name, start, span, owner) in enumerate(zip(tasks, starts, spans, owners)):
        y = len(tasks) - index
        ax.hlines(y, start, start + span, color=colors[owner], lw=6.0, alpha=0.85)
        ax.plot([start, start + span], [y, y], marker="|", ms=7, color=PALETTE["black"], lw=0)
        ax.text(start + span + 0.4, y, f"{span} w", va="center", fontsize=6)

    ax.set_yticks([len(tasks) - i for i in range(len(tasks))])
    ax.set_yticklabels(tasks)
    ax.set_xlabel("Week")
    ax.set_xlim(-0.5, max(np.array(starts) + np.array(spans)) + 2.5)
    ax.spines["left"].set_visible(False)
    save_py_nature_figure(fig, Path(output_dir) / "timeline_gantt_segments", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
