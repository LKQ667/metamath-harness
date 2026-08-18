from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import PALETTE, add_panel_label, apply_py_nature_style, compose_multi_panel, make_network_topology, make_tornado_plot, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    fig, axes = compose_multi_panel("hero_top_support_bottom")
    hero = axes["hero"]
    make_network_topology(hero)
    hero.set_title("多层供应网络与控制节点", pad=6)
    add_panel_label(hero, "a")

    x = np.arange(1, 9)
    y = 0.62 + 0.03 * x + 0.02 * np.sin(x / 1.5)
    axes["support_1"].plot(x, y, color=PALETTE["blue_main"], lw=2)
    axes["support_1"].set_title("收敛过程")
    axes["support_1"].set_xlabel("轮次")
    axes["support_1"].set_ylabel("收益")
    add_panel_label(axes["support_1"], "b")

    make_tornado_plot(axes["support_2"], ["需求", "时延", "容量", "阈值"], [0.14, -0.11, 0.08, -0.05])
    axes["support_2"].set_title("敏感性")
    add_panel_label(axes["support_2"], "c")

    axes["support_3"].scatter([0.70, 0.75, 0.80, 0.84], [58, 52, 47, 42], s=28, color=PALETTE["orange_main"])
    axes["support_3"].plot([0.70, 0.84], [58, 42], color=PALETTE["orange_main"], lw=1.8)
    axes["support_3"].set_title("Pareto 权衡")
    axes["support_3"].set_xlabel("鲁棒性")
    axes["support_3"].set_ylabel("成本")
    add_panel_label(axes["support_3"], "d")

    axes["legend"].axis("off")
    save_py_nature_figure(fig, Path(output_dir) / "multi_panel_hero_support")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
