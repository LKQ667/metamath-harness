from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import apply_py_nature_style, make_tornado_plot, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    labels = ["需求波动", "服务率", "运输时延", "库存阈值", "惩罚系数", "折现率"]
    impacts = [0.18, 0.12, -0.09, 0.06, -0.14, 0.04]
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    make_tornado_plot(ax, labels, impacts)
    save_py_nature_figure(fig, Path(output_dir) / "sensitivity_tornado")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
