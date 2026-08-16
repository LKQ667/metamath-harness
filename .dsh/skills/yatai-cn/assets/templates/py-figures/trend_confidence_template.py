from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import PALETTE, apply_py_nature_style, make_trend_with_band, save_py_nature_figure
import matplotlib.pyplot as plt


def main(output_dir: str) -> None:
    apply_py_nature_style(font_size=7.0)
    x = np.arange(1, 13)
    rng = np.random.default_rng(7)
    baseline = np.vstack([0.62 + 0.02 * x + rng.normal(0, 0.01, size=len(x)) for _ in range(4)])
    policy = np.vstack([0.66 + 0.024 * x + rng.normal(0, 0.01, size=len(x)) for _ in range(4)])
    robust = np.vstack([0.64 + 0.022 * x + rng.normal(0, 0.01, size=len(x)) for _ in range(4)])

    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    make_trend_with_band(
        ax,
        x,
        [baseline, robust, policy],
        ["基线方案", "稳健方案", "优化方案"],
        [PALETTE["neutral_mid"], PALETTE["teal_main"], PALETTE["blue_main"]],
        "迭代轮次",
        "目标函数值",
    )
    ax.legend(loc="lower right")
    save_py_nature_figure(fig, Path(output_dir) / "trend_confidence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()
    main(args.output_dir)
