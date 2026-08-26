from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
import warnings
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.patches import FancyArrowPatch
from matplotlib.collections import LineCollection
import numpy as np


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
    "curvature_low": "#2A6DBB",
    "curvature_mid": "#BFD3EA",
    "curvature_high": "#D95F4C",
    "temporal_focus": "#2B7C6F",
    "spatial_focus": "#1F9D8A",
    "neutral_light": "#D8D8D8",
    "neutral_mid": "#8A8A8A",
    "neutral_dark": "#3F3F3F",
    "slate_dark": "#324A5F",
    "black": "#222222",
}

FAMILY_PALETTE = {
    "baseline_dark": "#484878",
    "baseline_mid": "#7884B4",
    "baseline_soft": "#B4C0E4",
    "hero_tiny": "#E4E4F0",
    "hero_base": "#E4CCD8",
    "hero_large": "#F0C0CC",
}

NATURE_WIDTH_MM = {"single": 89, "double": 183}
ALLOWED_FORMATS = ("svg", "pdf", "png")
PROFILE_FONTS = {
    "competition_cn": ["Microsoft YaHei", "SimHei", "Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "competition_en": ["Arial", "Helvetica", "Microsoft YaHei", "SimHei", "DejaVu Sans", "sans-serif"],
    "research": ["Arial", "Helvetica", "DejaVu Sans", "Microsoft YaHei", "SimHei", "sans-serif"],
}
PROFILE_ALIASES = {"nature": "competition_cn", "cn": "competition_cn", "en": "competition_en"}


@dataclass(frozen=True)
class QAResult:
    passed: bool
    checks: dict


def mm_to_inch(mm: float) -> float:
    return mm / 25.4


def normalize_profile(profile: str | None) -> str:
    normalized = PROFILE_ALIASES.get((profile or "competition_cn").strip().lower(), (profile or "competition_cn").strip().lower())
    if normalized not in PROFILE_FONTS:
        raise ValueError(f"未知绘图配置: {profile}；可选值为 {', '.join(PROFILE_FONTS)}")
    return normalized


def apply_py_nature_style(
    font_size: float = 7.0,
    axes_linewidth: float = 1.0,
    dark: bool = False,
    profile: str = "competition_cn",
) -> None:
    profile = normalize_profile(profile)
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = PROFILE_FONTS[profile]
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    plt.rcParams["font.size"] = font_size
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.linewidth"] = axes_linewidth
    plt.rcParams["legend.frameon"] = False
    plt.rcParams["axes.grid"] = False
    plt.rcParams["savefig.facecolor"] = "#000000" if dark else "#FFFFFF"
    plt.rcParams["figure.facecolor"] = "#000000" if dark else "#FFFFFF"
    plt.rcParams["axes.facecolor"] = "#000000" if dark else "#FFFFFF"
    plt.rcParams["text.color"] = "#FFFFFF" if dark else PALETTE["black"]
    plt.rcParams["axes.labelcolor"] = "#FFFFFF" if dark else PALETTE["black"]
    plt.rcParams["xtick.color"] = "#FFFFFF" if dark else PALETTE["black"]
    plt.rcParams["ytick.color"] = "#FFFFFF" if dark else PALETTE["black"]


def choose_chart_family(
    task_type: str,
    data_semantics: str = "",
    compare_goal: str = "",
    need_uncertainty: bool = False,
) -> dict:
    task = (task_type or "").strip().lower()
    semantics = (data_semantics or "").strip().lower()
    goal = (compare_goal or "").strip().lower()

    if task == "sensitivity":
        return {
            "family": "tornado" if "sobol" not in semantics else "heatmap",
            "preferred": ["tornado", "heatmap", "local_response_curve"],
            "avoid": ["vertical_bar"],
            "reason": "敏感性分析默认不用二维竖直柱图。",
        }
    if task == "optimization":
        return {
            "family": "pareto" if "multi" in goal or "tradeoff" in goal or "权衡" in compare_goal else "line_band",
            "preferred": ["pareto", "feasible_region", "convergence_line"],
            "avoid": ["vertical_bar"],
            "reason": "优化任务优先表达前沿、可行域和收敛过程。",
        }
    if task == "network":
        if "curvature" in semantics or "geometry" in semantics or "multiscale" in semantics:
            return {
                "family": "network_curvature_multiscale",
                "preferred": ["network_curvature_multiscale", "network_topology", "resilience_curve"],
                "avoid": ["vertical_bar"],
                "reason": "网络几何和多尺度社区优先用结构主图加尺度曲线。",
            }
        if "temporal" in semantics or "dynamic community" in semantics or "社区" in data_semantics:
            return {
                "family": "temporal_network",
                "preferred": ["temporal_network", "community_timeline", "network_topology"],
                "avoid": ["vertical_bar"],
                "reason": "动态社区和时序网络需要时间轴或时间窗表达。",
            }
        return {
            "family": "network_curve",
            "preferred": ["network_topology", "percolation_curve", "resilience_curve"],
            "avoid": ["vertical_bar"],
            "reason": "网络任务默认采用结构图加曲线图。",
        }
    if task == "spatiotemporal":
        return {
            "family": "chronological_network",
            "preferred": ["chronological_network", "grid_heatmap", "summary_curve"],
            "avoid": ["vertical_bar"],
            "reason": "时空任务优先空间视图、网络视图和摘要图配对。",
        }
    if task == "temporal":
        family = "bursty_activity" if "burst" in semantics or "inter-event" in semantics or "bursty" in semantics else "line_band"
        return {
            "family": family,
            "preferred": ["bursty_activity", "timeline_curve", "distribution_curve"],
            "avoid": ["vertical_bar"],
            "reason": "时序活动优先事件过程和分布图，而不是频次柱图。",
        }
    if task == "spatial":
        return {
            "family": "contour_quiver",
            "preferred": ["contour", "heatmap", "quiver"],
            "avoid": ["vertical_bar"],
            "reason": "空间任务需要表达连续场而不是离散柱高。",
        }
    if task == "dynamics":
        return {
            "family": "phase_portrait",
            "preferred": ["phase_portrait", "trajectory", "vector_field"],
            "avoid": ["vertical_bar"],
            "reason": "动力系统优先相图与轨迹图。",
        }
    if task == "evolution":
        return {
            "family": "line_band",
            "preferred": ["line_band", "multi_line", "stacked_area"],
            "avoid": ["vertical_bar"],
            "reason": "过程变化默认用趋势线和置信带。",
        }
    if task == "comparison":
        if "causal" in semantics or "snr" in semantics:
            return {
                "family": "multi_line",
                "preferred": ["multi_line", "interval_plot", "lollipop"],
                "avoid": ["vertical_bar"],
                "reason": "因果效应和 SNR 变化更适合多方法折线比较。",
            }
        family = "interval_plot" if need_uncertainty else "lollipop"
        return {
            "family": family,
            "preferred": ["lollipop", "dot_plot", "forest", "interval_plot"],
            "avoid": ["vertical_bar"],
            "reason": "比较任务默认用排序点图或区间图。",
        }
    if task == "mechanism":
        return {
            "family": "hero_support",
            "preferred": ["hero_support", "schematic_plus_quant"],
            "avoid": [],
            "reason": "机制类任务默认采用主图加支撑图组合。",
        }
    if task == "flowchart":
        return {
            "family": "flowchart",
            "preferred": ["flowchart"],
            "avoid": [],
            "reason": "流程类非数据图由项目锁定的 Draw.io / AI 链路处理。",
        }
    return {
        "family": "line_band" if need_uncertainty else "lollipop",
        "preferred": ["line_band", "lollipop", "interval_plot"],
        "avoid": ["vertical_bar"],
        "reason": "未识别任务时，优先选择信息密度更高的非柱图。",
    }


def compose_multi_panel(
    layout_mode: str,
    panel_specs: list[str] | None = None,
    width_mm: float = NATURE_WIDTH_MM["double"],
    height_mm: float = 130,
):
    apply_py_nature_style()
    fig = plt.figure(figsize=(mm_to_inch(width_mm), mm_to_inch(height_mm)))
    axes: dict[str, plt.Axes] = {}
    panel_specs = panel_specs or []

    if layout_mode == "hero_top_support_bottom":
        gs = fig.add_gridspec(2, 4, height_ratios=[2.2, 1.1], hspace=0.28, wspace=0.35)
        axes["hero"] = fig.add_subplot(gs[0, :])
        for idx in range(3):
            axes[f"support_{idx+1}"] = fig.add_subplot(gs[1, idx])
        axes["legend"] = fig.add_subplot(gs[1, 3])
        axes["legend"].set_axis_off()
    elif layout_mode == "right_hero_stack":
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.35)
        axes["support_1"] = fig.add_subplot(gs[0, :2])
        axes["support_2"] = fig.add_subplot(gs[1, :2])
        axes["support_3"] = fig.add_subplot(gs[2, :2])
        axes["hero"] = fig.add_subplot(gs[:, 2:])
    elif layout_mode == "single_row_with_legend":
        n = max(3, len(panel_specs) + 1)
        gs = fig.add_gridspec(1, n, wspace=0.35)
        for idx in range(n - 1):
            axes[f"panel_{idx+1}"] = fig.add_subplot(gs[0, idx])
        axes["legend"] = fig.add_subplot(gs[0, n - 1])
        axes["legend"].set_axis_off()
    elif layout_mode == "single_column_stack":
        n = max(2, len(panel_specs) or 3)
        gs = fig.add_gridspec(n, 1, hspace=0.26)
        for idx in range(n):
            axes[f"panel_{idx+1}"] = fig.add_subplot(gs[idx, 0])
    elif layout_mode == "network_hero_curve_stack":
        gs = fig.add_gridspec(2, 3, width_ratios=[1.45, 1.0, 1.0], hspace=0.30, wspace=0.35)
        axes["hero"] = fig.add_subplot(gs[:, 0])
        axes["support_1"] = fig.add_subplot(gs[0, 1:])
        axes["support_2"] = fig.add_subplot(gs[1, 1:])
    elif layout_mode == "map_network_summary":
        gs = fig.add_gridspec(2, 2, height_ratios=[1.1, 1.0], hspace=0.28, wspace=0.28)
        axes["map"] = fig.add_subplot(gs[:, 0])
        axes["network"] = fig.add_subplot(gs[0, 1])
        axes["summary"] = fig.add_subplot(gs[1, 1])
    else:
        gs = fig.add_gridspec(2, 2, hspace=0.28, wspace=0.32)
        axes["panel_1"] = fig.add_subplot(gs[0, 0])
        axes["panel_2"] = fig.add_subplot(gs[0, 1])
        axes["panel_3"] = fig.add_subplot(gs[1, 0])
        axes["panel_4"] = fig.add_subplot(gs[1, 1])

    return fig, axes


def add_panel_label(ax, label: str, x: float = -0.06, y: float = 1.02, color: str | None = None) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=8,
        fontweight="bold",
        color=color or PALETTE["black"],
        ha="left",
        va="bottom",
    )


def save_py_nature_figure(
    fig,
    out_base: str | Path,
    dpi: int = 300,
    formats: tuple[str, ...] = ALLOWED_FORMATS,
    profile: str = "competition_cn",
) -> list[Path]:
    profile = normalize_profile(profile)
    out_base = Path(out_base)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    if out_base.suffix:
        out_base = out_base.with_suffix("")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig.tight_layout(pad=1.2)
    saved = []
    for fmt in formats:
        target = out_base.with_suffix(f".{fmt}")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            save_options = {} if profile == "research" else {"bbox_inches": "tight"}
            fig.savefig(target, dpi=dpi, **save_options)
        saved.append(target)
    plt.close(fig)
    return saved


def run_py_nature_qa(fig_path_or_fig_object, profile: str = "competition_cn") -> QAResult:
    profile = normalize_profile(profile)
    if hasattr(fig_path_or_fig_object, "savefig"):
        checks = {
            "profile": profile,
            "fig_object": True,
            "export_preflight_complete": False,
            "font_profile_ok": _font_profile_configured(profile),
            "cn_text_ok": _cn_font_configured() if profile == "competition_cn" else True,
            "research_preflight_ok": False,
            "issues": ["内存 Figure 尚未完成导出预检。"],
        }
        return QAResult(profile != "research" and checks["font_profile_ok"], checks)

    base = Path(fig_path_or_fig_object)
    if base.suffix:
        stems = [base]
    else:
        stems = [base.with_suffix(".svg"), base.with_suffix(".pdf"), base.with_suffix(".png")]

    checks = {
        "svg_exists": False,
        "pdf_exists": False,
        "png_exists": False,
        "svg_parse_ok": False,
        "svg_has_text_nodes": False,
        "editable_text_ok": False,
        "png_nonempty": False,
        "pdf_nonempty": False,
        "svg_color_count_reasonable": False,
        "cn_font_configured": _cn_font_configured(),
        "profile": profile,
        "export_ok": False,
        "export_preflight_complete": False,
        "font_profile_ok": False,
        "canvas_size_ok": profile != "research",
        "research_font_size_ok": profile != "research",
        "research_preflight_ok": False,
        "issues": [],
    }

    for item in stems:
        if item.suffix == ".svg":
            checks["svg_exists"] = item.exists()
            if item.exists():
                root = ET.parse(item).getroot()
                checks["svg_parse_ok"] = True
                checks["svg_has_text_nodes"] = any(node.tag.endswith("text") for node in root.iter())
                checks["editable_text_ok"] = checks["svg_has_text_nodes"]
                color_count = _svg_distinct_color_count(item)
                checks["svg_color_count_reasonable"] = 1 <= color_count <= 128
                svg_text = item.read_text(encoding="utf-8", errors="ignore")
                checks["font_profile_ok"] = _svg_font_profile_ok(svg_text, profile)
                if profile == "research":
                    checks["canvas_size_ok"] = _svg_canvas_width_ok(root)
                    font_ok, font_issues = _research_svg_font_sizes(root)
                    checks["research_font_size_ok"] = font_ok
                    checks["issues"].extend(font_issues)
        elif item.suffix == ".pdf":
            checks["pdf_exists"] = item.exists()
            checks["pdf_nonempty"] = item.exists() and item.stat().st_size > 1024
        elif item.suffix == ".png":
            checks["png_exists"] = item.exists()
            checks["png_nonempty"] = item.exists() and item.stat().st_size > 1024

    checks["export_ok"] = bool(
        checks["svg_exists"] and checks["pdf_exists"] and checks["png_exists"]
        and checks["svg_parse_ok"] and checks["png_nonempty"] and checks["pdf_nonempty"]
    )
    checks["export_preflight_complete"] = checks["export_ok"]
    checks["cn_text_ok"] = checks["font_profile_ok"] if profile == "competition_cn" else True
    checks["research_preflight_ok"] = bool(
        profile == "research"
        and checks["export_ok"]
        and checks["editable_text_ok"]
        and checks["font_profile_ok"]
        and checks["canvas_size_ok"]
        and checks["research_font_size_ok"]
    )
    required = [
        "export_ok", "editable_text_ok", "font_profile_ok",
        "svg_color_count_reasonable", "cn_text_ok",
    ]
    if profile == "research":
        required.append("research_preflight_ok")
    passed = all(bool(checks[key]) for key in required)
    return QAResult(passed, checks)


def _hide_ticks(ax):
    ax.tick_params(axis="both", which="both", length=0)


def make_trend_with_band(ax, x, ys, labels, colors, xlabel: str, ylabel: str):
    for y, label, color in zip(ys, labels, colors):
        y = np.asarray(y)
        mean = y.mean(axis=0) if y.ndim == 2 else y
        std = y.std(axis=0) if y.ndim == 2 else np.full_like(mean, 0.0, dtype=float)
        ax.plot(x, mean, color=color, lw=1.8, marker="o", ms=3.2, label=label)
        ax.fill_between(x, mean - std, mean + std, color=color, alpha=0.16)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)


def make_tornado_plot(ax, labels, impacts, baseline: float = 0.0):
    order = np.argsort(np.abs(impacts))
    labels = np.asarray(labels)[order]
    impacts = np.asarray(impacts)[order]
    y = np.arange(len(labels))
    colors = [PALETTE["red_strong"] if value < baseline else PALETTE["blue_main"] for value in impacts]
    ax.hlines(y, baseline, impacts, color=colors, linewidth=2.2)
    ax.scatter(impacts, y, s=28, color=colors, zorder=3)
    ax.axvline(baseline, color=PALETTE["neutral_mid"], linestyle="--", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("灵敏度影响量")


def make_heatmap(ax, matrix, x_labels, y_labels, cmap: str = "magma"):
    matrix = np.asarray(matrix)
    im = ax.imshow(matrix, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=30, ha="right")
    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels)
    ax.figure.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
    return im


def make_pareto_plot(ax, points, is_frontier):
    points = np.asarray(points)
    mask = np.asarray(is_frontier, dtype=bool)
    ax.scatter(points[~mask, 0], points[~mask, 1], s=24, color=PALETTE["neutral_mid"], alpha=0.7, label="候选方案")
    ax.scatter(points[mask, 0], points[mask, 1], s=34, color=PALETTE["orange_main"], label="Pareto 前沿")
    frontier = points[mask]
    frontier = frontier[np.argsort(frontier[:, 0])]
    ax.plot(frontier[:, 0], frontier[:, 1], color=PALETTE["orange_main"], linewidth=1.8)
    ax.set_xlabel("目标 1")
    ax.set_ylabel("目标 2")


def make_interval_plot(ax, labels, centers, lows, highs):
    y = np.arange(len(labels))[::-1]
    ax.hlines(y, lows, highs, color=PALETTE["blue_main"], linewidth=2)
    ax.scatter(centers, y, color=PALETTE["orange_main"], s=24, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("估计值与区间")


def make_lollipop_plot(ax, labels, values):
    order = np.argsort(values)
    labels = np.asarray(labels)[order]
    values = np.asarray(values)[order]
    y = np.arange(len(labels))
    ax.hlines(y, 0, values, color=PALETTE["neutral_mid"], linewidth=1.8)
    ax.scatter(values, y, color=PALETTE["blue_main"], s=26)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("综合得分")


def make_network_topology(ax):
    angles = np.linspace(0, 2 * math.pi, 10, endpoint=False)
    outer = np.column_stack([np.cos(angles), np.sin(angles)])
    inner = outer[:5] * 0.42
    points = np.vstack([outer, inner])
    edges = []
    for idx in range(10):
        edges.append((points[idx], points[(idx + 1) % 10]))
    for idx in range(5):
        edges.append((points[idx], points[10 + idx]))
        edges.append((points[10 + idx], points[10 + (idx + 1) % 5]))
    lc = LineCollection(edges, colors=PALETTE["neutral_mid"], linewidths=1.2)
    ax.add_collection(lc)
    ax.scatter(points[:10, 0], points[:10, 1], s=28, color=PALETTE["blue_secondary"], zorder=3)
    ax.scatter(points[10:, 0], points[10:, 1], s=28, color=PALETTE["orange_main"], zorder=3)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def make_network_curvature_panel(ax):
    angles = np.linspace(0, 2 * math.pi, 12, endpoint=False)
    outer = np.column_stack([np.cos(angles), np.sin(angles)])
    inner = outer[:6] * 0.46
    points = np.vstack([outer, inner, [[0.0, 0.0]]])
    edges = []
    values = []
    for idx in range(12):
        nxt = (idx + 1) % 12
        edges.append((points[idx], points[nxt]))
        values.append(np.sin(idx / 2.2))
    for idx in range(6):
        edges.append((points[idx * 2], points[12 + idx]))
        values.append(-0.65 + idx * 0.22)
        edges.append((points[12 + idx], points[-1]))
        values.append(0.25 + idx * 0.12)
    values = np.asarray(values)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "curvature_band",
        [PALETTE["curvature_low"], PALETTE["curvature_mid"], PALETTE["curvature_high"]],
    )
    lc = LineCollection(edges, array=values, cmap=cmap, linewidths=1.8)
    ax.add_collection(lc)
    ax.scatter(points[:12, 0], points[:12, 1], s=30, color=PALETTE["slate_dark"], zorder=3)
    ax.scatter(points[12:-1, 0], points[12:-1, 1], s=30, color=PALETTE["cyan_main"], zorder=3)
    ax.scatter(points[-1, 0], points[-1, 1], s=40, color=PALETTE["gold_main"], zorder=3)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return lc


def make_chronological_network_panel(ax):
    grid_x, grid_y = np.meshgrid(np.arange(4), np.arange(4))
    coords = np.column_stack([grid_x.ravel(), grid_y.ravel()]).astype(float)
    coords[:, 0] = coords[:, 0] / 3.0
    coords[:, 1] = coords[:, 1] / 3.0
    sequence = [0, 1, 5, 6, 10, 11, 15]
    for idx, (x, y) in enumerate(coords):
        color = PALETTE["spatial_focus"] if idx in sequence else PALETTE["neutral_light"]
        ax.scatter(x, y, s=70, color=color, edgecolor="white", linewidth=0.6, zorder=3)
    for start, end in zip(sequence[:-1], sequence[1:]):
        arrow = FancyArrowPatch(
            coords[start],
            coords[end],
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=1.2,
            color=PALETTE["blue_secondary"],
            alpha=0.9,
        )
        ax.add_patch(arrow)
    ax.set_xlim(-0.08, 1.08)
    ax.set_ylim(-0.08, 1.08)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def make_bursty_activity(ax, seed: int = 13):
    rng = np.random.default_rng(seed)
    t = np.arange(1, 161)
    baseline = 0.38 + 0.02 * np.sin(t / 8)
    bursts = baseline.copy()
    spike_points = [22, 48, 51, 91, 122, 124, 125, 146]
    for point in spike_points:
        bursts[point - 1 : min(point + 2, len(bursts))] += rng.uniform(0.18, 0.35)
    ax.plot(t, bursts, color=PALETTE["temporal_focus"], lw=1.8, label="突发强度")
    ax.plot(t, baseline, color=PALETTE["neutral_mid"], lw=1.2, linestyle="--", label="平滑基线")
    ax.set_xlabel("时间步")
    ax.set_ylabel("活动强度")
    return np.array(spike_points)


def make_inter_event_ccdf(ax):
    tau = np.arange(1, 26)
    empirical = np.exp(-(tau / 9.0) ** 0.72)
    poisson = np.exp(-tau / 6.5)
    ax.plot(tau, empirical, color=PALETTE["orange_main"], lw=1.8, marker="o", ms=3.5, label="突发网络")
    ax.plot(tau, poisson, color=PALETTE["neutral_mid"], lw=1.5, linestyle="--", label="泊松基线")
    ax.set_xlabel("间隔长度")
    ax.set_ylabel("CCDF")


def _cn_font_configured() -> bool:
    fonts = plt.rcParams.get("font.sans-serif", [])
    return any(font in fonts for font in ["Microsoft YaHei", "SimHei"])


def _font_profile_configured(profile: str) -> bool:
    fonts = list(plt.rcParams.get("font.sans-serif", []))
    preferred = PROFILE_FONTS[profile][:2]
    return bool(fonts) and any(font in fonts[:2] for font in preferred)


def _svg_font_profile_ok(svg_text: str, profile: str) -> bool:
    preferred = PROFILE_FONTS[profile][:]
    return any(font.lower() in svg_text.lower() for font in preferred if font != "sans-serif")


def _svg_length_to_mm(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9.]+)\s*(mm|cm|in|pt|px)?\s*", value)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or "px"
    return number * {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72.0, "px": 25.4 / 96.0}[unit]


def _svg_canvas_width_ok(root: ET.Element, tolerance_mm: float = 1.5) -> bool:
    width_mm = _svg_length_to_mm(root.attrib.get("width"))
    return width_mm is not None and any(abs(width_mm - expected) <= tolerance_mm for expected in NATURE_WIDTH_MM.values())


def _research_svg_font_sizes(root: ET.Element) -> tuple[bool, list[str]]:
    issues: list[str] = []
    for node in root.iter():
        if not node.tag.endswith("text"):
            continue
        style = node.attrib.get("style", "")
        size_value = node.attrib.get("font-size")
        if not size_value:
            match = re.search(r"font(?:-size)?\s*:\s*([0-9.]+)\s*(px|pt)?", style)
            size_value = "".join(match.groups(default="")) if match else None
        size_pt = _svg_font_size_to_pt(size_value)
        label = "".join(node.itertext()).strip()
        weight = (node.attrib.get("font-weight", "") + " " + style).lower()
        panel_label = bool(re.fullmatch(r"[a-z]", label)) and ("bold" in weight or "700" in weight)
        if size_pt is None:
            issues.append(f"无法解析字号: {label[:20] or '<空文本>'}")
        elif not (5.0 <= size_pt <= 7.0 or (panel_label and abs(size_pt - 8.0) <= 0.15)):
            issues.append(f"科研字号越界: {label[:20] or '<空文本>'}={size_pt:.2f} pt")
    return not issues, issues


def _svg_font_size_to_pt(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*([0-9.]+)\s*(px|pt)?\s*", value)
    if not match:
        return None
    number = float(match.group(1))
    # Matplotlib writes its point-sized text as SVG px values in the same user-unit scale.
    return number


def _svg_distinct_color_count(svg_path: Path) -> int:
    text = svg_path.read_text(encoding="utf-8", errors="ignore")
    colors = set(re.findall(r"#[0-9A-Fa-f]{6}", text))
    return len(colors)


def make_phase_portrait(ax, xlim=(-2.5, 2.5), ylim=(-2.5, 2.5)):
    x = np.linspace(*xlim, 22)
    y = np.linspace(*ylim, 22)
    X, Y = np.meshgrid(x, y)
    U = Y
    V = -0.8 * X - 0.35 * Y + 0.3 * X * (1 - X**2 / 4)
    ax.streamplot(X, Y, U, V, color=PALETTE["neutral_mid"], density=1.1, linewidth=0.8)
    t = np.linspace(0, 14, 220)
    traj_x = 1.7 * np.cos(t / 2.5) * np.exp(-t / 12)
    traj_y = 1.4 * np.sin(t / 2.0) * np.exp(-t / 12)
    ax.plot(traj_x, traj_y, color=PALETTE["blue_main"], linewidth=2.0)
    ax.scatter([0], [0], color=PALETTE["red_strong"], s=32, zorder=3)
    ax.set_xlabel("状态 x")
    ax.set_ylabel("状态 y")


def make_spatial_contour(ax, with_quiver: bool = True):
    x = np.linspace(-3, 3, 160)
    y = np.linspace(-3, 3, 160)
    X, Y = np.meshgrid(x, y)
    Z = np.exp(-(X**2 + Y**2) / 4) + 0.35 * np.sin(2 * X) * np.cos(1.5 * Y)
    contour = ax.contourf(X, Y, Z, levels=10, cmap="viridis")
    if with_quiver:
        xq = np.linspace(-2.5, 2.5, 12)
        yq = np.linspace(-2.5, 2.5, 12)
        Xq, Yq = np.meshgrid(xq, yq)
        Uq = -Yq / 4
        Vq = Xq / 4
        ax.quiver(Xq, Yq, Uq, Vq, color="white", alpha=0.7, scale=12)
    ax.figure.colorbar(contour, ax=ax, fraction=0.05, pad=0.03)
    ax.set_xlabel("空间 x")
    ax.set_ylabel("空间 y")
    return contour
