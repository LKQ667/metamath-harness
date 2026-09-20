from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (
    PALETTE,
    add_panel_label,
    apply_py_nature_style,
    compose_multi_panel,
    make_phase_portrait,
    save_py_nature_figure,
)
import matplotlib.pyplot as plt

PROFILE = "competition_en"

def main(output_dir: str) -> None:
    """chart_family: phase_portrait - qualitative behaviour of a dynamical system."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig, ax = plt.subplots(figsize=(3.2, 3.0))
    make_phase_portrait(ax)
    ax.set_title("Phase portrait of the epidemic model", pad=6)
    save_py_nature_figure(fig, Path(output_dir) / "dynamics_phase_portrait", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
