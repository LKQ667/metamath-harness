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
C = fc.MODALITY_COLORS
OUT = PROJECT / "Q2"
FIG = OUT / "figures"
RESULTS = OUT / "results"
DATA = PROJECT / "data" / "processed"
POLARITY_CN = ("负向", "中性", "正向")
MISSING_COLORS = {
    "all": PALETTE["slate_dark"],
    "text": PALETTE["blue_main"],
    "audio": PALETTE["orange_main"],
    "vision": PALETTE["teal_main"],
}
MISSING_LABELS = {"all": "全模态同时缺失", "text": "仅缺失文本", "audio": "仅缺失语音", "vision": "仅缺失视觉"}


def load_report() -> dict:
    return json.loads((RESULTS / "q2_report.json").read_text(encoding="utf-8"))


def fig_q2_01_missing_pattern() -> dict:
    import pandas as pd

    frame = pd.read_csv(DATA / "a3_missing_mask.csv")
    samples = frame["sample"].tolist()
    matrix = np.zeros((3 * len(samples), 50), dtype=float)
    for row, (_, item) in enumerate(frame.iterrows()):
        for modality_index, modality in enumerate(("text", "audio", "vision")):
            segments = json.loads(item[f"{modality}_missing_segments"])
            for start, end in segments:
                matrix[modality_index * len(samples) + row, start:end + 1] = 1.0

    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(92)))
    grid = fig.add_gridspec(1, 4, width_ratios=[1.35, 0.62, 0.62, 0.62], wspace=0.30)

    ax = fig.add_subplot(grid[0, 0])
    cmap = matplotlib.colors.ListedColormap(["#F2F2F2", PALETTE["red_strong"]])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, interpolation="nearest",
                   extent=[0, 50, matrix.shape[0], 0])
    ax.set_xlabel("序列位置")
    ax.set_ylabel("样本 × 模态（按模态分块）")
    ax.set_title("(a) 附件 3 缺失位置矩阵（红色为缺失）", fontsize=7.2, pad=6)
    ax.set_xticks([0, 10, 20, 30, 40, 50])
    for boundary in (len(samples), 2 * len(samples)):
        ax.axhline(boundary, color=PALETTE["neutral_dark"], lw=1.0)
    for index, name in enumerate(("文本", "语音", "视觉")):
        ax.text(53.5, (index + 0.5) * len(samples), name, fontsize=6.4, va="center",
                color=(C["文本"], C["语音"], C["视觉"])[index])
    cax = fig.add_axes([0.318, 0.19, 0.009, 0.26])
    bar = fig.colorbar(im, cax=cax, ticks=[0, 1])
    bar.ax.set_yticklabels(["有效", "缺失"], fontsize=5.6)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "y")
    ratios = {m: frame[f"{m}_missing_ratio"].values * 100 for m in ("text", "audio", "vision")}
    bins = np.arange(0, 105, 10)
    for name, key, color, marker in (("文本", "text", C["文本"], "o"),
                                     ("语音", "audio", C["语音"], "s"),
                                     ("视觉", "vision", C["视觉"], "^")):
        counts, edges = np.histogram(ratios[key], bins=bins)
        ax.plot(0.5 * (edges[:-1] + edges[1:]), counts, marker=marker, ms=3.4, lw=1.5,
                color=color, label=name, zorder=3)
    ax.set_xlabel("缺失率 / %")
    ax.set_ylabel("样本数 / 条")
    ax.set_title("(b) 缺失率分布", fontsize=7.0, pad=6)
    ax.legend(loc="upper left", handlelength=1.2, fontsize=5.9)
    ax.set_xlim(-4, 96)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    segment_lengths = {"text": [], "audio": [], "vision": []}
    segment_counts = {"text": [], "audio": [], "vision": []}
    for _, item in frame.iterrows():
        for modality in ("text", "audio", "vision"):
            segments = json.loads(item[f"{modality}_missing_segments"])
            segment_lengths[modality].extend([end - start + 1 for start, end in segments])
            segment_counts[modality].append(len(segments))
    bins = np.arange(0.5, 32.5, 2.0)
    for name, key, color, marker in (("文本", "text", C["文本"], "o"),
                                     ("语音", "audio", C["语音"], "s"),
                                     ("视觉", "vision", C["视觉"], "^")):
        counts, edges = np.histogram(segment_lengths[key], bins=bins)
        ax.plot(0.5 * (edges[:-1] + edges[1:]), counts, marker=marker, ms=3.4, lw=1.5,
                color=color, label=f"{name}（中位 {np.median(segment_lengths[key]):.0f}）", zorder=3)
    ax.set_xlabel("单个连续缺失区间长度 / 位置")
    ax.set_ylabel("区间数 / 个")
    ax.set_title("(c) 连续缺失区间长度", fontsize=7.0, pad=6)
    ax.legend(loc="upper right", handlelength=1.2, fontsize=5.7)

    ax = fig.add_subplot(grid[0, 3])
    fc.soften(ax, "y")
    x = np.arange(3)
    means = [np.mean(segment_counts[key]) for key in ("text", "audio", "vision")]
    medians = [np.median(segment_counts[key]) for key in ("text", "audio", "vision")]
    for index, (name, color) in enumerate((("文本", C["文本"]), ("语音", C["语音"]), ("视觉", C["视觉"]))):
        ax.hlines(index, 0, means[index], color=color, lw=2.4, zorder=2)
        ax.scatter([means[index]], [index], color=color, s=34, zorder=3)
        ax.scatter([medians[index]], [index], color="white", s=26, zorder=4,
                   edgecolor=color, linewidth=1.1)
        ax.annotate(f"均值 {means[index]:.2f}", xy=(means[index], index), xytext=(6, -1),
                    textcoords="offset points", fontsize=5.9, color=color, va="center")
    fc.soften(ax, "x")
    ax.set_yticks(x)
    ax.set_yticklabels(("文本", "语音", "视觉"))
    ax.set_xlabel("每样本连续缺失区间数 / 个")
    ax.set_xlim(0, max(means) * 1.55)
    ax.set_ylim(-0.7, 2.7)
    ax.set_title("(d) 缺失碎片化程度", fontsize=7.0, pad=6)
    ax.text(0.98, 0.06, "实心圆为均值\n空心圆为中位数", transform=ax.transAxes,
            fontsize=5.7, ha="right", va="bottom", color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    return fc.save(fig, "fig_q2_01_missing_pattern", FIG)


def fig_q2_02_rate_curves() -> dict:
    report = load_report()
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(78)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.0], wspace=0.36)

    series = [("all", report["missing_rate_all"])] + [
        (modality, report["missing_rate_single"][modality]) for modality in ("text", "audio", "vision")
    ]

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    for key, rows in series:
        x = np.asarray([item["missing_ratio"] for item in rows]) * 100
        y = np.asarray([item["accuracy"] for item in rows]) * 100
        yerr = np.asarray([item["accuracy_std"] for item in rows]) * 100
        ax.errorbar(x, y, yerr=yerr, marker="o", ms=3.6, lw=1.6, capsize=2.4, elinewidth=0.8,
                    color=MISSING_COLORS[key], label=MISSING_LABELS[key], zorder=3)
    ax.set_xlabel("缺失率 / %")
    ax.set_ylabel("情感极性准确率 / %")
    ax.set_title("(a) 缺失率对极性准确率的影响", fontsize=7.2, pad=6)
    ax.legend(loc="lower left", handlelength=1.5, fontsize=5.9)
    ax.set_xlim(-3, 73)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "y")
    for key, rows in series:
        x = np.asarray([item["missing_ratio"] for item in rows]) * 100
        y = np.asarray([item["macro_f1"] for item in rows]) * 100
        yerr = np.asarray([item["macro_f1_std"] for item in rows]) * 100
        ax.errorbar(x, y, yerr=yerr, marker="s", ms=3.6, lw=1.6, capsize=2.4, elinewidth=0.8,
                    color=MISSING_COLORS[key], label=MISSING_LABELS[key], zorder=3)
    ax.set_xlabel("缺失率 / %")
    ax.set_ylabel("宏平均 F1 / %")
    ax.set_title("(b) 缺失率对宏平均 F1 的影响", fontsize=7.2, pad=6)
    ax.set_xlim(-3, 73)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    for key, rows in series:
        x = np.asarray([item["missing_ratio"] for item in rows]) * 100
        y = np.asarray([item["mae"] for item in rows])
        yerr = np.asarray([item["mae_std"] for item in rows])
        ax.errorbar(x, y, yerr=yerr, marker="^", ms=3.6, lw=1.6, capsize=2.4, elinewidth=0.8,
                    color=MISSING_COLORS[key], label=MISSING_LABELS[key], zorder=3)
    ax.set_xlabel("缺失率 / %")
    ax.set_ylabel("情感强度平均绝对误差")
    ax.set_title("(c) 缺失率对强度误差的影响", fontsize=7.2, pad=6)
    ax.set_xlim(-3, 73)
    baseline = report["missing_rate_all"][0]["mae"]
    ax.axhline(baseline, color=PALETTE["neutral_mid"], linestyle="--", lw=0.9, zorder=1)
    ax.annotate(f"无缺失基线 {baseline:.4f}", xy=(36, baseline), xytext=(0, -14),
                textcoords="offset points", fontsize=5.9, color=PALETTE["neutral_dark"], ha="center")
    return fc.save(fig, "fig_q2_02_rate_curves", FIG)


def fig_q2_03_response_surface() -> dict:
    report = load_report()
    surface = report["response_surface"]["vision"]
    positions = np.asarray(surface["positions"], dtype=float)
    lengths = np.asarray(surface["lengths"], dtype=float)
    mae = np.asarray(surface["mae"], dtype=float)
    baseline = report["missing_rate_all"][0]["mae"]

    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(170), fc.mm_to_inch(120)))
    ax = fig.add_subplot(111, projection="3d")
    grid_x, grid_y = np.meshgrid(positions, lengths, indexing="ij")
    surf = ax.plot_surface(grid_x, grid_y, mae, cmap="viridis", edgecolor="none",
                           alpha=0.94, antialiased=True, rstride=1, cstride=1)
    ax.contour(grid_x, grid_y, mae, zdir="z", offset=mae.min() - 0.035, levels=8,
               cmap="viridis", linewidths=0.7)
    ax.set_xlabel("缺失起始位置", fontsize=6.6, labelpad=1)
    ax.set_ylabel("缺失时长 / 位置", fontsize=6.6, labelpad=1)
    ax.set_zlabel("情感强度平均绝对误差", fontsize=6.6, labelpad=1)
    ax.tick_params(labelsize=5.6, pad=-1)
    ax.view_init(elev=24, azim=-128)
    ax.set_title("视觉模态缺失位置与缺失时长的联合响应面", fontsize=8.0, pad=2)
    bar = fig.colorbar(surf, ax=ax, fraction=0.030, pad=0.10, shrink=0.72)
    bar.set_label("情感强度平均绝对误差", fontsize=6.4)
    bar.ax.tick_params(labelsize=5.8)
    worst = np.unravel_index(int(np.argmax(mae)), mae.shape)
    ax.scatter([positions[worst[0]]], [lengths[worst[1]]], [mae[worst]],
               color=PALETTE["red_strong"], s=42, marker="X", depthshade=False, zorder=6)
    ax.text(positions[worst[0]], lengths[worst[1]], mae[worst] + 0.02,
            f"最差组合：起始位置 {int(positions[worst[0]])}、时长 {int(lengths[worst[1]])}、误差 {mae[worst]:.4f}",
            fontsize=6.0, color=PALETTE["red_strong"])
    fig.text(0.5, 0.025,
             f"底投影为等值线；无缺失基线误差 {baseline:.4f}，响应面上所有组合的误差均高于基线，"
             "误差随时长增长而在序列中后段放大",
             ha="center", fontsize=6.2, color=PALETTE["slate_dark"])
    return fc.save(fig, "fig_q2_03_response_surface", FIG)


def fig_q2_04_contour_position() -> dict:
    report = load_report()
    surface = report["response_surface"]["vision"]
    positions = np.asarray(surface["positions"], dtype=float)
    lengths = np.asarray(surface["lengths"], dtype=float)
    accuracy = np.asarray(surface["accuracy"], dtype=float) * 100.0

    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(96)))
    grid_x, grid_y = np.meshgrid(positions, lengths, indexing="ij")
    ax = fig.add_subplot(111)
    filled = ax.contourf(grid_x, grid_y, accuracy, levels=14, cmap="RdYlBu")
    lines = ax.contour(grid_x, grid_y, accuracy, levels=8, colors="white", linewidths=0.6)
    ax.clabel(lines, inline=True, fontsize=5.4, fmt="%.1f")
    ax.set_xlabel("缺失起始位置")
    ax.set_ylabel("缺失时长 / 位置")
    ax.set_title("视觉模态缺失位置与缺失时长的准确率等值线", fontsize=8.0, pad=8)
    bar = fig.colorbar(filled, ax=ax, fraction=0.030, pad=0.020)
    bar.set_label("情感极性准确率 / %", fontsize=6.4)
    bar.ax.tick_params(labelsize=5.8)
    baseline = report["missing_rate_all"][0]["accuracy"] * 100.0
    best = np.unravel_index(int(np.argmax(accuracy)), accuracy.shape)
    worst = np.unravel_index(int(np.argmin(accuracy)), accuracy.shape)
    ax.scatter([positions[best[0]]], [lengths[best[1]]], marker="*", s=90,
               color=PALETTE["blue_main"], edgecolor="white", linewidth=0.6, zorder=6)
    ax.scatter([positions[worst[0]]], [lengths[worst[1]]], marker="X", s=70,
               color=PALETTE["red_strong"], edgecolor="white", linewidth=0.6, zorder=6)
    ax.annotate(f"最高 {accuracy[best]:.1f}%", xy=(positions[best[0]], lengths[best[1]]),
                xytext=(8, 8), textcoords="offset points", fontsize=6.2, color=PALETTE["blue_main"])
    ax.annotate(f"最低 {accuracy[worst]:.1f}%", xy=(positions[worst[0]], lengths[worst[1]]),
                xytext=(8, -12), textcoords="offset points", fontsize=6.2, color=PALETTE["red_strong"])
    ax.text(0.985, 0.035, f"无缺失基线准确率 {baseline:.2f}%", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=6.2, color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    return fc.save(fig, "fig_q2_04_contour_position", FIG)


def fig_q2_05_duration_error() -> dict:
    report = load_report()
    rows = report["missing_position"]
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(78)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.05, 1.0], wspace=0.36)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    for modality in ("text", "audio", "vision"):
        subset = [item for item in rows if item["modality"] == modality]
        grouped = {}
        for item in subset:
            grouped.setdefault(item["window_length"], []).append(item["mae"])
        xs = sorted(grouped)
        ys = [float(np.mean(grouped[key])) for key in xs]
        errs = [float(np.std(grouped[key])) for key in xs]
        ax.errorbar(xs, ys, yerr=errs, marker="o", ms=3.8, lw=1.6, capsize=2.6, elinewidth=0.8,
                    color=C[{"text": "文本", "audio": "语音", "vision": "视觉"}[modality]],
                    label={"text": "文本", "audio": "语音", "vision": "视觉"}[modality], zorder=3)
    ax.set_xlabel("缺失时长 / 位置")
    ax.set_ylabel("情感强度平均绝对误差")
    ax.set_title("(a) 缺失时长与强度误差", fontsize=7.2, pad=6)
    ax.legend(loc="upper left", handlelength=1.5, fontsize=6.0)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "y")
    positions = (("front", "序列前段"), ("middle", "序列中段"), ("back", "序列后段"))
    markers = ("o", "s", "^")
    for index, modality in enumerate(("text", "audio", "vision")):
        for (position, label), marker in zip(positions, markers):
            subset = [item for item in rows if item["modality"] == modality and item["position"] == position]
            subset.sort(key=lambda item: item["window_length"])
            xs = [item["window_length"] for item in subset]
            ys = [item["mae"] for item in subset]
            linestyle = ("-", "--", ":")[index]
            ax.plot(xs, ys, marker=marker, ms=3.4, lw=1.4, linestyle=linestyle,
                    color=C[{"text": "文本", "audio": "语音", "vision": "视觉"}[modality]],
                    alpha=0.95, zorder=3)
    handles = [Line2D([], [], marker=marker, linestyle="", color=PALETTE["neutral_dark"], ms=4.4,
                      label=label) for (_, label), marker in zip(positions, markers)]
    handles += [Line2D([], [], color=C[name], lw=1.6, label=name) for name in ("文本", "语音", "视觉")]
    ax.legend(handles=handles, loc="upper left", ncol=2, handlelength=1.2, fontsize=5.8,
              columnspacing=0.8)
    ax.set_xlabel("缺失时长 / 位置")
    ax.set_ylabel("情感强度平均绝对误差")
    ax.set_ylim(0.634, 0.678)
    ax.set_title("(b) 缺失位置 × 模态的误差", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    for modality, label, color, marker in (("text", "文本", C["文本"], "o"),
                                           ("audio", "语音", C["语音"], "s"),
                                           ("vision", "视觉", C["视觉"], "^")):
        subset = [item for item in rows if item["modality"] == modality and item["window_length"] == 25]
        order = {"front": 0, "middle": 1, "back": 2}
        subset.sort(key=lambda item: order[item["position"]])
        xs = np.arange(3)
        ys = [item["accuracy"] * 100 for item in subset]
        ax.plot(xs, ys, marker=marker, ms=4.2, lw=1.7, color=color, label=label, zorder=3)
        for x, y in zip(xs, ys):
            ax.annotate(f"{y:.1f}", xy=(x, y), xytext=(0, 8), textcoords="offset points",
                        fontsize=5.8, ha="center", color=color)
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(("序列前段", "序列中段", "序列后段"))
    ax.set_ylabel("情感极性准确率 / %")
    ax.set_ylim(52.4, 57.6)
    ax.set_title("(c) 25 位置缺失下的准确率", fontsize=7.2, pad=6)
    ax.legend(loc="lower right", handlelength=1.4, fontsize=6.0)
    return fc.save(fig, "fig_q2_05_duration_error", FIG)


def fig_q2_06_ablation() -> dict:
    report = load_report()
    ablation = report["ablation"]
    names = {
        "robust_full": "门控+注意力（主模型）",
        "robust_no_gate": "去可信度门控",
        "robust_no_attention": "去跨模态注意力",
        "mean_fusion": "简单平均融合",
        "tensor_fusion": "张量外积融合",
        "lowrank_fusion": "低秩多模态融合",
        "single_text": "仅文本",
        "single_audio": "仅语音",
        "single_vision": "仅视觉",
    }
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(210), fc.mm_to_inch(84)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.0, 1.0], wspace=0.56)

    entries = [(item["model"], item["valid"]) for item in ablation]
    entries.sort(key=lambda item: item[1]["mae"])
    labels = [names.get(key, key) for key, _ in entries]
    y = np.arange(len(entries))[::-1]
    main_index = [index for index, (key, _) in enumerate(entries) if key == "robust_full"][0]

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "x")
    for index, (key, metrics) in enumerate(entries):
        color = PALETTE["blue_main"] if key == "robust_full" else PALETTE["neutral_mid"]
        ax.hlines(y[index], 0, metrics["mae"], color=color, lw=2.2, zorder=2)
        ax.scatter([metrics["mae"]], [y[index]], color=color, s=30, zorder=3)
        ax.annotate(f"{metrics['mae']:.4f}", xy=(metrics["mae"], y[index]), xytext=(5, -1),
                    textcoords="offset points", fontsize=5.9, color=color, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6.0)
    ax.set_xlabel("验证集情感强度平均绝对误差（越小越好）")
    ax.set_xlim(0, max(item[1]["mae"] for item in entries) * 1.28)
    ax.set_title("(a) 融合结构消融：强度误差", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "x")
    entries_acc = sorted(ablation, key=lambda item: item["valid"]["accuracy"])
    y = np.arange(len(entries_acc))[::-1]
    for index, item in enumerate(entries_acc):
        color = PALETTE["blue_main"] if item["model"] == "robust_full" else PALETTE["neutral_mid"]
        ax.hlines(y[index], 0, item["valid"]["accuracy"] * 100, color=color, lw=2.2, zorder=2)
        ax.scatter([item["valid"]["accuracy"] * 100], [y[index]], color=color, s=30, zorder=3)
        ax.annotate(f"{item['valid']['accuracy'] * 100:.2f}", xy=(item["valid"]["accuracy"] * 100, y[index]),
                    xytext=(5, -1), textcoords="offset points", fontsize=5.9, color=color, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels([names.get(item["model"], item["model"]) for item in entries_acc], fontsize=6.0)
    ax.set_xlabel("验证集情感极性准确率 / %")
    ax.set_xlim(0, 78)
    ax.set_title("(b) 融合结构消融：极性准确率", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "x")
    strategies = report["strategies"]
    order = ["clean", "augment_light", "augment_heavy", "curriculum"]
    strategy_names = {"clean": "无缺失增强", "augment_light": "轻度增强", "augment_heavy": "重度增强",
                      "curriculum": "课程式增强"}
    y = np.arange(len(order))[::-1]
    for index, key in enumerate(order):
        entry = next(item for item in strategies if item["strategy"] == key)
        acc = entry["valid"]["accuracy"] * 100
        mae = entry["valid"]["mae"]
        ax.hlines(y[index], 0, acc, color=PALETTE["blue_main"], lw=2.4, zorder=2)
        ax.scatter([acc], [y[index]], color=PALETTE["blue_main"], s=32, zorder=3)
        ax.annotate(f"准确率 {acc:.2f}%　强度误差 {mae:.4f}", xy=(acc, y[index]), xytext=(6, -1),
                    textcoords="offset points", fontsize=5.9, va="center",
                    color=PALETTE["slate_dark"])
    ax.set_yticks(y)
    ax.set_yticklabels([strategy_names[key] for key in order], fontsize=6.2)
    ax.set_xlabel("验证集情感极性准确率 / %")
    ax.set_xlim(0, 78)
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.set_title("(c) 缺失增强策略对比", fontsize=7.2, pad=6)
    ax.text(0.98, 0.04, "线段长度表示准确率，\n右侧文字给出强度误差", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=5.7, color=PALETTE["slate_dark"])
    return fc.save(fig, "fig_q2_06_ablation", FIG)


def fig_q2_07_convergence() -> dict:
    report = load_report()
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(170), fc.mm_to_inch(84)))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.25, 1.0], wspace=0.34)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    styles = {"clean": ("-", PALETTE["neutral_dark"]), "augment_light": ("-", PALETTE["blue_main"]),
              "augment_heavy": ("--", PALETTE["orange_main"]), "curriculum": (":", PALETTE["teal_main"])}
    names = {"clean": "无缺失增强", "augment_light": "轻度增强", "augment_heavy": "重度增强",
             "curriculum": "课程式增强"}
    for item in report["strategies"]:
        key = item["strategy"]
        history = item["history"]
        xs = [entry["epoch"] for entry in history]
        ys = [entry["loss"] for entry in history]
        linestyle, color = styles[key]
        ax.plot(xs, ys, linestyle=linestyle, lw=1.7, color=color, label=names[key], zorder=3)
    ax.set_xlabel("训练轮次")
    ax.set_ylabel("训练损失（加权交叉熵 + Huber）")
    ax.set_yscale("log")
    ax.set_title("(a) 四种缺失增强策略的收敛过程", fontsize=7.2, pad=6)
    ax.legend(loc="upper right", handlelength=1.6, fontsize=6.0)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "both")
    ablation = report["ablation"]
    names_map = {"robust_full": "门控+注意力（主模型）", "robust_no_gate": "去可信度门控",
                 "robust_no_attention": "去跨模态注意力", "mean_fusion": "简单平均融合",
                 "tensor_fusion": "张量外积融合", "lowrank_fusion": "低秩多模态融合",
                 "single_text": "仅文本", "single_audio": "仅语音", "single_vision": "仅视觉"}
    fusion_keys = {"robust_full", "robust_no_gate", "robust_no_attention",
                   "mean_fusion", "tensor_fusion", "lowrank_fusion"}
    for item in ablation:
        key = item["model"]
        x = item["valid"]["mae"]
        y = item["valid"]["pearson"]
        size = item["valid"]["macro_f1"] * 240
        if key == "robust_full":
            ax.scatter(x, y, s=size, color=PALETTE["blue_main"], alpha=0.95,
                       edgecolor="white", linewidth=0.7, zorder=5, marker="*")
        elif key in fusion_keys:
            ax.scatter(x, y, s=size, color=PALETTE["neutral_mid"], alpha=0.72,
                       edgecolor="white", linewidth=0.6, zorder=3, marker="o")
        else:
            ax.scatter(x, y, s=size, color=PALETTE["orange_main"], alpha=0.85,
                       edgecolor="white", linewidth=0.6, zorder=4, marker="s")
        if key in {"single_audio", "single_vision", "single_text"}:
            offsets = {"single_text": (0, -16), "single_vision": (0, 12), "single_audio": (0, -16)}
            ax.annotate(names_map[key], xy=(x, y), xytext=offsets[key], textcoords="offset points",
                        fontsize=5.9, ha="center", color=PALETTE["orange_main"])
    handles = [
        Line2D([], [], marker="*", linestyle="", color=PALETTE["blue_main"], ms=8, label="门控+注意力（主模型）"),
        Line2D([], [], marker="o", linestyle="", color=PALETTE["neutral_mid"], ms=5.5, label="其他融合结构"),
        Line2D([], [], marker="s", linestyle="", color=PALETTE["orange_main"], ms=5.5, label="单模态对照"),
    ]
    ax.legend(handles=handles, loc="lower left", handlelength=1.0, fontsize=5.9)
    ax.set_xlabel("情感强度平均绝对误差（越小越好）")
    ax.set_ylabel("情感强度皮尔逊相关系数（越大越好）")
    ax.set_title("(b) 误差–相关权衡（点面积表示宏平均 F1）", fontsize=7.2, pad=6)
    ax.set_ylim(-0.02, 0.72)
    ax.margins(x=0.14)
    return fc.save(fig, "fig_q2_07_convergence", FIG)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    reports = [fig_q2_01_missing_pattern(), fig_q2_02_rate_curves(),
               fig_q2_03_response_surface(), fig_q2_04_contour_position(),
               fig_q2_05_duration_error(), fig_q2_06_ablation(), fig_q2_07_convergence()]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
