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
    """chart_family: radar_profile - multi-criteria profile of a few schemes."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    criteria = ["Cost", "Speed", "Robustness", "Equity", "Feasibility"]
    schemes = {"Scheme A": [0.72, 0.81, 0.66, 0.58, 0.88], "Scheme B": [0.64, 0.69, 0.86, 0.79, 0.72]}
    angles = np.linspace(0.0, 2.0 * np.pi, len(criteria), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(3.2, 3.0), subplot_kw={"projection": "polar"})
    for (name, values), color in zip(schemes.items(), [PALETTE["blue_main"], PALETTE["orange_main"]]):
        closed = values + values[:1]
        ax.plot(angles, closed, lw=1.6, color=color, label=name)
        ax.fill(angles, closed, color=color, alpha=0.18)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(criteria, fontsize=6)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8"], fontsize=6)
    ax.set_ylim(0.0, 1.0)
    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.12), fontsize=6)
    save_py_nature_figure(fig, Path(output_dir) / "profile_radar", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
