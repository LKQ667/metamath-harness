from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import apply_py_nature_style, make_spatial_contour, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    make_spatial_contour(ax, with_quiver=True)
    save_py_nature_figure(fig, Path(output_dir) / "spatial_contour_flow")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
