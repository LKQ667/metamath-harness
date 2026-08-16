from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from py_nature_core import (
    PALETTE,
    add_panel_label,
    apply_py_nature_style,
    compose_multi_panel,
    make_network_curvature_panel,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    fig, axes = compose_multi_panel("network_hero_curve_stack", ["network", "gap", "community"])
    hero = axes["hero"]
    support_1 = axes["support_1"]
    support_2 = axes["support_2"]

    lc = make_network_curvature_panel(hero)
    add_panel_label(hero, "a")
    cbar = fig.colorbar(lc, ax=hero, fraction=0.046, pad=0.04)
    cbar.set_label("动态曲率", fontsize=7.0)

    t = np.linspace(0.1, 2.0, 10)
    gap = np.array([0.08, 0.11, 0.17, 0.29, 0.35, 0.31, 0.24, 0.20, 0.18, 0.17])
    support_1.plot(t, gap, color=PALETTE["curvature_high"], lw=1.9, marker="o", ms=3.8)
    support_1.axvline(0.9, color=PALETTE["neutral_mid"], linestyle="--", linewidth=1.0)
    support_1.annotate("特征时间尺度", xy=(0.9, 0.35), xytext=(1.08, 0.39), fontsize=6.8, color=PALETTE["neutral_dark"])
    support_1.set_xlabel("扩散时间")
    support_1.set_ylabel("曲率间隙")
    add_panel_label(support_1, "b")

    levels = np.array([2, 4, 8, 16, 32])
    modularity = np.array([0.36, 0.45, 0.58, 0.62, 0.56])
    support_2.plot(levels, modularity, color=PALETTE["blue_main"], lw=1.9, marker="s", ms=4.0)
    support_2.fill_between(levels, modularity - 0.03, modularity + 0.03, color=PALETTE["blue_secondary"], alpha=0.16)
    support_2.set_xlabel("社区尺度")
    support_2.set_ylabel("几何模块度")
    add_panel_label(support_2, "c")

    save_py_nature_figure(fig, Path(output_dir) / "network_curvature_multiscale")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
