"""论文用图统一样式与导出工具。

按 competition_cn 配置：中文标签、克制配色、白底无边框、三格式导出
（svg 文字可编辑、pdf TrueType 文本、png 预览），并统一单栏宽度。
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "cyan_main": "#3F8EFC",
    "green_soft": "#AADCA9",
    "green_strong": "#4F8A4B",
    "red_soft": "#E9A6A1",
    "red_strong": "#B64342",
    "orange_main": "#E28E2C",
    "coral_main": "#E76F51",
    "teal_main": "#42949E",
    "violet_main": "#9A4D8E",
    "gold_main": "#D8A431",
    "neutral_light": "#D8D8D8",
    "neutral_mid": "#8A8A8A",
    "neutral_dark": "#3F3F3F",
    "slate_dark": "#324A5F",
    "black": "#222222",
}

CN_FONT_CANDIDATES = ("Microsoft YaHei", "SimHei", "SimSun", "Arial", "DejaVu Sans")
SINGLE_COLUMN_MM = 89.0
MM_PER_INCH = 25.4


def mm_to_inch(mm: float) -> float:
    return mm / MM_PER_INCH


def available_cn_font() -> str:
    names = {f.name for f in font_manager.fontManager.ttflist}
    for candidate in CN_FONT_CANDIDATES:
        if candidate in names:
            return candidate
    return "DejaVu Sans"


def apply_style(base_font_pt: float = 8.0) -> str:
    """设置全局样式，返回实际使用的中文字体名。"""
    font = available_cn_font()
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [font] + [c for c in CN_FONT_CANDIDATES if c != font],
        "axes.unicode_minus": False,
        "font.size": base_font_pt,
        "axes.labelsize": base_font_pt + 0.5,
        "axes.titlesize": base_font_pt + 1.0,
        "xtick.labelsize": base_font_pt - 0.5,
        "ytick.labelsize": base_font_pt - 0.5,
        "legend.fontsize": base_font_pt - 0.5,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": PALETTE["neutral_dark"],
        "axes.labelcolor": PALETTE["black"],
        "text.color": PALETTE["black"],
        "xtick.color": PALETTE["neutral_dark"],
        "ytick.color": PALETTE["neutral_dark"],
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.major.size": 2.6,
        "ytick.major.size": 2.6,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "lines.linewidth": 1.3,
        "grid.color": PALETTE["neutral_light"],
        "grid.linewidth": 0.5,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.dpi": 120,
        "savefig.dpi": 320,
    })
    return font


def new_figure(width_mm: float = SINGLE_COLUMN_MM, height_mm: float = 62.0):
    """建立单面板画布；禁用子图策略下每张图只允许一个数据视图。"""
    fig = plt.figure(figsize=(mm_to_inch(width_mm), mm_to_inch(height_mm)))
    ax = fig.add_axes([0.15, 0.20, 0.82, 0.74])
    return fig, ax


def export(fig, out_dir: Path, stem: str) -> list[str]:
    """导出 svg + pdf + png 三格式，返回相对路径列表。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for suffix, dpi in ((".svg", None), (".pdf", None), (".png", 320)):
        path = out_dir / f"{stem}{suffix}"
        kwargs = {"dpi": dpi} if dpi else {}
        fig.savefig(path, **kwargs)
        paths.append(path)
    plt.close(fig)
    return paths


def check_cn_render(texts: list[str]) -> dict:
    """检查待渲染中文文本是否含缺字符号。"""
    bad = [t for t in texts if any(ch in t for ch in ("\ufffd", "?", "\u25a1"))]
    return {"ok": not bad, "offenders": bad}


def style_axes(ax, xlabel: str = "", ylabel: str = "", grid_axis: str | None = None) -> None:
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if grid_axis:
        ax.grid(True, axis=grid_axis, linestyle="-", alpha=0.35, zorder=0)
        ax.set_axisbelow(True)


def add_note(ax, text: str, loc: str = "upper right") -> None:
    anchors = {
        "upper right": (0.98, 0.96, "right", "top"),
        "upper left": (0.02, 0.96, "left", "top"),
        "lower right": (0.98, 0.04, "right", "bottom"),
        "lower left": (0.02, 0.04, "left", "bottom"),
    }
    x, y, ha, va = anchors[loc]
    ax.text(x, y, text, transform=ax.transAxes, ha=ha, va=va,
            fontsize=plt.rcParams["font.size"] - 0.5, color=PALETTE["neutral_dark"])
