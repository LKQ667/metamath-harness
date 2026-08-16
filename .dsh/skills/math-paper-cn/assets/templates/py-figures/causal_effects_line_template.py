from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import apply_py_nature_style, save_py_nature_figure
import matplotlib.pyplot as plt


METHODS = [
    ("Pearson", "#e19419", "o", np.array([0.72, 0.71, 0.69, 0.64, 0.59, 0.58, 0.56, 0.54, 0.51])),
    ("IDA", "#4aa3df", "h", np.array([0.776, 0.782, 0.769, 0.748, 0.740, 0.723, 0.697, 0.666, 0.629])),
    ("D$^2$CL", "#111111", "X", np.array([0.852, 0.860, 0.854, 0.844, 0.806, 0.794, 0.770, 0.733, 0.724])),
    ("SCL", "#0c9483", "D", np.array([0.850, 0.840, 0.818, 0.764, 0.721, 0.688, 0.653, 0.587, 0.561])),
]

SNR_LABELS = ["10.0", "6.0", "4.0", "2.0", "1.0", "0.75", "0.5", "0.25", "0.1"]


def add_value_rows(fig, methods: list[tuple[str, str, str, np.ndarray]]) -> None:
    left_x = 0.12
    start_x = 0.26
    end_x = 0.88
    y_rows = [0.115, 0.085, 0.055, 0.025]
    x_positions = np.linspace(start_x, end_x, len(SNR_LABELS))

    fig.text(0.11, 0.145, "SNR", ha="center", va="center", fontsize=8.2, color="black")
    for x, snr in zip(x_positions, SNR_LABELS):
        fig.text(x, 0.145, snr, ha="center", va="center", fontsize=8.2, color="black")

    for row_y, (name, color, _, values) in zip(y_rows, methods):
        fig.text(left_x, row_y, name, ha="center", va="center", fontsize=8.2, color=color)
        for x, val in zip(x_positions, values):
            fig.text(x, row_y, f"{val:.2f}", ha="center", va="center", fontsize=8.0, color=color)


def main(output_dir: str) -> None:
    apply_py_nature_style(font_size=7.2, axes_linewidth=0.8)
    fig = plt.figure(figsize=(4.0, 4.9))
    ax = fig.add_axes([0.14, 0.18, 0.79, 0.72])

    x = np.arange(len(SNR_LABELS))
    for name, color, marker, values in METHODS:
        ax.plot(
            x,
            values,
            color=color,
            marker=marker,
            markersize=5.0,
            linewidth=0.75,
            markerfacecolor=color,
            markeredgecolor=color if color != "#111111" else "black",
            label=name,
        )

    ax.set_title("Direct causal effects", fontsize=9.2, pad=4)
    ax.set_ylabel("1anh AUC", fontsize=8.6)
    ax.set_xlim(-0.8, len(SNR_LABELS) - 0.2)
    ax.set_ylim(0.40, 1.00)
    ax.set_xticks([])
    ax.set_yticks(np.arange(0.40, 1.01, 0.05))
    ax.tick_params(axis="y", labelsize=7.2, width=0.55)
    ax.tick_params(axis="x", length=0)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
    ax.legend(
        loc="upper right",
        frameon=False,
        fontsize=7.0,
        handlelength=1.6,
        handletextpad=0.5,
        labelspacing=0.35,
        borderaxespad=0.3,
    )

    add_value_rows(fig, METHODS)
    save_py_nature_figure(fig, Path(output_dir) / "causal_effects_line", dpi=320)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
