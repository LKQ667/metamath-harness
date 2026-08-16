from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from py_nature_core import add_panel_label, apply_py_nature_style, compose_multi_panel, make_interval_plot, make_lollipop_plot, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    fig, axes = compose_multi_panel("two_by_two")
    labels = ["方案 A", "方案 B", "方案 C", "方案 D"]
    make_interval_plot(axes["panel_1"], labels, [0.84, 0.81, 0.77, 0.72], [0.79, 0.76, 0.72, 0.68], [0.89, 0.86, 0.82, 0.76])
    axes["panel_1"].set_title("区间比较")
    add_panel_label(axes["panel_1"], "a")
    make_lollipop_plot(axes["panel_2"], labels, [0.74, 0.82, 0.69, 0.88])
    axes["panel_2"].set_title("排序比较")
    add_panel_label(axes["panel_2"], "b")
    axes["panel_3"].axis("off")
    axes["panel_4"].axis("off")
    save_py_nature_figure(fig, Path(output_dir) / "stats_interval_lollipop")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
