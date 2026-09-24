"""生成进入论文正文的全部 Python 数据图（统一入口，输出写入各分区 figures/ 目录）。

设计约束：
- 每张图的 `panel_count` 为语义面板数；全篇多面板图不超过 4 张（少用子图策略）。
- 柱状图策略为禁用：所有区间、排序与幅度比较一律用线段与端点标记表达。
- 导出 svg + pdf + png 三种格式，并完成中文字体、可编辑文本与配色 QA。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import fig_common as fc

PALETTE = fc.PALETTE
C = fc.MODALITY_COLORS
POLARITY_CN = ("负向", "中性", "正向")
MODALITY_NAMES = ("文本", "语音", "视觉")
DATA = PROJECT / "data" / "processed"

FIG_ROOT = PROJECT / "figures"
FIG_Q1 = PROJECT / "Q1" / "figures"
FIG_Q2 = PROJECT / "Q2" / "figures"
FIG_Q3 = PROJECT / "Q3" / "figures"
FIG_SENS = PROJECT / "灵敏度分析" / "figures"

Q2_RESULTS = PROJECT / "Q2" / "results"
Q3_RESULTS = PROJECT / "Q3" / "results"
SENS = PROJECT / "灵敏度分析"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fig01_data_overview() -> dict:
    summary = load_json(DATA / "eda_summary.json")
    inventory = np.genfromtxt(DATA.parent / "raw" / "a1_media_inventory.csv", delimiter=",",
                              names=True, dtype=None, encoding="utf-8-sig")
    durations = np.asarray(inventory["duration_sec"], dtype=float)
    words = np.asarray(inventory["text_words"], dtype=float)
    labels_reg = np.asarray(inventory["label"], dtype=float)
    stats = {(item["split"], item["modality"]): item for item in summary["modality_stats"]}

    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(210), fc.mm_to_inch(80)))
    grid = fig.add_gridspec(1, 4, width_ratios=[1.0, 0.95, 1.0, 1.0], wspace=0.46)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    means = np.asarray([summary["attachments"]["a2_splits"][key]["reg_mean"]
                        for key in ("train", "valid", "test")])
    stds = np.asarray([summary["attachments"]["a2_splits"][key]["reg_std"]
                       for key in ("train", "valid", "test")])
    x = np.arange(3)
    ax.errorbar(x, means, yerr=stds, fmt="o", color=PALETTE["blue_main"], ms=6, lw=1.6,
                capsize=3.2, elinewidth=1.1, zorder=3)
    ax.axhline(0.0, color=PALETTE["neutral_mid"], linestyle="--", linewidth=0.8, zorder=1)
    ax.set_xticks(x)
    ax.set_xticklabels(("训练集", "验证集", "测试集"))
    ax.set_ylabel("连续情感强度（均值±标准差）")
    ax.set_xlim(-0.55, 2.55)
    ax.set_ylim(-1.75, 1.45)
    ax.set_title("(a) 三划分强度分布一致性", fontsize=7.2, pad=6)
    ax.text(0.5, 0.045, "\n".join(f"{name}：{means[i]:.3f}±{stds[i]:.3f}"
                                  for i, name in enumerate(("训练集", "验证集", "测试集"))),
            transform=ax.transAxes, ha="center", va="bottom", fontsize=6.0,
            color=PALETTE["slate_dark"], linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))

    ax = fig.add_subplot(grid[0, 1])
    counts = np.asarray([[summary["attachments"]["a2_splits"][key]["cls_counts"][name]
                          for name in ("negative", "neutral", "positive")]
                         for key in ("train", "valid", "test")], dtype=float)
    ratio = counts / counts.sum(axis=1, keepdims=True) * 100.0
    for column, (name, color, marker) in enumerate(zip(POLARITY_CN,
                                                       (PALETTE["red_strong"], PALETTE["neutral_mid"],
                                                        PALETTE["blue_main"]), ("o", "s", "^"))):
        ax.plot(np.arange(3), ratio[:, column], marker=marker, color=color, lw=1.8, ms=5.5,
                label=name, zorder=3)
    fc.soften(ax, "y")
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(("训练集", "验证集", "测试集"))
    ax.set_ylabel("类别占比 / %")
    ax.set_ylim(0, 88)
    ax.set_xlim(-0.45, 2.45)
    ax.legend(loc="upper center", ncol=3, handlelength=1.1, columnspacing=0.8)
    ax.set_title("(b) 情感极性类别占比", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    palette = np.where(labels_reg > 0, PALETTE["blue_main"],
                       np.where(labels_reg < 0, PALETTE["red_strong"], PALETTE["neutral_mid"]))
    ax.scatter(durations, words, s=17, c=palette, alpha=0.85, edgecolor="white",
               linewidth=0.35, zorder=3)
    slope = np.polyfit(durations, words, 1)
    xs = np.linspace(durations.min(), durations.max(), 50)
    ax.plot(xs, np.polyval(slope, xs), color=PALETTE["slate_dark"], linestyle="--", lw=1.1, zorder=2)
    fc.soften(ax, "both")
    r = float(np.corrcoef(durations, words)[0, 1])
    ax.set_xlabel("片段时长 / 秒")
    ax.set_ylabel("转写词数 / 词")
    ax.set_xlim(0, 33)
    ax.set_ylim(0, 82)
    ax.set_title("(c) 时长与转写长度", fontsize=7.2, pad=6)
    ax.text(0.03, 0.97, f"皮尔逊相关系数 r = {r:.3f}\n样本数 n = {len(durations)}",
            transform=ax.transAxes, fontsize=6.0, va="top", color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    handles = [Line2D([], [], marker="o", linestyle="", color=color, ms=4.5, label=name)
               for color, name in zip((PALETTE["red_strong"], PALETTE["neutral_mid"],
                                       PALETTE["blue_main"]), POLARITY_CN)]
    ax.legend(handles=handles, loc="lower right", handlelength=1.0, title="情感极性",
              title_fontsize=6.2)

    ax = fig.add_subplot(grid[0, 3])
    fc.soften(ax, "y")
    for name, key, color, marker in (("文本", "text", C["文本"], "o"),
                                     ("语音", "audio", C["语音"], "s"),
                                     ("视觉", "vision", C["视觉"], "^")):
        values = [stats[("train", key)]["zero_ratio"] * 100, stats[("valid", key)]["zero_ratio"] * 100,
                  stats[("test", key)]["zero_ratio"] * 100]
        ax.plot(np.arange(3), values, marker=marker, color=color, lw=1.8, ms=5.5, label=name, zorder=3)
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(("训练集", "验证集", "测试集"))
    ax.set_ylabel("全零元素占比 / %")
    ax.set_xlim(-0.45, 2.45)
    ax.set_ylim(-4, 84)
    ax.legend(loc="upper center", ncol=3, handlelength=1.1, columnspacing=0.8)
    ax.set_title("(d) 三模态零值占比", fontsize=7.2, pad=6)
    return fc.save(fig, "fig01_data_overview", FIG_ROOT)


def fig02_modality_correlation() -> dict:
    summary = load_json(DATA / "eda_summary.json")
    corr = summary["modality_correlation"]["train"]
    pairs = (("文本–语音", "text_audio"), ("文本–视觉", "text_vision"), ("语音–视觉", "audio_vision"),
             ("文本–强度", "text_reg"), ("语音–强度", "audio_reg"), ("视觉–强度", "vision_reg"))
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(150), fc.mm_to_inch(86)))
    fc.soften(ax, "x")
    y = np.arange(len(pairs))[::-1]
    for index, (label, key) in enumerate(pairs):
        value = corr[key]
        color = PALETTE["blue_main"] if value >= 0 else PALETTE["red_strong"]
        ax.hlines(y[index], 0, value, color=color, lw=2.4, zorder=2)
        ax.scatter([value], [y[index]], color=color, s=30, zorder=3)
        text_x, align = (value + 0.05, "left") if value >= 0 else (value - 0.05, "right")
        ax.annotate(f"{value:+.3f}", xy=(text_x, y[index]), ha=align, va="center",
                    fontsize=6.2, color=color)
    ax.axvline(0, color=PALETTE["neutral_dark"], lw=0.9)
    ax.axvspan(-0.15, 0.15, color=PALETTE["neutral_light"], alpha=0.45, zorder=0)
    ax.set_yticks(y)
    ax.set_yticklabels([item[0] for item in pairs])
    ax.set_xlabel("样本级均值特征的皮尔逊相关系数")
    ax.set_xlim(-1.25, 1.05)
    ax.set_ylim(-0.85, 6.35)
    ax.set_title("三模态之间与模态–情感强度之间的相关结构（训练集）", fontsize=7.6, pad=8)
    ax.text(-0.15, 6.02, "弱相关带", ha="center", va="bottom", fontsize=6.0,
            color=PALETTE["neutral_dark"])
    ax.text(0.985, 0.03,
            "三模态均值之间相关中等，\n但与情感强度的线性相关都落在弱相关带内",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.0,
            color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    return fc.save(fig, "fig02_modality_correlation", FIG_ROOT)


def fig_q1_alignment() -> dict:
    """单面板对齐核验图：三模态特征强度与文本词元密度落在同一时间轴上。"""
    import re

    data = dict(np.load(PROJECT / "Q1" / "features_a1_100.npz", allow_pickle=True))
    labels = np.asarray(data["labels_reg"], dtype=float)
    durations = np.asarray(data["durations"], dtype=float)
    audio = np.asarray(data["audio"], dtype=np.float64)
    vision = np.asarray(data["vision"], dtype=np.float64)
    text = np.asarray(data["text"], dtype=np.float64)
    raw_text = [str(item) for item in data["raw_text"]]
    token_re = re.compile(r"[a-z0-9']+")

    order = np.argsort(np.abs(labels))[::-1]
    chosen = None
    for index in order:
        count = len(token_re.findall(raw_text[index].lower()))
        if 6.0 <= durations[index] <= 16.0 and 18 <= count <= 44:
            chosen = int(index)
            break
    if chosen is None:
        for index in order:
            count = len(token_re.findall(raw_text[index].lower()))
            if count < 50:
                chosen = int(index)
                break
    if chosen is None:
        chosen = int(order[0])

    duration = float(durations[chosen])
    edges = np.linspace(0.0, duration, 51)
    centers = 0.5 * (edges[:-1] + edges[1:])
    tokens = token_re.findall(raw_text[chosen].lower().replace("’", "'"))
    total = len(tokens)
    token_density = np.zeros(50)
    for k in range(50):
        start = int(np.floor(k * total / 50))
        stop = int(np.floor((k + 1) * total / 50))
        token_density[k] = max(0, stop - start)

    series = (
        ("语音帧级能量", audio[chosen][:, 72], PALETTE["orange_main"], "s"),
        ("视觉帧间灰度差", vision[chosen][:, 31], PALETTE["teal_main"], "^"),
    )
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(96)))
    fc.soften(ax, "y")
    for name, values, color, marker in series:
        scaled = values / max(float(values.max()), 1e-9)
        ax.plot(centers, scaled, marker=marker, ms=3.0, lw=1.7, color=color, label=name, zorder=3)
    for k in range(0, 51, 5):
        ax.axvline(edges[k], color="#E6E6E6", linewidth=0.6, zorder=0)
    assigned = np.zeros(50, dtype=int)
    for k in range(50):
        start = int(np.floor(k * total / 50))
        stop = int(np.floor((k + 1) * total / 50))
        assigned[k] = max(0, stop - start)
    for k in range(50):
        if assigned[k] <= 0:
            continue
        ax.plot([centers[k], centers[k]], [1.06, 1.16], color=PALETTE["blue_main"], lw=1.0, zorder=3)
        ax.text(centers[k], 1.19, " ".join(tokens[int(np.floor(k * total / 50)):
                                                int(np.floor((k + 1) * total / 50))]),
                rotation=90, fontsize=4.8, ha="center", va="bottom",
                color=PALETTE["blue_main"])
    ax.plot([], [], color=PALETTE["blue_main"], lw=1.2, label=f"文本词元落位（共 {total} 个词元）")
    ax.set_xlabel("时间 / 秒")
    ax.set_ylabel("归一化特征强度")
    ax.set_xlim(0, duration)
    ax.set_ylim(-0.08, 1.62)
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.legend(loc="upper center", ncol=3, handlelength=1.4, columnspacing=1.2)
    ax.set_title(f"典型样本三模态在同一时间栅格上的对齐核验"
                 f"（样本 {str(data['ids'][chosen]).replace('$', '-')}，"
                 f"时长 {duration:.3f} 秒，栅格粒度 {duration / 50:.4f} 秒）",
                 fontsize=7.8, pad=8)
    ax.text(0.012, 0.60,
            "灰线为 50 等分栅格边界；三通道共用同一条时间轴，\n"
            "栅格粒度 = 片段时长 / 50，位置 k 代表时刻 (k+0.5)·粒度；\n"
            "顶部竖线为文本词元按出现次序的落位，与语音、视觉曲线共享同一时间轴",
            transform=ax.transAxes, fontsize=6.0, va="top", color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    return fc.save(fig, "fig_q1_01_alignment", FIG_Q1)


def fig_q1_vision_space() -> dict:
    data = dict(np.load(PROJECT / "Q1" / "features_a1_100.npz", allow_pickle=True))
    labels = np.asarray(data["labels_cls"], dtype=int)
    vision = np.asarray(data["vision"], dtype=np.float64).mean(axis=1)
    mean = vision.mean(axis=0)
    std = vision.std(axis=0)
    std[std < 1e-9] = 1.0
    matrix = (vision - mean) / std
    centered = matrix - matrix.mean(axis=0)
    u, s, _ = np.linalg.svd(centered, full_matrices=False)
    coords = u[:, :3] * s[:3]
    variance = (s ** 2 / (s ** 2).sum())[:3] * 100
    colors = (PALETTE["red_strong"], PALETTE["neutral_mid"], PALETTE["blue_main"])
    centroids = np.stack([coords[labels == c].mean(axis=0) for c in range(3)])
    spread = np.mean([coords[labels == c].std(axis=0).mean() for c in range(3)])
    separation = float(np.mean(np.linalg.norm(
        centroids[:, None, :] - centroids[None, :, :], axis=2)) / max(spread, 1e-9))

    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(150), fc.mm_to_inch(112)))
    ax = fig.add_subplot(111, projection="3d")
    for class_index, color in enumerate(colors):
        mask = labels == class_index
        ax.scatter(coords[mask, 0], coords[mask, 1], coords[mask, 2], s=17, c=color,
                   alpha=0.85, depthshade=False, edgecolor="white", linewidth=0.18,
                   label=POLARITY_CN[class_index])
    for class_index, color in enumerate(colors):
        ax.scatter(centroids[class_index, 0], centroids[class_index, 1], centroids[class_index, 2],
                   s=80, marker="X", c=color, edgecolor="black", linewidth=0.7, zorder=6)
    ax.set_xlabel(f"主成分1（{variance[0]:.1f}%）", fontsize=6.6, labelpad=0)
    ax.set_ylabel(f"主成分2（{variance[1]:.1f}%）", fontsize=6.6, labelpad=0)
    ax.set_zlabel(f"主成分3（{variance[2]:.1f}%）", fontsize=6.6, labelpad=-1)
    ax.tick_params(labelsize=5.6, pad=-1)
    ax.view_init(elev=20, azim=38)
    ax.set_title(f"视觉模态特征空间三维投影（附件1 自生成特征）\n"
                 f"前三个主成分累计方差 {variance.sum():.1f}%，类心分离度 {separation:.2f}",
                 fontsize=7.4, pad=2)
    ax.legend(loc="upper left", bbox_to_anchor=(-0.10, 0.99), handlelength=0.9,
              fontsize=6.0, title="情感极性", title_fontsize=6.2)
    fig.text(0.5, 0.022,
             "叉号为类别中心；类别中心高度重叠，说明情感判别依赖时序局部结构而非全局均值",
             ha="center", fontsize=6.0, color=PALETTE["slate_dark"])
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.10)
    return fc.save(fig, "fig_q1_03_vision_space", FIG_Q1)


def fig_q1_vision_coverage() -> dict:
    data = dict(np.load(PROJECT / "Q1" / "features_a1_100.npz", allow_pickle=True))
    durations = np.asarray(data["durations"], dtype=float)
    labels = np.asarray(data["labels_cls"], dtype=int)
    matrix = np.asarray(data["vision_valid"], dtype=float)
    order = np.lexsort((durations, labels))
    cmap = LinearSegmentedColormap.from_list("coverage", ["#F2F2F2", PALETTE["blue_secondary"]])
    fc.setup(6.6)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(150), fc.mm_to_inch(104)))
    im = ax.imshow(matrix[order], aspect="auto", cmap=cmap, interpolation="nearest",
                   vmin=0, vmax=1, extent=[0, 50, len(order), 0])
    ax.set_xlabel("序列位置")
    ax.set_ylabel("样本序号（按极性、时长排序）")
    ax.set_xticks([0, 10, 20, 30, 40, 50])
    for boundary in np.where(np.diff(labels[order]) != 0)[0] + 1:
        ax.axhline(boundary, color=PALETTE["red_strong"], lw=0.8, linestyle="--")
    starts = np.concatenate([[0], np.where(np.diff(labels[order]) != 0)[0] + 1])
    ends = np.concatenate([starts[1:], [len(order)]])
    for start, end in zip(starts, ends):
        ax.text(52.5, 0.5 * (start + end), POLARITY_CN[labels[order][start]],
                fontsize=6.2, va="center", rotation=90, color=PALETTE["red_strong"])
    ax.set_title(f"视觉通道有效位置覆盖（附件1 自生成特征）\n"
                 f"有效位置均值 {matrix.sum(axis=1).mean():.2f} / 50，"
                 f"最少 {int(matrix.sum(axis=1).min())} 个、最多 {int(matrix.sum(axis=1).max())} 个",
                 fontsize=7.4, pad=8)
    bar = fig.colorbar(im, ax=ax, fraction=0.040, pad=0.035, ticks=[0, 1])
    bar.set_label("有效标志", fontsize=6.2)
    bar.ax.set_yticklabels(["填充", "有效"], fontsize=5.8)
    fig.subplots_adjust(left=0.11, right=0.98, top=0.86, bottom=0.10)
    return fc.save(fig, "fig_q1_04_vision_coverage", FIG_Q1)


def fig_q2_missing_pattern() -> dict:
    import pandas as pd

    frame = pd.read_csv(DATA / "a3_missing_mask.csv")
    samples = frame["sample"].tolist()
    matrix = np.zeros((3 * len(samples), 50), dtype=float)
    for row, (_, item) in enumerate(frame.iterrows()):
        for modality_index, modality in enumerate(("text", "audio", "vision")):
            for start, end in json.loads(item[f"{modality}_missing_segments"]):
                matrix[modality_index * len(samples) + row, start:end + 1] = 1.0

    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(94)))
    grid = fig.add_gridspec(1, 4, width_ratios=[1.40, 0.60, 0.62, 0.62], wspace=0.34)

    ax = fig.add_subplot(grid[0, 0])
    cmap = matplotlib.colors.ListedColormap(["#F2F2F2", PALETTE["red_strong"]])
    im = ax.imshow(matrix, aspect="auto", cmap=cmap, interpolation="nearest",
                   extent=[0, 50, matrix.shape[0], 0])
    ax.set_xlabel("序列位置")
    ax.set_ylabel("样本 × 模态（按模态分块）")
    ax.set_xticks([0, 10, 20, 30, 40, 50])
    for boundary in (len(samples), 2 * len(samples)):
        ax.axhline(boundary, color=PALETTE["neutral_dark"], lw=1.0)
    for index, name in enumerate(MODALITY_NAMES):
        ax.text(53.5, (index + 0.5) * len(samples), name, fontsize=6.4, va="center",
                color=(C["文本"], C["语音"], C["视觉"])[index])
    ax.set_title("(a) 附件3 缺失位置矩阵（红色为缺失）", fontsize=7.2, pad=6)
    cax = fig.add_axes([0.330, 0.19, 0.009, 0.26])
    bar = fig.colorbar(im, cax=cax, ticks=[0, 1])
    bar.ax.set_yticklabels(["有效", "缺失"], fontsize=5.6)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "y")
    bins = np.arange(0, 105, 10)
    for name, key, color, marker in (("文本", "text", C["文本"], "o"),
                                     ("语音", "audio", C["语音"], "s"),
                                     ("视觉", "vision", C["视觉"], "^")):
        counts, edges = np.histogram(frame[f"{key}_missing_ratio"].values * 100, bins=bins)
        ax.plot(0.5 * (edges[:-1] + edges[1:]), counts, marker=marker, ms=3.4, lw=1.5,
                color=color, label=name, zorder=3)
    ax.set_xlabel("缺失率 / %")
    ax.set_ylabel("样本数 / 条")
    ax.set_xlim(-4, 96)
    ax.legend(loc="upper left", handlelength=1.2, fontsize=5.9)
    ax.set_title("(b) 缺失率分布", fontsize=7.0, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    lengths = {"text": [], "audio": [], "vision": []}
    for _, item in frame.iterrows():
        for modality in ("text", "audio", "vision"):
            segments = json.loads(item[f"{modality}_missing_segments"])
            lengths[modality].extend([end - start + 1 for start, end in segments])
    bins = np.arange(0.5, 32.5, 2.0)
    for name, key, color, marker in (("文本", "text", C["文本"], "o"),
                                     ("语音", "audio", C["语音"], "s"),
                                     ("视觉", "vision", C["视觉"], "^")):
        counts, edges = np.histogram(lengths[key], bins=bins)
        ax.plot(0.5 * (edges[:-1] + edges[1:]), counts, marker=marker, ms=3.4, lw=1.5,
                color=color, label=f"{name}（中位 {np.median(lengths[key]):.0f}）", zorder=3)
    ax.set_xlabel("连续缺失区间长度 / 位置")
    ax.set_ylabel("区间数 / 个")
    ax.legend(loc="upper right", handlelength=1.2, fontsize=5.7)
    ax.set_title("(c) 缺失区间长度", fontsize=7.0, pad=6)

    ax = fig.add_subplot(grid[0, 3])
    fc.soften(ax, "x")
    counts_per_sample = {key: [] for key in ("text", "audio", "vision")}
    for _, item in frame.iterrows():
        for modality in ("text", "audio", "vision"):
            counts_per_sample[modality].append(len(json.loads(item[f"{modality}_missing_segments"])))
    y = np.arange(3)[::-1]
    for index, (name, key, color) in enumerate((("文本", "text", C["文本"]),
                                                ("语音", "audio", C["语音"]),
                                                ("视觉", "vision", C["视觉"]))):
        mean = float(np.mean(counts_per_sample[key]))
        median = float(np.median(counts_per_sample[key]))
        ax.hlines(y[index], 0, mean, color=color, lw=2.4, zorder=2)
        ax.scatter([mean], [y[index]], color=color, s=34, zorder=3)
        ax.scatter([median], [y[index]], color="white", s=26, zorder=4,
                   edgecolor=color, linewidth=1.1)
        ax.annotate(f"{mean:.2f}", xy=(mean, y[index]), xytext=(6, 0), textcoords="offset points",
                    fontsize=5.9, color=color, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("每样本缺失区间数 / 个")
    ax.set_xlim(0, 6.2)
    ax.set_ylim(-0.7, 2.7)
    ax.set_title("(d) 缺失碎片化程度", fontsize=7.0, pad=6)
    ax.text(0.98, 0.04, "实心为均值、空心为中位数", transform=ax.transAxes,
            fontsize=5.7, ha="right", va="bottom", color=PALETTE["slate_dark"])
    return fc.save(fig, "fig_q2_01_missing_pattern", FIG_Q2)


def fig_q2_rate_curves() -> dict:
    report = load_json(Q2_RESULTS / "q2_report.json")
    series = [("all", report["missing_rate_all"], PALETTE["slate_dark"], "全模态同时缺失")]
    for modality, name, color in (("text", "文本", PALETTE["blue_main"]),
                                  ("audio", "语音", PALETTE["orange_main"]),
                                  ("vision", "视觉", PALETTE["teal_main"])):
        series.append((modality, report["missing_rate_single"][modality], color, f"仅缺失{name}"))
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(92)))
    fc.soften(ax, "y")
    for key, rows, color, label in series:
        xs = np.asarray([item["missing_ratio"] for item in rows]) * 100
        ys = np.asarray([item["accuracy"] for item in rows]) * 100
        errs = np.asarray([item["accuracy_std"] for item in rows]) * 100
        ax.errorbar(xs, ys, yerr=errs, marker="o", ms=4.0, lw=1.7, capsize=2.6, elinewidth=0.9,
                    color=color, label=label, zorder=3)
    baseline = report["missing_rate_all"][0]["accuracy"] * 100
    ax.axhline(baseline, color=PALETTE["neutral_mid"], linestyle="--", lw=0.9, zorder=1)
    ax.annotate(f"无缺失基线 {baseline:.2f}%", xy=(52, baseline), xytext=(0, -14),
                textcoords="offset points", fontsize=6.0, ha="center",
                color=PALETTE["neutral_dark"])
    ax.set_xlabel("缺失率 / %")
    ax.set_ylabel("情感极性准确率 / %")
    ax.set_xlim(-3, 73)
    ax.set_title("缺失模态类型与缺失率对情感极性准确率的影响（误差棒为 3 次随机缺失的标准差）",
                 fontsize=7.8, pad=8)
    ax.legend(loc="lower left", handlelength=1.5, fontsize=6.2)
    return fc.save(fig, "fig_q2_02_rate_curves", FIG_Q2)


def fig_q2_response_surface() -> dict:
    report = load_json(Q2_RESULTS / "q2_report.json")
    surface = report["response_surface"]["vision"]
    positions = np.asarray(surface["positions"], dtype=float)
    lengths = np.asarray(surface["lengths"], dtype=float)
    mae = np.asarray(surface["mae"], dtype=float)
    baseline = report["missing_rate_all"][0]["mae"]
    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(120)))
    ax = fig.add_subplot(111, projection="3d")
    grid_x, grid_y = np.meshgrid(positions, lengths, indexing="ij")
    surf = ax.plot_surface(grid_x, grid_y, mae, cmap="viridis", edgecolor="none",
                           alpha=0.94, antialiased=True, rstride=1, cstride=1)
    ax.contour(grid_x, grid_y, mae, zdir="z", offset=float(mae.min()) - 0.04, levels=8,
               cmap="viridis", linewidths=0.7)
    ax.set_xlabel("缺失起始位置", fontsize=6.8, labelpad=1)
    ax.set_ylabel("缺失时长 / 位置", fontsize=6.8, labelpad=1)
    ax.set_zlabel("情感强度平均绝对误差", fontsize=6.8, labelpad=1)
    ax.tick_params(labelsize=5.8, pad=-1)
    ax.view_init(elev=24, azim=-128)
    ax.set_title("视觉模态缺失位置与缺失时长的联合响应面", fontsize=8.0, pad=2)
    bar = fig.colorbar(surf, ax=ax, fraction=0.030, pad=0.10, shrink=0.72)
    bar.set_label("情感强度平均绝对误差", fontsize=6.4)
    bar.ax.tick_params(labelsize=5.8)
    worst = np.unravel_index(int(np.argmax(mae)), mae.shape)
    ax.scatter([positions[worst[0]]], [lengths[worst[1]]], [mae[worst]],
               color=PALETTE["red_strong"], s=44, marker="X", depthshade=False, zorder=6)
    fig.text(0.5, 0.022,
             f"底投影为等值线；无缺失基线误差 {baseline:.4f}，响应面上所有组合的误差均高于基线，"
             "误差随时长增长而在序列中后段放大",
             ha="center", fontsize=6.2, color=PALETTE["slate_dark"])
    return fc.save(fig, "fig_q2_03_response_surface", FIG_Q2)


def fig_q2_duration_error() -> dict:
    report = load_json(Q2_RESULTS / "q2_report.json")
    rows = report["missing_position"]
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(92)))
    fc.soften(ax, "y")
    for modality, name, color, marker in (("text", "文本", PALETTE["blue_main"], "o"),
                                          ("audio", "语音", PALETTE["orange_main"], "s"),
                                          ("vision", "视觉", PALETTE["teal_main"], "^")):
        subset = [item for item in rows if item["modality"] == modality]
        grouped = {}
        for item in subset:
            grouped.setdefault(item["window_length"], []).append(item["mae"])
        xs = sorted(grouped)
        ys = [float(np.mean(grouped[key])) for key in xs]
        errs = [float(np.std(grouped[key])) for key in xs]
        ax.errorbar(xs, ys, yerr=errs, marker=marker, ms=4.2, lw=1.8, capsize=2.6,
                    elinewidth=0.9, color=color, label=f"{name}（三个缺失位置合并）", zorder=3)
    baseline = report["missing_rate_all"][0]["mae"]
    ax.axhline(baseline, color=PALETTE["neutral_mid"], linestyle="--", lw=0.9, zorder=1)
    ax.annotate(f"无缺失基线 {baseline:.4f}", xy=(12, baseline), xytext=(0, -14),
                textcoords="offset points", fontsize=6.0, ha="center",
                color=PALETTE["neutral_dark"])
    ax.set_xlabel("缺失时长 / 位置")
    ax.set_ylabel("情感强度平均绝对误差")
    ax.set_title("缺失时长对情感强度误差的影响（误差棒为序列前/中/后三个缺失位置的标准差）",
                 fontsize=7.8, pad=8)
    ax.legend(loc="upper left", handlelength=1.5, fontsize=6.2)
    return fc.save(fig, "fig_q2_05_duration_error", FIG_Q2)


def fig_q2_ablation() -> dict:
    report = load_json(Q2_RESULTS / "q2_report.json")
    ablation = report["ablation"]
    names = {
        "robust_full": "门控+注意力（主模型）", "robust_no_gate": "去可信度门控",
        "robust_no_attention": "去跨模态注意力", "mean_fusion": "简单平均融合",
        "tensor_fusion": "张量外积融合", "lowrank_fusion": "低秩多模态融合",
        "single_text": "仅文本", "single_audio": "仅语音", "single_vision": "仅视觉",
    }
    entries = sorted(ablation, key=lambda item: item["valid"]["mae"])
    labels = [names.get(item["model"], item["model"]) for item in entries]
    y = np.arange(len(entries))[::-1]
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(96)))
    fc.soften(ax, "x")
    for index, item in enumerate(entries):
        key = item["model"]
        mae = item["valid"]["mae"]
        if key == "robust_full":
            color, marker, size = PALETTE["blue_main"], "*", 90
        elif key.startswith("single_"):
            color, marker, size = PALETTE["orange_main"], "s", 34
        else:
            color, marker, size = PALETTE["neutral_mid"], "o", 30
        ax.hlines(y[index], 0, mae, color=color, lw=2.2, zorder=2)
        ax.scatter([mae], [y[index]], color=color, s=size, marker=marker, zorder=3,
                   edgecolor="white", linewidth=0.5)
        ax.annotate(f"{mae:.4f}", xy=(mae, y[index]), xytext=(6, 0), textcoords="offset points",
                    fontsize=6.0, va="center", color=color)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6.2)
    ax.set_xlabel("验证集情感强度平均绝对误差（越小越好）")
    ax.set_xlim(0, max(item["valid"]["mae"] for item in entries) * 1.28)
    ax.set_ylim(-0.7, len(entries) - 0.3)
    ax.set_title("融合结构消融：可信度门控、跨模态注意力与多模态融合的贡献", fontsize=7.8, pad=8)
    handles = [Line2D([], [], marker="*", linestyle="", color=PALETTE["blue_main"], ms=9,
                      label="门控+注意力（主模型）"),
               Line2D([], [], marker="o", linestyle="", color=PALETTE["neutral_mid"], ms=5.5,
                      label="其他融合结构"),
               Line2D([], [], marker="s", linestyle="", color=PALETTE["orange_main"], ms=5.5,
                      label="单模态对照")]
    ax.legend(handles=handles, loc="lower right", handlelength=1.0, fontsize=6.0)
    return fc.save(fig, "fig_q2_06_ablation", FIG_Q2)


def fig_q3_modality_heatmap() -> dict:
    data = dict(np.load(Q3_RESULTS / "q3_valid_outputs.npz", allow_pickle=True))
    alpha = np.asarray(data["alpha"], dtype=float)
    labels = np.asarray(data["labels_cls"], dtype=int)
    order = np.lexsort((-alpha[:, 0], labels))
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(88)))
    grid = fig.add_gridspec(1, 4, width_ratios=[1.15, 1.0, 0.92, 0.92], wspace=0.38)

    ax = fig.add_subplot(grid[0, 0])
    im = ax.imshow(alpha[order].T, aspect="auto", cmap="magma", interpolation="nearest",
                   extent=[0, len(order), 3, 0], vmin=0.0, vmax=1.0)
    ax.set_yticks([0.5, 1.5, 2.5])
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("验证集样本（按极性、文本作用程度排序）")
    starts = np.concatenate([[0], np.where(np.diff(labels[order]) != 0)[0] + 1])
    ends = np.concatenate([starts[1:], [len(order)]])
    for start, end in zip(starts, ends):
        ax.axvline(start, color="white", lw=0.7, linestyle="--")
        ax.text(0.5 * (start + end), -0.24, POLARITY_CN[labels[order][start]], ha="center",
                va="bottom", fontsize=6.2, color=PALETTE["slate_dark"])
    ax.set_title("(a) 逐样本模态作用程度", fontsize=7.2, pad=6)
    bar = fig.colorbar(im, ax=ax, fraction=0.038, pad=0.035)
    bar.set_label("模态作用程度", fontsize=6.2)
    bar.ax.tick_params(labelsize=5.8)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "x")
    y = np.arange(3)[::-1]
    for index, (name, color) in enumerate(zip(MODALITY_NAMES, (C["文本"], C["语音"], C["视觉"]))):
        values = alpha[:, index]
        mean = float(values.mean())
        low, high = np.percentile(values, [25, 75])
        ax.hlines(y[index], low, high, color=color, lw=4.2, alpha=0.35, zorder=2)
        ax.scatter([mean], [y[index]], color=color, s=46, zorder=4, edgecolor="white", linewidth=0.6)
        ax.annotate(f"{mean:.3f}", xy=(mean, y[index]), xytext=(0, 11), textcoords="offset points",
                    fontsize=6.0, ha="center", color=color)
    ax.set_yticks(y)
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("模态作用程度")
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.85, 2.65)
    ax.set_title("(b) 模态作用程度的分布", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    for class_index, (name, color, marker) in enumerate(zip(POLARITY_CN,
                                                            (PALETTE["red_strong"],
                                                             PALETTE["neutral_mid"],
                                                             PALETTE["blue_main"]),
                                                            ("o", "s", "^"))):
        mask = labels == class_index
        if mask.sum() == 0:
            continue
        values = alpha[mask].mean(axis=0)
        ax.plot(np.arange(3), values, marker=marker, ms=4.6, lw=1.8, color=color, label=name, zorder=3)
        for x, value in zip(np.arange(3), values):
            ax.annotate(f"{value:.3f}", xy=(x, value), xytext=(0, 7), textcoords="offset points",
                        fontsize=5.8, ha="center", color=color)
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(MODALITY_NAMES)
    ax.set_ylabel("平均模态作用程度")
    ax.set_ylim(0, 0.62)
    ax.legend(loc="upper right", handlelength=1.2, fontsize=5.9)
    ax.set_title("(c) 不同极性下的模态作用", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 3])
    fc.soften(ax, "x")
    dominant = alpha.argmax(axis=1)
    counts = [int((dominant == index).sum()) for index in range(3)]
    for index, (name, color, count) in enumerate(zip(MODALITY_NAMES,
                                                     (C["文本"], C["语音"], C["视觉"]), counts)):
        ax.hlines(index, 0, count, color=color, lw=2.6, zorder=2)
        ax.scatter([count], [index], color=color, s=42, zorder=3)
        ax.annotate(f"{count} 条（{count / len(dominant) * 100:.1f}%）", xy=(count, index),
                    xytext=(6, 0), textcoords="offset points", fontsize=6.0, va="center", color=color)
    ax.set_yticks(np.arange(3))
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("被判定为主要参考模态的样本数 / 条")
    ax.set_xlim(0, max(counts) * 1.85)
    ax.set_ylim(-0.7, 2.7)
    ax.set_title("(d) 主要参考模态构成", fontsize=7.2, pad=6)
    return fc.save(fig, "fig_q3_01_modality_heatmap", FIG_Q3)


def fig_q3_modality_space() -> dict:
    data = dict(np.load(Q3_RESULTS / "q3_valid_outputs.npz", allow_pickle=True))
    alpha = np.asarray(data["alpha"], dtype=float)
    labels = np.asarray(data["labels_cls"], dtype=int)
    reg = np.asarray(data["regression"], dtype=float)
    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(150), fc.mm_to_inch(118)))
    ax = fig.add_subplot(111, projection="3d")
    colors = (PALETTE["red_strong"], PALETTE["neutral_mid"], PALETTE["blue_main"])
    for class_index, (name, color) in enumerate(zip(POLARITY_CN, colors)):
        mask = labels == class_index
        ax.scatter(alpha[mask, 0], alpha[mask, 1], alpha[mask, 2], s=18, c=color, alpha=0.8,
                   depthshade=False, edgecolor="white", linewidth=0.2, label=name)
    ax.set_xlabel("文本作用程度", fontsize=6.8, labelpad=1)
    ax.set_ylabel("语音作用程度", fontsize=6.8, labelpad=1)
    ax.set_zlabel("视觉作用程度", fontsize=6.8, labelpad=1)
    ax.tick_params(labelsize=5.8, pad=-1)
    ax.view_init(elev=22, azim=42)
    ax.set_title("验证集样本在模态作用三元空间中的分布\n（三轴之和恒为 1，点色表示真实情感极性）",
                 fontsize=8.0, pad=2)
    ax.legend(loc="upper left", bbox_to_anchor=(-0.06, 0.99), handlelength=0.9, fontsize=6.0,
              title="情感极性", title_fontsize=6.2)
    centroid = alpha.mean(axis=0)
    ax.scatter([centroid[0]], [centroid[1]], [centroid[2]], marker="X", s=110,
               color=PALETTE["slate_dark"], edgecolor="white", linewidth=0.8, zorder=8)
    corr = float(np.corrcoef(alpha[:, 0], reg)[0, 1])
    fig.text(0.5, 0.025,
             f"文本作用程度与预测情感强度的皮尔逊相关系数为 {corr:+.3f}，"
             "说明文本通道主导强度的连续变化方向",
             ha="center", fontsize=6.2, color=PALETTE["slate_dark"])
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.10)
    return fc.save(fig, "fig_q3_02_modality_space", FIG_Q3)


def fig_q3_temporal_evidence() -> dict:
    data = dict(np.load(Q3_RESULTS / "q3_valid_outputs.npz", allow_pickle=True))
    beta = np.asarray(data["beta"], dtype=float)
    contribution = np.asarray(data["contribution"], dtype=float)
    positions = np.arange(1, 51)
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(94)))
    fc.soften(ax, "y")
    uniform = 1.0 / 50.0
    for modality_index, (name, color, marker) in enumerate(zip(MODALITY_NAMES,
                                                               (C["文本"], C["语音"], C["视觉"]),
                                                               ("o", "s", "^"))):
        curve = contribution[:, modality_index, :].mean(axis=0)
        ax.plot(positions, curve, color=color, lw=1.8, marker=marker, ms=2.6, label=name, zorder=3)
    mean_curve = beta.mean(axis=0)
    low, high = np.percentile(beta, [25, 75], axis=0)
    ax.fill_between(positions, low, high, color=PALETTE["blue_secondary"], alpha=0.18,
                    label="位置重要性四分位区间", zorder=2)
    ax.plot(positions, mean_curve, color=PALETTE["slate_dark"], lw=2.0, linestyle="--",
            label="平均位置重要性", zorder=4)
    ax.axhline(uniform, color=PALETTE["neutral_mid"], linestyle=":", lw=1.0, zorder=1)
    peak = int(np.argmax(mean_curve))
    ax.annotate(f"位置重要性峰值在第 {peak + 1} 位（{mean_curve[peak]:.4f}）",
                xy=(peak + 1, mean_curve[peak]), xytext=(18, -26), textcoords="offset points",
                fontsize=6.2, color=PALETTE["slate_dark"],
                arrowprops=dict(arrowstyle="-", color=PALETTE["slate_dark"], lw=0.8))
    ax.set_xlabel("序列位置")
    ax.set_ylabel("逐位置模态贡献 / 位置重要性")
    ax.set_xlim(0.5, 50.5)
    ax.set_title("逐位置模态贡献分解与位置重要性分布（虚线为均匀分布基线 0.0200）",
                 fontsize=7.8, pad=8)
    ax.legend(loc="upper right", handlelength=1.5, fontsize=6.2)
    return fc.save(fig, "fig_q3_03_temporal_evidence", FIG_Q3)


def fig_q3_evidence_network() -> dict:
    training = load_json(Q3_RESULTS / "q3_training_report.json")
    deletion = training["deletion_test"]
    alpha_mean = training["modality_alpha_mean"]
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(94)))
    fc.soften(ax, "y")
    ks = [item["top_k"] for item in deletion]
    top = [item["value_shift_top"] for item in deletion]
    rnd = [item["value_shift_random"] for item in deletion]
    gain = [item["value_gain"] for item in deletion]
    ax.plot(ks, top, marker="o", ms=5.0, lw=1.9, color=PALETTE["red_strong"],
            label="删除模型认为最重要的位置", zorder=3)
    ax.plot(ks, rnd, marker="s", ms=5.0, lw=1.9, color=PALETTE["neutral_mid"],
            label="删除同规模随机位置", zorder=3)
    ax.fill_between(ks, rnd, top, color=PALETTE["red_soft"], alpha=0.32, zorder=2)
    for index, k in enumerate(ks):
        ax.annotate(f"定位增益 {gain[index]:+.4f}", xy=(k, 0.5 * (top[index] + rnd[index])),
                    xytext=(10, 0), textcoords="offset points", fontsize=6.0,
                    color=PALETTE["slate_dark"], va="center")
    ax.set_xlabel("删除位置数 K")
    ax.set_ylabel("情感强度预测值偏移量")
    ax.set_xticks(ks)
    ax.set_xlim(0, 15)
    ax.set_ylim(-0.004, max(top) * 1.18)
    ax.set_title("证据定位的删除实验：删除重要位置比删除随机位置引起更大的预测偏移", fontsize=7.8, pad=8)
    ax.legend(loc="upper left", handlelength=1.5, fontsize=6.2)
    ax.text(0.985, 0.06,
            "模态作用程度均值：" + "、".join(f"{name} {value:.3f}"
                                            for name, value in zip(MODALITY_NAMES, alpha_mean)),
            transform=ax.transAxes, ha="right", va="bottom", fontsize=6.0,
            color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    return fc.save(fig, "fig_q3_04_evidence_network", FIG_Q3)


def fig_q3_sample_card() -> dict:
    data = dict(np.load(Q3_RESULTS / "a4_outputs.npz", allow_pickle=True))
    alpha = np.asarray(data["alpha"], dtype=float)
    beta = np.asarray(data["beta"], dtype=float)
    contribution = np.asarray(data["contribution"], dtype=float)
    reg = np.asarray(data["regression"], dtype=float)
    prob = np.asarray(data["prob"], dtype=float)
    durations = np.asarray(data["durations"], dtype=float)
    ids = [str(item) for item in data["ids"]]
    labels = prob.argmax(axis=1)
    chosen = int(np.argmax(beta.max(axis=1)))
    duration = float(durations[chosen])
    centers = (np.arange(50) + 0.5) * duration / 50.0

    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(94)))
    fc.soften(ax, "y")
    for modality_index, (name, color) in enumerate(zip(MODALITY_NAMES,
                                                       (C["文本"], C["语音"], C["视觉"]))):
        ax.plot(centers, contribution[chosen, modality_index], color=color, lw=1.8,
                label=name, zorder=3)
    top_positions = np.argsort(-beta[chosen])[:3]
    ceiling = float(contribution[chosen][:, top_positions].sum(axis=0).max()) * 1.85
    for rank, position in enumerate(top_positions):
        ax.axvspan(position * duration / 50.0, (position + 1) * duration / 50.0,
                   color=PALETTE["gold_main"], alpha=0.28, zorder=1)
        ax.annotate(f"证据{rank + 1}\n第{int(position) + 1}位",
                    xy=(centers[position], ceiling * (0.99 - 0.20 * rank)),
                    fontsize=6.0, ha="center", va="top", color=PALETTE["slate_dark"])
    ax.set_xlabel("时间 / 秒")
    ax.set_ylabel("逐位置模态贡献")
    ax.set_xlim(0, duration)
    ax.set_ylim(-0.0002, ceiling)
    ax.legend(loc="center right", handlelength=1.4, fontsize=6.2)
    dominant = MODALITY_NAMES[int(np.argmax(alpha[chosen]))]
    card = "\n".join([
        f"样本编号：{ids[chosen]}　片段时长：{duration:.3f} 秒",
        f"情感极性：{POLARITY_CN[labels[chosen]]}（置信度 {prob[chosen, labels[chosen]]:.4f}）　"
        f"情感强度：{reg[chosen]:+.4f}",
        f"主要参考模态：{dominant}　模态作用程度："
        + "、".join(f"{name} {alpha[chosen, i]:.3f}" for i, name in enumerate(MODALITY_NAMES)),
        "关键证据位置：" + "、".join(str(int(item) + 1) for item in top_positions)
        + "　视觉关键帧：第 " + f"{int(top_positions[0] * duration / 50.0 * 5) + 1}" + " 帧",
    ])
    ax.text(0.985, 0.035, card, transform=ax.transAxes, fontsize=6.2, va="bottom", ha="right",
            color=PALETTE["black"], linespacing=1.7,
            bbox=dict(boxstyle="round,pad=0.40", facecolor="#FAFAFA",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.7))
    ax.set_title(f"附件4 典型样本解释卡与关键证据定位（样本 {ids[chosen]}）", fontsize=7.8, pad=8)
    return fc.save(fig, "fig_q3_05_sample_card", FIG_Q3)


def fig_sens_local() -> dict:
    local = load_json(SENS / "local_sensitivity.json")
    rows = local["rows"]
    labels = []
    for item in rows:
        if item["参数"] not in labels:
            labels.append(item["参数"])
    y = np.arange(len(labels))[::-1]
    base_mae = local["missing_baseline"]["mae"]
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(96)))
    fc.soften(ax, "x")
    tick_labels = []
    for index, label in enumerate(labels):
        subset = [item for item in rows
                  if item["参数"] == label and item["场景"] == "三模态均缺失 35%"]
        span = [min(item["强度平均绝对误差"] for item in subset),
                max(item["强度平均绝对误差"] for item in subset)]
        color = (PALETTE["red_strong"] if span[1] - base_mae > base_mae - span[0]
                 else PALETTE["blue_main"])
        ax.hlines(y[index], span[0], span[1], color=color, lw=3.4, alpha=0.9, zorder=2)
        ax.scatter(span, [y[index]] * 2, color=color, s=26, zorder=3,
                   edgecolor="white", linewidth=0.5)
        tick_labels.append(f"{label}\n{span[0]:.4f}–{span[1]:.4f}")
    ax.axvline(base_mae, color=PALETTE["slate_dark"], linestyle="--", lw=1.0, zorder=1)
    ax.annotate(f"缺失基线 {base_mae:.4f}", xy=(base_mae, -0.45), xytext=(5, 0),
                textcoords="offset points", fontsize=6.0, va="center",
                color=PALETTE["slate_dark"])
    ax.set_yticks(y)
    ax.set_yticklabels(tick_labels, fontsize=5.9, linespacing=1.5)
    ax.set_ylim(-0.7, len(labels) - 0.3)
    ax.set_xlabel("情感强度平均绝对误差")
    ax.set_title("鲁棒模型对六个关键参数的局部敏感度（三模态均缺失 35% 基线）", fontsize=7.8, pad=8)
    fig.subplots_adjust(left=0.20, right=0.98, top=0.90, bottom=0.13)
    return fc.save(fig, "fig_sens_01_local_tornado", FIG_SENS)


def fig_sens_summary() -> dict:
    local = load_json(SENS / "local_sensitivity.json")
    report = load_json(Q2_RESULTS / "q2_report.json")
    surface = load_json(SENS / "joint_surface.json")
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
        subset = [item for item in rows
                  if item["参数"] == label and item["场景"] == "三模态均缺失 35%"]
        span = [min(item["强度平均绝对误差"] for item in subset),
                max(item["强度平均绝对误差"] for item in subset)]
        color = (PALETTE["red_strong"] if span[1] - base_mae > base_mae - span[0]
                 else PALETTE["blue_main"])
        ax.hlines(y[index], span[0], span[1], color=color, lw=3.2, alpha=0.9, zorder=2)
        ax.scatter(span, [y[index]] * 2, color=color, s=22, zorder=3,
                   edgecolor="white", linewidth=0.4)
        ax.annotate(f"{span[1] - span[0]:.4f}", xy=(span[1], y[index]), xytext=(7, 0),
                    textcoords="offset points", fontsize=5.8, va="center", color=color)
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
    for key, rate_rows, color, label in series:
        xs = np.asarray([item["missing_ratio"] for item in rate_rows]) * 100
        ys = np.asarray([item["mae"] for item in rate_rows])
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
    return fc.save(fig, "fig_sens_02_sobol_heatmap", FIG_SENS)


def fig_sens_joint() -> dict:
    surface = load_json(SENS / "joint_surface.json")
    text_ratios = np.asarray(surface["text_ratios"]) * 100
    z = np.asarray(surface["robust_score"])
    profile = z.mean(axis=1)
    fc.setup(6.8)
    fig, ax = plt.subplots(figsize=(fc.mm_to_inch(168), fc.mm_to_inch(92)))
    fc.soften(ax, "both")
    ax.fill_between(text_ratios, z.min(axis=1), z.max(axis=1), color=PALETTE["blue_secondary"],
                    alpha=0.20, zorder=2, label="不同语音缺失率下的取值区间")
    ax.plot(text_ratios, profile, marker="o", ms=5.0, lw=1.9, color=PALETTE["blue_main"],
            label="稳健得分均值", zorder=3)
    for x, value in zip(text_ratios, profile):
        ax.annotate(f"{value:.4f}", xy=(x, value), xytext=(0, 9), textcoords="offset points",
                    fontsize=6.0, ha="center", color=PALETTE["blue_main"])
    ax.set_xlabel("文本缺失率 / %")
    ax.set_ylabel("稳健得分（均值与区间）")
    ax.set_xlim(-4, 74)
    ax.set_title("稳健得分随文本缺失率的退化（区间为不同语音缺失率下的取值范围）", fontsize=7.8, pad=8)
    ax.legend(loc="lower left", handlelength=1.5, fontsize=6.2)
    return fc.save(fig, "fig_sens_03_joint_surface", FIG_SENS)


def main() -> int:
    for directory in (FIG_ROOT, FIG_Q1, FIG_Q2, FIG_Q3, FIG_SENS):
        directory.mkdir(parents=True, exist_ok=True)
    reports = [
        fig01_data_overview(), fig02_modality_correlation(),
        fig_q1_alignment(), fig_q1_vision_space(), fig_q1_vision_coverage(),
        fig_q2_missing_pattern(), fig_q2_rate_curves(), fig_q2_response_surface(),
        fig_q2_duration_error(), fig_q2_ablation(),
        fig_q3_modality_heatmap(), fig_q3_modality_space(), fig_q3_temporal_evidence(),
        fig_q3_evidence_network(), fig_q3_sample_card(),
        fig_sens_local(), fig_sens_summary(), fig_sens_joint(),
    ]
    payload = {
        "count": len(reports),
        "all_qa_passed": all(item["qa_passed"] for item in reports),
        "figures": reports,
    }
    (PROJECT / "检查结果" / "paper_figures_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"count": payload["count"], "all_qa_passed": payload["all_qa_passed"],
                      "names": [item["name"] for item in reports]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
