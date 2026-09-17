"""统一的论文级绘图配置与通用绘图工具。"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "figures"
QFIGS = {1: ROOT / "Q1" / "figures", 2: ROOT / "Q2" / "figures", 3: ROOT / "Q3" / "figures"}
CN = ["Microsoft YaHei", "SimHei", "Arial", "Helvetica", "DejaVu Sans", "sans-serif"]
CLR = {
    "blue": "#0F4D92",
    "blue2": "#3775BA",
    "cyan": "#3F8EFC",
    "green": "#4F8A4B",
    "green2": "#AADCA9",
    "red": "#B64342",
    "red2": "#E9A6A1",
    "orange": "#E28E2C",
    "teal": "#42949E",
    "violet": "#9A4D8E",
    "gold": "#D8A431",
    "grey": "#8A8A8A",
    "grey2": "#D8D8D8",
    "dark": "#3F3F3F",
    "ink": "#222222",
    "slate": "#324A5F",
}
FAMILY = {
    "粮食": "#0F4D92",
    "粮食（豆类）": "#4F8A4B",
    "蔬菜": "#E28E2C",
    "蔬菜（豆类）": "#42949E",
    "食用菌": "#9A4D8E",
}


def style(font_size=8.0, line=1.0):
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = CN
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    plt.rcParams["font.size"] = font_size
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.linewidth"] = line
    plt.rcParams["legend.frameon"] = False
    plt.rcParams["axes.grid"] = False
    plt.rcParams["savefig.facecolor"] = "#FFFFFF"
    plt.rcParams["figure.facecolor"] = "#FFFFFF"
    plt.rcParams["axes.facecolor"] = "#FFFFFF"
    plt.rcParams["text.color"] = CLR["ink"]
    plt.rcParams["axes.labelcolor"] = CLR["ink"]
    plt.rcParams["xtick.color"] = CLR["ink"]
    plt.rcParams["ytick.color"] = CLR["ink"]
    plt.rcParams["figure.dpi"] = 120


def save(fig, q, name, dpi=320):
    targets = [ROOT / "figures", QFIGS[q]]
    saved = []
    for base in targets:
        base.mkdir(parents=True, exist_ok=True)
        for suffix in (".svg", ".pdf", ".png"):
            path = base / f"{name}{suffix}"
            fig.savefig(path, dpi=dpi, bbox_inches="tight")
            saved.append(path)
    plt.close(fig)
    return saved


def panel(ax, label, x=-0.08, y=1.03):
    if hasattr(ax, "get_zlim"):
        ax.text2D(x, y, label, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="left")
        return
    ax.text(x, y, label, transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom", ha="left")


def load_json(path):
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def line_with_band(ax, x, mean, low, high, color, label, marker="o"):
    ax.fill_between(x, low, high, color=color, alpha=0.16, linewidth=0)
    ax.plot(x, mean, color=color, lw=1.8, marker=marker, ms=3.4, label=label)


def interval_rows(ax, labels, centers, lows, highs, color, mark):
    y = np.arange(len(labels))[::-1]
    ax.hlines(y, lows, highs, color=color, linewidth=2.0, alpha=0.55)
    ax.scatter(centers, y, color=mark, s=26, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    return y
