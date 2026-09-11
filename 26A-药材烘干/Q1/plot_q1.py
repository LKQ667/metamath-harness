"""问题 1 论文插图：温度场、含水率场、特征剖面与三维温度响应面。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import MultipleLocator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ambient import ambient_functions  # noqa: E402
from drying_model import properties_from_appendix2, solve_cylinder  # noqa: E402
from plot_common import export, palette, prepare_style  # noqa: E402

FIG_DIR = PROJECT_ROOT / "Q1" / "figures"
RESULTS_DIR = PROJECT_ROOT / "results"

CMAP_TEMP = LinearSegmentedColormap.from_list("tempseq", ["#F4F8FC", "#BBD6EC", "#5C93C6", "#2A5F9E", "#0F3D74"])
CMAP_MOIST = LinearSegmentedColormap.from_list("moistseq", ["#F3F9F7", "#B9DFD5", "#6FB3A8", "#3A8A8E", "#1C5A61"])


def compute():
    t_air, c_air = ambient_functions()
    return solve_cylinder(
        props=properties_from_appendix2(),
        radius=0.02,
        t_end=1800.0,
        dt=1.0,
        n_cells=200,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
    )


def figure_fields(result) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    r_cm = result.radii * 100.0
    t_min = result.times / 60.0
    fields = [
        ("fig_q1_temperature_field", result.temperature, CMAP_TEMP, "药材温度 / ℃", "温度由表面向中心逐层传入"),
        ("fig_q1_moisture_field", result.moisture, CMAP_MOIST, "含水率 / (kg·kg$^{-1}$)", "干燥前沿 30 min 内推进到 1.34 cm"),
    ]
    for name, data, cmap, label, title in fields:
        fig = plt.figure(figsize=(183 / 25.4, 74 / 25.4))
        ax = fig.add_subplot(111)
        mesh = ax.pcolormesh(r_cm, t_min, data, cmap=cmap, shading="gouraud", rasterized=True)
        levels = np.linspace(float(data.min()), float(data.max()), 7)[1:-1]
        cs = ax.contour(r_cm, t_min, data, levels=levels, colors="#FFFFFF", linewidths=0.6, alpha=0.75)
        ax.clabel(cs, inline=True, fontsize=6.5, fmt="%.2f")
        bar = fig.colorbar(mesh, ax=ax, pad=0.02)
        bar.set_label(label, fontsize=8.5)
        bar.ax.tick_params(labelsize=7.5)
        ax.set_xlabel("到药材中心的距离 / cm")
        ax.set_ylabel("时间 / min")
        ax.set_title(title, fontsize=9.5, pad=8)
        export(fig, FIG_DIR / name)


def figure_profiles(result) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    r_cm = result.radii * 100.0
    fig = plt.figure(figsize=(183 / 25.4, 76 / 25.4))
    grid = fig.add_gridspec(1, 2, wspace=0.28)

    ax = fig.add_subplot(grid[0, 0])
    picks = [300, 600, 900, 1200, 1500, 1800]
    shades = ["#C9DCF0", "#A6C6E4", "#7FA9D4", "#5688C0", "#2F63A2", "#0F3D74"]
    for value, color in zip(picks, shades):
        step = int(np.argmin(np.abs(result.times - value)))
        ax.plot(r_cm, result.moisture[step], color=color, lw=1.5, label=f"{value} s")
    ax.axhline(2.55, color=colors["neutral_mid"], lw=0.8, ls=":")
    ax.set_xlabel("到药材中心的距离 / cm")
    ax.set_ylabel("含水率 / (kg·kg$^{-1}$)")
    ax.set_ylim(1.2, 2.7)
    ax.legend(fontsize=7.2, ncol=2, loc="lower right")
    ax.set_title("含水率剖面随时间外扩", fontsize=9.2, pad=8)

    ax2 = fig.add_subplot(grid[0, 1])
    times = result.times / 60.0
    ax2.plot(times, result.temperature[:, -1], color=colors["red_strong"], lw=1.8, label="表面温度")
    ax2.plot(times, result.temperature[:, 0], color=colors["blue_main"], lw=1.8, label="中心温度")
    ax2.set_xlabel("时间 / min")
    ax2.set_ylabel("药材温度 / ℃")
    ax2.set_ylim(27.5, 38.5)
    ax2.legend(fontsize=8, loc="lower right")
    ax2.xaxis.set_major_locator(MultipleLocator(6.0))
    ax2.annotate(
        "表面 36.79 ℃",
        xy=(30.0, float(result.temperature[-1, -1])),
        xytext=(-64, 16),
        textcoords="offset points",
        fontsize=8,
        color=colors["red_strong"],
        arrowprops=dict(arrowstyle="->", color=colors["red_strong"], lw=0.8),
    )
    ax2.annotate(
        "中心 33.58 ℃",
        xy=(30.0, float(result.temperature[-1, 0])),
        xytext=(-64, -26),
        textcoords="offset points",
        fontsize=8,
        color=colors["blue_main"],
        arrowprops=dict(arrowstyle="->", color=colors["blue_main"], lw=0.8),
    )
    ax2.set_title("温度响应远快于含水率", fontsize=9.2, pad=8)
    export(fig, FIG_DIR / "fig_q1_profiles")


def figure_surface3d(result) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 82 / 25.4))
    ax = fig.add_subplot(111, projection="3d")
    r_cm = result.radii * 100.0
    t_min = result.times / 60.0
    tt, rr = np.meshgrid(t_min, r_cm, indexing="ij")
    surf = ax.plot_surface(tt, rr, result.temperature, cmap=CMAP_TEMP, linewidth=0, antialiased=True, rstride=8, cstride=2)
    ax.contour(tt, rr, result.temperature, zdir="z", offset=27.0, levels=8, cmap=CMAP_TEMP, linewidths=0.7)
    ax.set_xlabel("时间 / min", labelpad=6)
    ax.set_ylabel("到药材中心的距离 / cm", labelpad=6)
    ax.set_zlabel("药材温度 / ℃", labelpad=4)
    ax.view_init(elev=22, azim=-58)
    ax.tick_params(labelsize=7.5)
    ax.set_title("温度对时间与半径的耦合依赖", fontsize=9.5, pad=2)
    bar = fig.colorbar(surf, ax=ax, shrink=0.62, pad=0.09)
    bar.set_label("药材温度 / ℃", fontsize=8.5)
    bar.ax.tick_params(labelsize=7.5)
    export(fig, FIG_DIR / "fig_q1_surface3d")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    result = compute()
    figure_fields(result)
    figure_profiles(result)
    figure_surface3d(result)
    np.savez_compressed(
        RESULTS_DIR / "q1_fields.npz",
        times=result.times,
        radii=result.radii,
        temperature=result.temperature,
        moisture=result.moisture,
    )
    print("ok")


if __name__ == "__main__":
    main()
