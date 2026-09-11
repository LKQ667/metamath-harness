"""数据预处理阶段的顶刊风格中文图。

输出到 数据预处理/figures/，每张图同时导出 svg、pdf、png。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from plot_common import export, palette, prepare_style  # noqa: E402

FIG_DIR = PROJECT_ROOT / "数据预处理" / "figures"
DERIVED_DIR = PROJECT_ROOT / "data" / "derived"


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    ambient = pd.read_csv(DERIVED_DIR / "ambient_conditions.csv")
    radius = pd.read_csv(DERIVED_DIR / "radius_profile.csv")
    return ambient, radius


def figure_ambient(ambient: pd.DataFrame) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 74 / 25.4))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.0], wspace=0.42)

    hours = ambient["时间"].to_numpy() / 3600.0
    temp = ambient["温度"].to_numpy()
    conc = ambient["水分浓度"].to_numpy()

    ax_t = fig.add_subplot(grid[0, 0])
    ax_t.plot(hours, temp, color=colors["blue_main"], lw=1.9)
    ax_t.set_xlabel("时间 / h")
    ax_t.set_ylabel("烘房温度 / ℃")
    ax_t.set_xlim(0, 4.0)
    ax_t.set_ylim(26, 53)
    ax_t.xaxis.set_major_locator(MultipleLocator(1.0))
    ax_t.annotate(
        f"{temp[-1]:.2f} ℃",
        xy=(hours[-1], temp[-1]),
        xytext=(-46, -20),
        textcoords="offset points",
        color=colors["blue_main"],
        fontsize=8,
        arrowprops=dict(arrowstyle="-", color=colors["blue_main"], lw=0.8),
    )
    ax_t.set_title("烘房温度在 4 h 内趋稳", fontsize=9.2, pad=8)

    ax_c = fig.add_subplot(grid[0, 1])
    ax_c.plot(hours, conc, color=colors["orange_main"], lw=1.9)
    ax_c.set_xlabel("时间 / h")
    ax_c.set_ylabel("烘房水分浓度 / (kg·kg$^{-1}$)")
    ax_c.set_xlim(0, 4.0)
    ax_c.xaxis.set_major_locator(MultipleLocator(1.0))
    ax_c.annotate(
        f"{conc[-1]:.4f}",
        xy=(hours[-1], conc[-1]),
        xytext=(-56, -30),
        textcoords="offset points",
        color=colors["orange_main"],
        fontsize=8,
        arrowprops=dict(arrowstyle="-", color=colors["orange_main"], lw=0.8),
    )
    ax_c.set_title("烘房水分浓度同向上升", fontsize=9.2, pad=8)

    ax_s = fig.add_subplot(grid[0, 2])
    ax_s.scatter(temp, conc, s=9, color=colors["teal_main"], alpha=0.75, edgecolors="none")
    slope, intercept = np.polyfit(temp, conc, 1)
    fit_x = np.linspace(temp.min(), temp.max(), 50)
    ax_s.plot(fit_x, slope * fit_x + intercept, color=colors["red_strong"], lw=1.3)
    corr = float(np.corrcoef(temp, conc)[0, 1])
    ax_s.text(0.04, 0.92, f"Pearson $r$ = {corr:.3f}", transform=ax_s.transAxes, fontsize=8.2)
    ax_s.set_xlabel("烘房温度 / ℃")
    ax_s.set_ylabel("烘房水分浓度 / (kg·kg$^{-1}$)")
    ax_s.set_title("两工况高度线性相关", fontsize=9.2, pad=8)
    export(fig, FIG_DIR / "fig_eda_ambient")


def figure_radius(radius: pd.DataFrame) -> None:
    colors = palette()
    prepare_style(font_size=8.5)
    fig = plt.figure(figsize=(183 / 25.4, 78 / 25.4))
    grid = fig.add_gridspec(1, 2, width_ratios=[2.0, 1.0], wspace=0.3)

    t = radius["时间"].to_numpy() / 3600.0
    r = radius["半径"].to_numpy()
    ax = fig.add_subplot(grid[0, 0])
    ax.plot(t, r, color=colors["blue_main"], lw=1.6, alpha=0.5, label="实测半径")
    ax.scatter(t, r, s=12, color=colors["blue_main"], zorder=3, label="附件 2 采样点")
    ax.fill_between(t, r, r.min(), color=colors["blue_secondary"], alpha=0.10)
    ax.set_xlabel("时间 / h")
    ax.set_ylabel("药材半径 / cm")
    ax.set_xlim(0, t.max() * 1.02)
    ax.set_ylim(r.min() - 0.08, r.max() + 0.06)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("药材半径随时间的收缩轨迹", fontsize=9.5, pad=8)
    ax.annotate(
        f"{r[0]:.3f} cm → {r[-1]:.3f} cm",
        xy=(t[-1], r[-1]),
        xytext=(-104, 22),
        textcoords="offset points",
        fontsize=8,
        color=colors["neutral_dark"],
        arrowprops=dict(arrowstyle="->", color=colors["neutral_mid"], lw=0.8),
    )

    axr = fig.add_subplot(grid[0, 1])
    dt = np.diff(t)
    dr = np.diff(r)
    rate = np.divide(dr, dt, out=np.zeros_like(dr), where=dt != 0)
    axr.plot(t[1:], rate, color=colors["coral_main"], lw=1.5)
    axr.axhline(0, color=colors["neutral_mid"], lw=0.8, ls=":")
    axr.set_xlabel("时间 / h")
    axr.set_ylabel("收缩速率 / (cm·h$^{-1}$)")
    axr.set_title("收缩速率快速衰减后趋稳", fontsize=9.5, pad=8)
    export(fig, FIG_DIR / "fig_eda_radius")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    ambient, radius = load()
    figure_ambient(ambient)
    figure_radius(radius)
    print("ok")


if __name__ == "__main__":
    main()
