"""问题 3 论文插图：烘干时间判定曲线、剖面演化与三维含水率曲面。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import MultipleLocator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ambient import ambient_functions  # noqa: E402
from drying_model import properties_from_appendix3, solve_cylinder  # noqa: E402
from plot_common import export, palette, prepare_style  # noqa: E402

FIG_DIR = PROJECT_ROOT / "Q3" / "figures"
CMAP_MOIST = LinearSegmentedColormap.from_list("moistseq", ["#F3F9F7", "#B9DFD5", "#6FB3A8", "#3A8A8E", "#1C5A61"])


def compute():
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
        keep_index=np.arange(0, 201, 10),
    )


def figure_curve(result) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 76 / 25.4))
    grid = fig.add_gridspec(1, 2, wspace=0.28)

    t_h = result.times / 3600.0
    ax = fig.add_subplot(grid[0, 0])
    ax.semilogy(t_h, result.moisture[:, 0], color=colors["blue_main"], lw=1.9, label="中心含水率")
    ax.semilogy(t_h, result.moisture[:, -1], color=colors["orange_main"], lw=1.9, label="表面含水率")
    ax.semilogy(t_h, result.moisture.mean(axis=1), color=colors["teal_main"], lw=1.5, ls="--", label="径向平均含水率")
    ax.axhline(0.15, color=colors["red_strong"], lw=1.2, ls=":")
    ax.text(2.0, 0.165, "烘干阈值 0.15 kg/kg", color=colors["red_strong"], fontsize=8)
    ax.axvline(57.1, color=colors["neutral_mid"], lw=1.0, ls="--")
    ax.annotate(
        "烘干结束 57.1 h",
        xy=(57.1, 0.15),
        xytext=(-96, 34),
        textcoords="offset points",
        fontsize=8.2,
        color=colors["neutral_dark"],
        arrowprops=dict(arrowstyle="->", color=colors["neutral_mid"], lw=0.9),
    )
    ax.set_xlabel("时间 / h")
    ax.set_ylabel("含水率 / (kg·kg$^{-1}$)")
    ax.set_xlim(0, 62)
    ax.set_ylim(0.04, 3.0)
    ax.xaxis.set_major_locator(MultipleLocator(12.0))
    ax.legend(fontsize=7.8, loc="upper right")
    ax.set_title("中心含水率是烘干判据的控制点", fontsize=9.2, pad=8)

    ax2 = fig.add_subplot(grid[0, 1])
    rate = np.gradient(result.moisture[:, 0], result.times / 3600.0)
    ax2.plot(t_h, -rate, color=colors["blue_main"], lw=1.8)
    ax2.set_yscale("log")
    ax2.set_xlabel("时间 / h")
    ax2.set_ylabel("中心含水率下降速率 / (kg·kg$^{-1}$·h$^{-1}$)")
    ax2.set_xlim(0, 62)
    ax2.set_ylim(2e-4, 8e-2)
    ax2.xaxis.set_major_locator(MultipleLocator(12.0))
    ax2.axvspan(0, 12, color=colors["blue_secondary"], alpha=0.12)
    ax2.text(1.5, 3.2e-2, "快速失水段", fontsize=8, color=colors["blue_main"])
    ax2.text(20.0, 1.4e-3, "扩散控制段", fontsize=8, color=colors["neutral_dark"])
    ax2.set_title("失水速率在 12 h 后转入扩散控制", fontsize=9.2, pad=8)
    export(fig, FIG_DIR / "fig_q3_drying_curve")


def figure_profiles(result) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 74 / 25.4))
    ax = fig.add_subplot(111)
    r_cm = result.radii * 100.0
    picks = [6, 12, 18, 24, 36, 48]
    shades = ["#D5E5F2", "#AECBE6", "#87B0D7", "#5E92C6", "#3570AE", "#0F3D74"]
    for value, color in zip(picks, shades):
        step = int(np.argmin(np.abs(result.times - value * 3600.0)))
        ax.plot(r_cm, result.moisture[step], color=color, lw=1.5, label=f"{value} h")
    step = result.moisture.shape[0] - 1
    ax.plot(r_cm, result.moisture[step], color=colors["red_strong"], lw=1.9, label="57.1 h（结束）")
    ax.axhline(0.15, color=colors["neutral_mid"], lw=0.9, ls=":")
    ax.set_xlabel("到药材中心的距离 / cm")
    ax.set_ylabel("含水率 / (kg·kg$^{-1}$)")
    ax.set_ylim(0.0, 2.8)
    ax.legend(fontsize=7.4, ncol=2, loc="upper right")
    ax.set_title("剖面由外向内整体下移直至全断面达标", fontsize=9.4, pad=8)
    export(fig, FIG_DIR / "fig_q3_profile_evolution")


def figure_surface3d(result) -> None:
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 82 / 25.4))
    ax = fig.add_subplot(111, projection="3d")
    r_cm = result.radii * 100.0
    t_h = result.times / 3600.0
    tt, rr = np.meshgrid(t_h, r_cm, indexing="ij")
    surf = ax.plot_surface(tt, rr, result.moisture, cmap=CMAP_MOIST, linewidth=0, antialiased=True, rstride=12, cstride=2)
    ax.contour(tt, rr, result.moisture, zdir="z", offset=0.0, levels=9, cmap=CMAP_MOIST, linewidths=0.7)
    ax.set_xlabel("时间 / h", labelpad=6)
    ax.set_ylabel("到药材中心的距离 / cm", labelpad=6)
    ax.set_zlabel("含水率 / (kg·kg$^{-1}$)", labelpad=4)
    ax.view_init(elev=22, azim=-58)
    ax.tick_params(labelsize=7.5)
    ax.set_title("含水率在时间—半径平面上的衰减曲面", fontsize=9.4, pad=2)
    bar = fig.colorbar(surf, ax=ax, shrink=0.62, pad=0.09)
    bar.set_label("含水率 / (kg·kg$^{-1}$)", fontsize=8.5)
    bar.ax.tick_params(labelsize=7.5)
    export(fig, FIG_DIR / "fig_q3_surface3d")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    result = compute()
    figure_curve(result)
    figure_profiles(result)
    figure_surface3d(result)
    print("ok")


if __name__ == "__main__":
    main()
