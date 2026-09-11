"""问题 2 论文插图：温度场、含水率场与物性演化。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ambient import ambient_functions  # noqa: E402
from drying_model import properties_from_appendix3, solve_cylinder  # noqa: E402
from plot_common import export, palette, prepare_style  # noqa: E402

FIG_DIR = PROJECT_ROOT / "Q2" / "figures"
CMAP_TEMP = LinearSegmentedColormap.from_list("tempseq", ["#F4F8FC", "#BBD6EC", "#5C93C6", "#2A5F9E", "#0F3D74"])
CMAP_MOIST = LinearSegmentedColormap.from_list("moistseq", ["#F3F9F7", "#B9DFD5", "#6FB3A8", "#3A8A8E", "#1C5A61"])


def compute():
    t_air, c_air = ambient_functions()
    return solve_cylinder(
        props=properties_from_appendix3(),
        radius=0.02,
        t_end=3.0 * 3600.0,
        dt=1.0,
        n_cells=200,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
        record_every=20,
    )


def figure_fields(result) -> None:
    prepare_style(font_size=8.5)
    r_cm = result.radii * 100.0
    t_h = result.times / 3600.0
    for name, data, cmap, label, title in (
        ("fig_q2_temperature_field", result.temperature, CMAP_TEMP, "药材温度 / ℃", "恒温干燥段温度场趋于均匀"),
        ("fig_q2_moisture_field", result.moisture, CMAP_MOIST, "含水率 / (kg·kg$^{-1}$)", "干燥前沿在 3 h 内推进到距中心 1.1 cm"),
    ):
        fig = plt.figure(figsize=(183 / 25.4, 74 / 25.4))
        ax = fig.add_subplot(111)
        mesh = ax.pcolormesh(r_cm, t_h, data, cmap=cmap, shading="gouraud", rasterized=True)
        levels = np.linspace(float(data.min()), float(data.max()), 8)[1:-1]
        cs = ax.contour(r_cm, t_h, data, levels=levels, colors="#FFFFFF", linewidths=0.6, alpha=0.75)
        ax.clabel(cs, inline=True, fontsize=6.5, fmt="%.2f")
        bar = fig.colorbar(mesh, ax=ax, pad=0.02)
        bar.set_label(label, fontsize=8.5)
        bar.ax.tick_params(labelsize=7.5)
        ax.set_xlabel("到药材中心的距离 / cm")
        ax.set_ylabel("时间 / h")
        ax.set_title(title, fontsize=9.5, pad=8)
        export(fig, FIG_DIR / name)


def figure_properties(result) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 76 / 25.4))
    grid = fig.add_gridspec(1, 2, wspace=0.3)

    c = np.linspace(0.05, 2.55, 200)
    ax = fig.add_subplot(grid[0, 0])
    ax.plot(c, 650 + 128 * c, color=colors["blue_main"], lw=1.7, label="密度 ρ / (kg·m$^{-3}$)")
    ax.plot(c, 1450 + 2736 * c / (c + 1), color=colors["orange_main"], lw=1.7, label="比热容 $c_p$ / (J·kg$^{-1}$·K$^{-1}$)")
    ax.plot(c, (0.21 + 0.38 * c / (c + 1)) * 1000, color=colors["teal_main"], lw=1.7, label="导热系数 $k$ ×1000")
    ax.set_xlabel("含水率 / (kg·kg$^{-1}$)")
    ax.set_ylabel("物性取值")
    ax.legend(fontsize=7.4, loc="upper left")
    ax.set_title("物性随含水率单调增大", fontsize=9.2, pad=8)

    ax2 = fig.add_subplot(grid[0, 1])
    for tk, color, label in ((303.15, "#9EC5E8", "30 ℃"), (313.15, "#5688C0", "40 ℃"), (323.15, "#0F3D74", "50 ℃")):
        d = 2.4e-3 * np.exp(-0.45 / c) * np.exp(-3850.0 / tk) * 1e9
        ax2.semilogy(c, d, color=color, lw=1.7, label=label)
    ax2.set_xlabel("含水率 / (kg·kg$^{-1}$)")
    ax2.set_ylabel("扩散系数 $D$ / (10$^{-9}$ m$^{2}$·s$^{-1}$)")
    ax2.legend(fontsize=7.6, loc="upper right")
    ax2.set_title("扩散系数随含水率指数衰减", fontsize=9.2, pad=8)
    export(fig, FIG_DIR / "fig_q2_properties")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    result = compute()
    figure_fields(result)
    figure_properties(result)
    print("ok")


if __name__ == "__main__":
    main()
