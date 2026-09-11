"""问题 4 论文插图：收缩与含水率耦合、以及与固定域模型（问题 3）的对比。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from scipy.interpolate import PchipInterpolator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ambient import ambient_functions  # noqa: E402
from drying_model import properties_from_appendix3, properties_from_appendix4, solve_cylinder, solve_shrinking  # noqa: E402
from plot_common import export, palette, prepare_style  # noqa: E402

FIG_DIR = PROJECT_ROOT / "Q4" / "figures"
DERIVED_DIR = PROJECT_ROOT / "data" / "derived"


def radius_functions():
    frame = pd.read_csv(DERIVED_DIR / "radius_profile.csv")
    time = frame["时间"].to_numpy(dtype=float)
    radius_cm = frame["半径"].to_numpy(dtype=float)
    spline = PchipInterpolator(time, radius_cm)
    derivative = spline.derivative()
    t_last = float(time[-1])

    def radius_of(t: float) -> float:
        return float(spline(min(t, t_last))) / 100.0

    def rate_of(t: float) -> float:
        return 0.0 if t >= t_last else float(derivative(t)) / 100.0

    return radius_of, rate_of


def compute_q4():
    t_air, c_air = ambient_functions()
    radius_of, rate_of = radius_functions()
    return solve_shrinking(
        props=properties_from_appendix4(),
        radius_of=radius_of,
        rate_of=rate_of,
        t_end=30.0 * 24 * 3600.0,
        dt=10.0,
        n_cells=200,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
        record_every=6,
        stop_moisture=0.15,
    )


def compute_q3():
    t_air, c_air = ambient_functions()
    return solve_cylinder(
        props=properties_from_appendix3(),
        radius=0.02,
        t_end=30.0 * 24 * 3600.0,
        dt=10.0,
        n_cells=200,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
        record_every=6,
        stop_moisture=0.15,
        keep_index=np.array([0, 200]),
    )


def figure_shrinkage(result4, radius_of) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 76 / 25.4))
    grid = fig.add_gridspec(1, 2, wspace=0.3)

    t_h = result4.times / 3600.0
    radius_cm = np.array([radius_of(t) * 100.0 for t in result4.times])

    ax = fig.add_subplot(grid[0, 0])
    ax.plot(t_h, radius_cm, color=colors["teal_main"], lw=1.9, label="药材半径 $R(t)$")
    ax.set_xlabel("时间 / h")
    ax.set_ylabel("药材半径 / cm")
    ax.set_xlim(0, 55)
    ax.set_ylim(1.15, 2.05)
    ax.xaxis.set_major_locator(MultipleLocator(12.0))
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("半径在 50.8 h 内收缩到 1.20 cm", fontsize=9.2, pad=8)

    ax2 = fig.add_subplot(grid[0, 1])
    ax2.plot(t_h, result4.moisture[:, 0], color=colors["blue_main"], lw=1.8, label="中心含水率")
    ax2.plot(t_h, result4.moisture[:, -1], color=colors["orange_main"], lw=1.8, label="表面含水率")
    ax2.axhline(0.15, color=colors["red_strong"], lw=1.1, ls=":")
    ax2.text(2.0, 0.18, "烘干阈值 0.15 kg/kg", color=colors["red_strong"], fontsize=8)
    ax2.set_xlabel("时间 / h")
    ax2.set_ylabel("含水率 / (kg·kg$^{-1}$)")
    ax2.set_xlim(0, 55)
    ax2.set_ylim(0.0, 2.8)
    ax2.xaxis.set_major_locator(MultipleLocator(12.0))
    ax2.legend(fontsize=8, loc="upper right")
    ax2.set_title("收缩使内外含水率差显著收窄", fontsize=9.2, pad=8)
    export(fig, FIG_DIR / "fig_q4_shrinkage")


def figure_compare(result3, result4) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 76 / 25.4))
    grid = fig.add_gridspec(1, 2, wspace=0.3)

    ax = fig.add_subplot(grid[0, 0])
    ax.plot(result3.times / 3600.0, result3.moisture[:, 0], color=colors["neutral_mid"], lw=1.8, label="固定域：中心")
    ax.plot(result4.times / 3600.0, result4.moisture[:, 0], color=colors["blue_main"], lw=1.9, label="收缩域：中心")
    ax.plot(result4.times / 3600.0, result4.moisture[:, -1], color=colors["orange_main"], lw=1.5, ls="--", label="收缩域：表面")
    ax.axhline(0.15, color=colors["red_strong"], lw=1.1, ls=":")
    ax.set_xlabel("时间 / h")
    ax.set_ylabel("含水率 / (kg·kg$^{-1}$)")
    ax.set_xlim(0, 62)
    ax.set_ylim(0.0, 2.8)
    ax.xaxis.set_major_locator(MultipleLocator(12.0))
    ax.legend(fontsize=7.6, loc="upper right")
    ax.set_title("收缩域含水率整体更快下降", fontsize=9.2, pad=8)

    ax2 = fig.add_subplot(grid[0, 1])
    labels = ["固定域\n问题 3", "收缩域\n问题 4"]
    values = [57.1, 50.8]
    ys = [1.0, 0.0]
    ax2.hlines(ys, 0.0, values, color=[colors["neutral_mid"], colors["blue_main"]], lw=2.4)
    ax2.scatter(values, ys, s=70, color=[colors["neutral_mid"], colors["blue_main"]], zorder=3)
    for value, y in zip(values, ys):
        ax2.text(value + 1.6, y, f"{value:.1f} h", va="center", fontsize=9)
    ax2.set_yticks(ys)
    ax2.set_yticklabels(labels)
    ax2.set_xlim(0, 72)
    ax2.set_ylim(-0.6, 1.6)
    ax2.set_xlabel("烘干所需时间 / h")
    ax2.set_title("收缩使烘干时间缩短 11.0%", fontsize=9.2, pad=8)
    export(fig, FIG_DIR / "fig_q4_compare")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    radius_of, _ = radius_functions()
    result4 = compute_q4()
    result3 = compute_q3()
    figure_shrinkage(result4, radius_of)
    figure_compare(result3, result4)
    print("ok")


if __name__ == "__main__":
    main()
