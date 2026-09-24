from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import fig_common as fc

PALETTE = fc.PALETTE
OUT = PROJECT / "灵敏度分析"
FIG = OUT / "figures"


def load_indices() -> dict:
    return json.loads((OUT / "sensitivity_indices.json").read_text(encoding="utf-8"))


def load_q2_report() -> dict:
    return json.loads((PROJECT / "Q2" / "results" / "q2_report.json").read_text(encoding="utf-8"))


def load_local() -> dict:
    return json.loads((OUT / "local_sensitivity.json").read_text(encoding="utf-8"))


def tornado_panel(ax, rows, baseline, scenario: str, title: str) -> None:
    labels = []
    for item in rows:
        if item["参数"] not in labels:
            labels.append(item["参数"])
    y = np.arange(len(labels))[::-1]
    fc.soften(ax, "x")
    base_mae = baseline["mae"]
    tick_labels = []
    for index, label in enumerate(labels):
        subset = [item for item in rows if item["参数"] == label and item["场景"] == scenario]
        span = [min(item["强度平均绝对误差"] for item in subset),
                max(item["强度平均绝对误差"] for item in subset)]
        color = (PALETTE["red_strong"] if span[1] - base_mae > base_mae - span[0]
                 else PALETTE["blue_main"])
        ax.hlines(y[index], span[0], span[1], color=color, lw=3.4, alpha=0.9, zorder=2)
        ax.scatter(span, [y[index]] * 2, color=color, s=24, zorder=3,
                   edgecolor="white", linewidth=0.5)
        tick_labels.append(f"{label}\n{span[0]:.4f}–{span[1]:.4f}")
    ax.axvline(base_mae, color=PALETTE["slate_dark"], linestyle="--", lw=1.0, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=5.8, linespacing=1.5)
    ax.set_ylim(-0.7, len(labels) - 0.3)
    ax.set_title(title, fontsize=7.2, pad=6)


def fig_sens_01_local_tornado() -> dict:
    data = load_local()
    rows = data["rows"]
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(92)))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.0], wspace=0.46)
    fig.subplots_adjust(left=0.14, right=0.98, bottom=0.20, top=0.90)

    ax = fig.add_subplot(grid[0, 0])
    tornado_panel(ax, rows, data["clean_baseline"], "无缺失基线",
                  "(a) 无缺失基线下的参数端点效应")
    ax.set_xlabel("情感强度平均绝对误差")
    ax.annotate(f"基线 {data['clean_baseline']['mae']:.4f}",
                xy=(data["clean_baseline"]["mae"], -0.4),
                xytext=(4, 0), textcoords="offset points", fontsize=5.9,
                color=PALETTE["slate_dark"], va="center")

    ax = fig.add_subplot(grid[0, 1])
    tornado_panel(ax, rows, data["missing_baseline"], "三模态均缺失 35%",
                  "(b) 三模态均缺失 35% 下的参数端点效应")
    ax.set_xlabel("情感强度平均绝对误差")
    ax.annotate(f"基线 {data['missing_baseline']['mae']:.4f}",
                xy=(data["missing_baseline"]["mae"], -0.4),
                xytext=(4, 0), textcoords="offset points", fontsize=5.9,
                color=PALETTE["slate_dark"], va="center")
    fig.text(0.5, 0.028,
             "每行左侧为参数名与其上下界取值下的误差区间；线段越长表示该参数影响越大。"
             "无缺失基线下缺失类参数几乎不改变误差，只有已存在缺失时区间长度与区间数才产生可测影响",
             ha="center", fontsize=6.2, color=PALETTE["slate_dark"])
    return fc.save(fig, "fig_sens_01_local_tornado", FIG)


def fig_sens_02_sobol_heatmap() -> dict:
    """四面板敏感度总图：参数影响区间、缺失率退化曲线、缺失时长效应、联合响应面。"""
    local = load_local()
    report = load_q2_report()
    surface = json.loads((OUT / "joint_surface.json").read_text(encoding="utf-8"))
    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(210), fc.mm_to_inch(142)))
    grid = fig.add_gridspec(2, 2, width_ratios=[1.10, 1.0], height_ratios=[1.0, 1.0],
                            wspace=0.46, hspace=0.50)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "x")
    rows = local["rows"]
    labels = []
    for item in rows:
        if item["参数"] not in labels:
            labels.append(item["参数"])
    y = np.arange(len(labels))[::-1]
    base_mae = local["missing_baseline"]["mae"]
    for index, label in enumerate(labels):
        subset = [item for item in rows if item["参数"] == label and item["场景"] == "三模态均缺失 35%"]
        span = [min(item["强度平均绝对误差"] for item in subset),
                max(item["强度平均绝对误差"] for item in subset)]
        color = (PALETTE["red_strong"] if span[1] - base_mae > base_mae - span[0]
                 else PALETTE["blue_main"])
        ax.hlines(y[index], span[0], span[1], color=color, lw=3.2, alpha=0.9, zorder=2)
        ax.scatter(span, [y[index]] * 2, color=color, s=22, zorder=3,
                   edgecolor="white", linewidth=0.4)
        ax.annotate(f"{span[1] - span[0]:.4f}", xy=(span[1], y[index]),
                    xytext=(7, 0), textcoords="offset points", fontsize=5.8,
                    va="center", color=color)
    ax.axvline(base_mae, color=PALETTE["slate_dark"], linestyle="--", lw=1.0, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6.0)
    ax.set_xlim(base_mae - 0.008, max(item["强度平均绝对误差"] for item in rows) + 0.012)
    ax.set_ylim(-0.7, len(labels) - 0.3)
    ax.set_xlabel("情感强度平均绝对误差（基线 " + f"{base_mae:.4f}" + "，右侧数字为影响幅度）")
    ax.set_title("(a) 参数影响幅度（线段长度即误差变化范围）", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "y")
    series = [("all", report["missing_rate_all"], PALETTE["slate_dark"], "全模态同时缺失")]
    for modality, name, color in (("text", "文本", PALETTE["blue_main"]),
                                  ("audio", "语音", PALETTE["orange_main"]),
                                  ("vision", "视觉", PALETTE["teal_main"])):
        series.append((modality, report["missing_rate_single"][modality], color, f"仅缺失{name}"))
    for key, rows_rate, color, label in series:
        xs = np.asarray([item["missing_ratio"] for item in rows_rate]) * 100
        ys = np.asarray([item["mae"] for item in rows_rate])
        ax.plot(xs, ys, marker="o", ms=3.6, lw=1.6, color=color, label=label, zorder=3)
    ax.set_xlabel("缺失率 / %")
    ax.set_ylabel("情感强度平均绝对误差")
    ax.set_xlim(-3, 73)
    ax.set_title("(b) 缺失率对强度误差的影响", fontsize=7.2, pad=6)
    ax.legend(loc="upper left", handlelength=1.4, fontsize=5.9)

    ax = fig.add_subplot(grid[1, 0])
    fc.soften(ax, "y")
    for modality, name, color, marker in (("text", "文本", PALETTE["blue_main"], "o"),
                                          ("audio", "语音", PALETTE["orange_main"], "s"),
                                          ("vision", "视觉", PALETTE["teal_main"], "^")):
        subset = [item for item in report["missing_position"] if item["modality"] == modality]
        grouped = {}
        for item in subset:
            grouped.setdefault(item["window_length"], []).append(item["mae"])
        xs = sorted(grouped)
        ys = [float(np.mean(grouped[key])) for key in xs]
        errs = [float(np.std(grouped[key])) for key in xs]
        ax.errorbar(xs, ys, yerr=errs, marker=marker, ms=3.8, lw=1.6, capsize=2.4,
                    elinewidth=0.8, color=color, label=name, zorder=3)
    ax.set_xlabel("缺失时长 / 位置")
    ax.set_ylabel("情感强度平均绝对误差")
    ax.set_title("(c) 缺失时长对强度误差的影响", fontsize=7.2, pad=6)
    ax.legend(loc="upper left", handlelength=1.4, fontsize=5.9)

    ax = fig.add_subplot(grid[1, 1], projection="3d")
    text_ratios = np.asarray(surface["text_ratios"]) * 100
    z = np.asarray(surface["robust_score"])
    grid_x, grid_y = np.meshgrid(text_ratios, np.asarray(surface["audio_ratios"]) * 100,
                                 indexing="ij")
    surf = ax.plot_surface(grid_x, grid_y, z, cmap="cividis", edgecolor="none", alpha=0.95,
                           antialiased=True, rstride=1, cstride=1)
    ax.set_xlabel("文本缺失率 / %", fontsize=6.2, labelpad=0)
    ax.set_ylabel("语音缺失率 / %", fontsize=6.2, labelpad=0)
    ax.set_zlabel("稳健得分", fontsize=6.2, labelpad=1)
    ax.tick_params(labelsize=5.2, pad=-1)
    ax.view_init(elev=24, azim=-130)
    ax.set_title("(d) 文本与语音缺失率的联合响应面", fontsize=7.2, pad=2)
    bar = fig.colorbar(surf, ax=ax, fraction=0.032, pad=0.09, shrink=0.72)
    bar.set_label("稳健得分", fontsize=6.0)
    bar.ax.tick_params(labelsize=5.6)
    worst = np.unravel_index(int(np.argmin(z)), z.shape)
    ax.scatter([grid_x[worst]], [grid_y[worst]], [z[worst]], color=PALETTE["red_strong"],
               s=40, marker="X", depthshade=False, zorder=6)
    return fc.save(fig, "fig_sens_02_sobol_heatmap", FIG)


def fig_sens_03_joint_surface() -> dict:
    """敏感度补充图：无缺失与有缺失两种基线下的参数端点效应对比。"""
    local = load_local()
    rows = local["rows"]
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(84)))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.0], wspace=0.36)

    ax = fig.add_subplot(grid[0, 0])
    tornado_panel(ax, rows, local["clean_baseline"], "无缺失基线",
                  "(a) 无缺失基线下的参数端点效应")
    ax.set_xlabel("情感强度平均绝对误差（线段端点为参数上下界取值）")

    ax = fig.add_subplot(grid[0, 1])
    tornado_panel(ax, rows, local["missing_baseline"], "三模态均缺失 35%",
                  "(b) 三模态均缺失 35% 下的参数端点效应")
    ax.set_xlabel("情感强度平均绝对误差（线段端点为参数上下界取值）")
    fig.text(0.5, 0.015,
             "空心圆为参数下界、实心圆为上界；无缺失基线下缺失类参数几乎不改变误差，"
             "只有已存在缺失时区间长度与区间数才产生可测影响",
             ha="center", fontsize=6.2, color=PALETTE["slate_dark"])
    return fc.save(fig, "fig_sens_03_joint_surface", FIG)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    reports = [fig_sens_01_local_tornado(), fig_sens_02_sobol_heatmap(), fig_sens_03_joint_surface()]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
