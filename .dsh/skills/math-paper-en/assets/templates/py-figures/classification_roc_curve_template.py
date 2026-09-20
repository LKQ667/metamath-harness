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
    """chart_family: roc_curve - discrimination of competing classifiers."""
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fpr = np.linspace(0.0, 1.0, 200)
    curves = {
        "Logistic": fpr ** 0.55,
        "Random forest": fpr ** 0.34,
        "Gradient boosting": fpr ** 0.24,
    }
    colors = [PALETTE["neutral_mid"], PALETTE["teal_main"], PALETTE["blue_main"]]
    auc = {"Logistic": 0.78, "Random forest": 0.88, "Gradient boosting": 0.92}

    fig, ax = plt.subplots(figsize=(3.2, 2.9))
    ax.plot([0, 1], [0, 1], ls=":", lw=0.9, color=PALETTE["neutral_mid"])
    for (name, curve), color in zip(curves.items(), colors):
        ax.plot(fpr, curve, lw=1.8, color=color, label=f"{name} (AUC={auc[name]:.2f})")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.legend(loc="lower right", fontsize=6)
    save_py_nature_figure(fig, Path(output_dir) / "classification_roc_curve", profile=PROFILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
