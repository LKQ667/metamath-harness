from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from py_nature_core import apply_py_nature_style, make_phase_portrait, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style()
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    make_phase_portrait(ax)
    save_py_nature_figure(fig, Path(output_dir) / "dynamics_phase_portrait")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
