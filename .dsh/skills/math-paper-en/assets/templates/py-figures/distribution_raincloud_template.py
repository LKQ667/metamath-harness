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
    """chart_family: raincloud - distribution shape + spread + raw points."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    rng = np.random.default_rng(19)
    groups = ["Baseline", "Policy A", "Policy B", "Policy C"]
    data = [rng.normal(0.58 + 0.04 * i, 0.07 + 0.01 * i, 120) for i in range(4)]

    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    for index, values in enumerate(data, start=1):
        parts = ax.violinplot([values], positions=[index + 0.16], widths=0.7, showextrema=False, showmedians=False)
        for body in parts["bodies"]:
            vertices = body.get_paths()[0].vertices
            vertices[:, 0] = np.minimum(vertices[:, 0], vertices[:, 0].mean())
            body.set_facecolor(PALETTE["blue_secondary"])
            body.set_edgecolor("none")
            body.set_alpha(0.75)
        box = ax.boxplot([values], positions=[index - 0.06], widths=0.10, vert=True, patch_artist=True,
                         showfliers=False, medianprops=dict(color="white", lw=1.0))
        for patch in box["boxes"]:
            patch.set_facecolor(PALETTE["slate_dark"])
            patch.set_edgecolor(PALETTE["slate_dark"])
        jitter = rng.normal(index - 0.30, 0.035, values.size)
        ax.scatter(jitter, values, s=2.4, color=PALETTE["neutral_mid"], alpha=0.55, linewidths=0)

    ax.set_xticks(range(1, len(groups) + 1))
    ax.set_xticklabels(groups)
    ax.set_ylabel("Service level")
    save_py_nature_figure(fig, Path(output_dir) / "distribution_raincloud", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
