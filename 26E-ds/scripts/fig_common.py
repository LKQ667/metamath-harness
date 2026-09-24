from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _skill_root() -> Path:
    override = os.environ.get("MATH_PAPER_HUAWEI_SKILL")
    if override:
        candidate = Path(override)
        if candidate.is_dir():
            return candidate
        raise RuntimeError(f"MATH_PAPER_HUAWEI_SKILL 指向的目录不存在: {candidate}")
    home = Path.home()
    candidates = (
        home / ".dsh" / "skills" / "math-paper-huawei",
        home / ".codex" / "skills" / "math-paper-huawei",
        home / ".trae-cn" / "skills" / "math-paper-huawei",
    )
    for item in candidates:
        if item.is_dir():
            return item
    raise RuntimeError(
        "未找到 math-paper-huawei 技能目录；请设置环境变量 MATH_PAPER_HUAWEI_SKILL"
    )


SKILL = _skill_root()
CORE_PATH = SKILL / "scripts" / "plotting" / "py_nature_core.py"

_spec = importlib.util.spec_from_file_location("py_nature_core", CORE_PATH)
core = importlib.util.module_from_spec(_spec)
sys.modules["py_nature_core"] = core
_spec.loader.exec_module(core)

PALETTE = core.PALETTE
FAMILY_PALETTE = core.FAMILY_PALETTE
apply_py_nature_style = core.apply_py_nature_style
save_py_nature_figure = core.save_py_nature_figure
run_py_nature_qa = core.run_py_nature_qa
mm_to_inch = core.mm_to_inch
NATURE_WIDTH_MM = core.NATURE_WIDTH_MM

PROJECT = Path(__file__).resolve().parents[1]
FIGURES = PROJECT / "figures"

MODALITY_COLORS = {
    "文本": PALETTE["blue_main"],
    "语音": PALETTE["orange_main"],
    "视觉": PALETTE["teal_main"],
    "全模态": PALETTE["slate_dark"],
    "缺失文本": PALETTE["red_strong"],
    "缺失语音": PALETTE["violet_main"],
    "缺失视觉": PALETTE["gold_main"],
}


def setup(font_size: float = 7.0) -> None:
    apply_py_nature_style(font_size=font_size, profile="competition_cn")
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["axes.titlesize"] = font_size + 0.5
    plt.rcParams["axes.labelsize"] = font_size
    plt.rcParams["xtick.labelsize"] = font_size - 0.5
    plt.rcParams["ytick.labelsize"] = font_size - 0.5
    plt.rcParams["legend.fontsize"] = font_size - 0.5


def single_figure(width_mm: float = 140.0, height_mm: float = 88.0):
    setup()
    fig, ax = plt.subplots(figsize=(mm_to_inch(width_mm), mm_to_inch(height_mm)))
    return fig, ax


def wide_figure(width_mm: float = 183.0, height_mm: float = 92.0):
    setup()
    fig, ax = plt.subplots(figsize=(mm_to_inch(width_mm), mm_to_inch(height_mm)))
    return fig, ax


def three_d_figure(width_mm: float = 150.0, height_mm: float = 118.0):
    setup()
    fig = plt.figure(figsize=(mm_to_inch(width_mm), mm_to_inch(height_mm)))
    ax = fig.add_subplot(111, projection="3d")
    return fig, ax


def soften(ax, grid_axis: str = "y", color: str | None = None) -> None:
    ax.grid(True, axis=grid_axis, color="#D9D9D9", linewidth=0.5, linestyle="-", zorder=0)
    ax.set_axisbelow(True)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#4D4D4D")


def save(fig, name: str, out_dir: Path | None = None) -> dict:
    target_dir = Path(out_dir) if out_dir else FIGURES
    target_dir.mkdir(parents=True, exist_ok=True)
    base = target_dir / name
    saved = save_py_nature_figure(fig, base, dpi=400, formats=("svg", "pdf", "png"),
                                  profile="competition_cn")
    qa = run_py_nature_qa(base, profile="competition_cn")
    return {
        "name": name,
        "files": [str(Path(item).relative_to(PROJECT)).replace("\\", "/") for item in saved],
        "qa_passed": bool(qa.passed),
        "qa_checks": {key: value for key, value in qa.checks.items()
                      if isinstance(value, (bool, str, int, float))},
    }


def annotate_extremum(ax, x, y, label: str, color: str, dx: float = 6.0, dy: float = 6.0) -> None:
    ax.annotate(
        label,
        xy=(x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=6.4,
        color=color,
        arrowprops=dict(arrowstyle="-", color=color, linewidth=0.7, shrinkA=0.0, shrinkB=2.0),
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor=color,
                  linewidth=0.6, alpha=0.92),
    )
