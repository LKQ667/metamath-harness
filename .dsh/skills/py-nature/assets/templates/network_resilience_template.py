from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from py_nature_core import PALETTE, add_panel_label, apply_py_nature_style, compose_multi_panel, make_network_topology, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    fig, axes = compose_multi_panel("single_row_with_legend", ["topology", "curve"])
    ax1 = axes["panel_1"]
    ax2 = axes["panel_2"]

    make_network_topology(ax1)
    add_panel_label(ax1, "a")

    x = np.linspace(0, 0.9, 40)
    y1 = 0.95 - 0.8 * x**1.3
    y2 = 0.96 - 0.62 * x**1.05
    ax2.plot(x, y1, color=PALETTE["neutral_mid"], lw=2, label="随机失效")
    ax2.plot(x, y2, color=PALETTE["blue_main"], lw=2, label="稳健策略")
    ax2.axvline(0.42, color=PALETTE["red_strong"], linestyle="--", linewidth=1)
    ax2.set_xlabel("失效节点比例")
    ax2.set_ylabel("最大连通分量")
    add_panel_label(ax2, "b")

    handles, labels = ax2.get_legend_handles_labels()
    axes["legend"].legend(handles, labels, loc="center")
    save_py_nature_figure(fig, Path(output_dir) / "network_resilience")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
