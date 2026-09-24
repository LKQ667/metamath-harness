from __future__ import annotations

import json
import re
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
OUT = PROJECT / "Q1"
FIG = OUT / "figures"
DATA = PROJECT / "data" / "processed"
POLARITY_CN = ("负向", "中性", "正向")
TOKEN_RE = re.compile(r"[a-z0-9']+")


def load_features() -> dict:
    return dict(np.load(OUT / "features_a1_100.npz", allow_pickle=True))


def tokens_of(text: str) -> list[str]:
    return TOKEN_RE.findall(str(text).lower().replace("’", "'"))


def fig_q1_01_alignment() -> dict:
    data = load_features()
    labels = np.asarray(data["labels_reg"], dtype=float)
    durations = np.asarray(data["durations"], dtype=float)
    audio = np.asarray(data["audio"], dtype=np.float64)
    vision = np.asarray(data["vision"], dtype=np.float64)
    text = np.asarray(data["text"], dtype=np.float64)
    raw_text = [str(item) for item in data["raw_text"]]

    order = np.argsort(np.abs(labels))[::-1]
    chosen = None
    for index in order:
        token_count = len(tokens_of(raw_text[index]))
        if 8.0 <= durations[index] <= 14.0 and token_count >= 12:
            chosen = int(index)
            break
    if chosen is None:
        chosen = int(order[0])

    duration = durations[chosen]
    seq = np.arange(50)
    edges = np.linspace(0.0, duration, 51)
    centers = 0.5 * (edges[:-1] + edges[1:])
    safe_id = str(data["ids"][chosen]).replace("$", "-")
    tokens = tokens_of(raw_text[chosen])
    total = len(tokens)
    per_position = []
    for k in range(50):
        start = int(np.floor(k * total / 50))
        stop = int(np.floor((k + 1) * total / 50))
        if stop <= start:
            stop = min(start + 1, total)
        per_position.append(" ".join(tokens[start:stop]) or "—")

    fc.setup(6.6)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(132)))
    grid = fig.add_gridspec(4, 1, height_ratios=[0.62, 1.35, 1.20, 0.82], hspace=0.62)

    ax = fig.add_subplot(grid[0, 0])
    ax.set_xlim(0, duration)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    for k in range(0, 50, 2):
        ax.axvline(edges[k], color="#E6E6E6", linewidth=0.5, zorder=0)
    for k in range(50):
        if k % 3:
            continue
        ax.text(centers[k], 0.60, per_position[k], rotation=90, fontsize=5.0,
                color=PALETTE["blue_main"], ha="center", va="bottom")
    ax.text(0.0, 0.10, f"文本词元按位置等分：共 {total} 个词元，位置 k 覆盖词元区间 "
                       f"[floor(k·{total}/50), floor((k+1)·{total}/50))",
            transform=ax.transAxes, fontsize=6.0, color=PALETTE["slate_dark"])
    ax.set_title(f"(a) 典型样本文本通道时序组织（样本 {safe_id}，时长 {duration:.3f} 秒）",
                 fontsize=7.2, pad=5)

    ax = fig.add_subplot(grid[1, 0])
    mel = audio[chosen][:, :64].T
    im = ax.imshow(mel, aspect="auto", origin="lower", cmap="magma",
                   extent=[0, duration, 0, 64], interpolation="nearest")
    ax.set_ylabel("梅尔带序号")
    ax.set_title("(b) 语音通道：64 个梅尔带的对数功率（按 50 位置栅格聚合）", fontsize=7.2, pad=5)
    for k in range(0, 51, 5):
        ax.axvline(edges[k], color="white", linewidth=0.35, alpha=0.45)
    bar = fig.colorbar(im, ax=ax, fraction=0.030, pad=0.012)
    bar.set_label("对数功率 / dB", fontsize=6.2)
    bar.ax.tick_params(labelsize=5.8)

    ax = fig.add_subplot(grid[2, 0])
    vis = vision[chosen]
    lines = (("亮度均值", 0, PALETTE["blue_main"]), ("饱和度均值", 2, PALETTE["orange_main"]),
             ("色调熵", 14, PALETTE["teal_main"]), ("帧间灰度差", 31, PALETTE["red_strong"]))
    for name, column, color in lines:
        values = vis[:, column]
        normalized = (values - values.min()) / max(float(np.ptp(values)), 1e-9)
        ax.plot(centers, normalized, marker="o", ms=2.4, lw=1.4, color=color, label=name, zorder=3)
    fc.soften(ax, "y")
    ax.set_ylabel("归一化取值")
    ax.set_xlim(0, duration)
    ax.set_ylim(-0.12, 1.42)
    ax.legend(loc="upper center", ncol=4, handlelength=1.4, columnspacing=1.0,
              bbox_to_anchor=(0.5, 1.02))
    ax.set_title("(c) 视觉通道：帧级颜色与运动统计量（按 50 位置栅格聚合）", fontsize=7.2, pad=5)

    ax = fig.add_subplot(grid[3, 0])
    audio_energy = np.abs(audio[chosen]).sum(axis=1)
    vision_energy = np.abs(vision[chosen]).sum(axis=1)
    text_norm = np.linalg.norm(text[chosen], axis=1)
    for name, values, color, marker in (
        ("文本特征范数", text_norm, PALETTE["blue_main"], "o"),
        ("语音特征绝对和", audio_energy, PALETTE["orange_main"], "s"),
        ("视觉特征绝对和", vision_energy, PALETTE["teal_main"], "^"),
    ):
        scaled = values / max(values.max(), 1e-9)
        ax.plot(centers, scaled, marker=marker, ms=2.6, lw=1.3, color=color, label=name, zorder=3)
    fc.soften(ax, "y")
    ax.set_xlabel("时间 / 秒")
    ax.set_ylabel("归一化强度")
    ax.set_xlim(0, duration)
    ax.set_ylim(-0.12, 1.55)
    ax.legend(loc="upper center", ncol=3, handlelength=1.4, columnspacing=1.0,
              bbox_to_anchor=(0.5, 1.02))
    ax.set_title("(d) 三模态在同一时间轴上的对齐核验", fontsize=7.2, pad=5)

    info = {"sample": str(data["ids"][chosen]), "duration": float(duration),
            "tokens": total, "label": float(labels[chosen])}
    (OUT / "alignment_diagnostic.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                                   encoding="utf-8")
    return fc.save(fig, "fig_q1_01_alignment", FIG)


def fig_q1_02_timeline() -> dict:
    data = load_features()
    durations = np.asarray(data["durations"], dtype=float)
    labels = np.asarray(data["labels_reg"], dtype=float)
    text = np.asarray(data["text"], dtype=np.float64)
    audio = np.asarray(data["audio"], dtype=np.float64)
    vision = np.asarray(data["vision"], dtype=np.float64)
    token_counts = np.asarray([len(tokens_of(item)) for item in data["raw_text"]], dtype=float)

    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(80)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.0, 1.05], wspace=0.38)

    ax = fig.add_subplot(grid[0, 0])
    ax.hlines(np.arange(len(durations)), 0, durations, color=PALETTE["neutral_light"], lw=0.6, zorder=1)
    order = np.argsort(durations)
    colors = np.where(labels > 0, PALETTE["blue_main"],
                      np.where(labels < 0, PALETTE["red_strong"], PALETTE["neutral_mid"]))
    ax.scatter(durations[order], np.arange(len(order)), c=colors[order], s=9, zorder=3,
               edgecolor="white", linewidth=0.2)
    fc.soften(ax, "x")
    ax.set_xlabel("片段时长 / 秒")
    ax.set_ylabel("样本序号（按时长升序）")
    ax.set_yticks([])
    ax.set_xlim(0, 31)
    ax.set_title("(a) 100 条样本时长分布与情感极性", fontsize=7.2, pad=6)
    median = float(np.median(durations))
    ax.axvline(median, color=PALETTE["slate_dark"], linestyle="--", lw=1.0, zorder=2)
    ax.annotate(f"中位时长 {median:.3f} 秒", xy=(median, 62), xytext=(median + 3.4, 48),
                fontsize=6.0, color=PALETTE["slate_dark"],
                arrowprops=dict(arrowstyle="-", color=PALETTE["slate_dark"], lw=0.7))
    handles = [Line2D([], [], marker="o", linestyle="", color=color, ms=4.5, label=name)
               for color, name in zip((PALETTE["red_strong"], PALETTE["neutral_mid"], PALETTE["blue_main"]),
                                      POLARITY_CN)]
    ax.legend(handles=handles, loc="lower right", handlelength=1.0, title="情感极性", title_fontsize=6.2)

    ax = fig.add_subplot(grid[0, 1])
    ax.scatter(durations, token_counts, s=17, c=colors, alpha=0.85, edgecolor="white",
               linewidth=0.35, zorder=3)
    slope = np.polyfit(durations, token_counts, 1)
    xs = np.linspace(durations.min(), durations.max(), 60)
    ax.plot(xs, np.polyval(slope, xs), color=PALETTE["slate_dark"], linestyle="--", lw=1.1, zorder=2)
    fc.soften(ax, "both")
    ax.set_xlabel("片段时长 / 秒")
    ax.set_ylabel("英文词元数 / 个")
    r = float(np.corrcoef(durations, token_counts)[0, 1])
    ax.set_title("(b) 时长与词元数的线性关系", fontsize=7.2, pad=6)
    ax.set_xlim(0, 33)
    ax.set_ylim(0, 78)
    ax.text(0.96, 0.06, f"皮尔逊相关系数 r = {r:.3f}\n平均每词元 {(durations / np.maximum(token_counts, 1)).mean():.3f} 秒",
            transform=ax.transAxes, fontsize=6.0, ha="right", va="bottom",
            color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    grid_seconds = durations / 50.0
    series = (
        ("文本", grid_seconds, PALETTE["blue_main"], "o"),
        ("语音", grid_seconds, PALETTE["orange_main"], "s"),
        ("视觉", grid_seconds, PALETTE["teal_main"], "^"),
    )
    bins = np.linspace(0, 0.7, 22)
    for name, values, color, marker in series:
        counts, edges = np.histogram(values, bins=bins)
        centers = 0.5 * (edges[:-1] + edges[1:])
        ax.plot(centers, counts, marker=marker, ms=3.0, lw=1.4, color=color, label=name, zorder=3)
    ax.set_xlabel("对齐粒度（每位置覆盖时长）/ 秒")
    ax.set_ylabel("样本数 / 条")
    ax.set_title("(c) 三模态对齐粒度分布", fontsize=7.2, pad=6)
    ax.legend(loc="upper right", handlelength=1.4)
    ax.text(0.03, 0.96,
            f"三模态共用同一栅格：\n粒度 = 片段时长 / 50\n最小 {grid_seconds.min():.4f} 秒，"
            f"最大 {grid_seconds.max():.4f} 秒",
            transform=ax.transAxes, fontsize=5.9, va="top", color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))

    return fc.save(fig, "fig_q1_02_timeline", FIG)


def fig_q1_03_feature_space() -> dict:
    """三张独立单面板图：每个模态一张三维投影图。"""
    data = load_features()
    labels = np.asarray(data["labels_cls"], dtype=int)
    text = np.asarray(data["text"], dtype=np.float64).mean(axis=1)
    audio = np.asarray(data["audio"], dtype=np.float64).mean(axis=1)
    vision = np.asarray(data["vision"], dtype=np.float64).mean(axis=1)
    text[:, 0] = np.sign(text[:, 0]) * np.log1p(np.abs(text[:, 0]))
    audio[:, 0] = np.sign(audio[:, 0]) * np.log1p(np.abs(audio[:, 0]))

    def standardize(matrix: np.ndarray) -> np.ndarray:
        mean = matrix.mean(axis=0)
        std = matrix.std(axis=0)
        std[std < 1e-9] = 1.0
        return (matrix - mean) / std

    panels = (
        ("text", standardize(text), "文本", PALETTE["blue_main"]),
        ("audio", standardize(audio), "语音", PALETTE["orange_main"]),
        ("vision", standardize(vision), "视觉", PALETTE["teal_main"]),
    )
    colors = (PALETTE["red_strong"], PALETTE["neutral_mid"], PALETTE["blue_main"])
    reports = []
    summary = {}
    for key, matrix, name, accent in panels:
        centered = matrix - matrix.mean(axis=0)
        u, s, _ = np.linalg.svd(centered, full_matrices=False)
        coords = u[:, :3] * s[:3]
        variance = (s ** 2 / (s ** 2).sum())[:3] * 100
        centroids = np.stack([coords[labels == c].mean(axis=0) for c in range(3)])
        spread = np.mean([coords[labels == c].std(axis=0).mean() for c in range(3)])
        separation = float(np.mean(np.linalg.norm(
            centroids[:, None, :] - centroids[None, :, :], axis=2)) / max(spread, 1e-9))
        summary[key] = {"cumulative_variance": float(variance.sum()),
                        "separation": separation}

        fc.setup(6.6)
        fig = plt.figure(figsize=(fc.mm_to_inch(128), fc.mm_to_inch(104)))
        ax = fig.add_subplot(111, projection="3d")
        for class_index, color in enumerate(colors):
            mask = labels == class_index
            ax.scatter(coords[mask, 0], coords[mask, 1], coords[mask, 2], s=15, c=color,
                       alpha=0.85, depthshade=False, edgecolor="white", linewidth=0.18,
                       label=POLARITY_CN[class_index])
        for class_index, color in enumerate(colors):
            ax.scatter(centroids[class_index, 0], centroids[class_index, 1], centroids[class_index, 2],
                       s=76, marker="X", c=color, edgecolor="black", linewidth=0.7, zorder=6)
        ax.set_xlabel(f"主成分1（{variance[0]:.1f}%）", fontsize=6.4, labelpad=-1)
        ax.set_ylabel(f"主成分2（{variance[1]:.1f}%）", fontsize=6.4, labelpad=-1)
        ax.set_zlabel(f"主成分3（{variance[2]:.1f}%）", fontsize=6.4, labelpad=-2)
        ax.tick_params(labelsize=5.4, pad=-1)
        ax.view_init(elev=20, azim=38)
        ax.set_title(f"{name}模态特征空间三维投影\n前三个主成分累计方差 {variance.sum():.1f}%，"
                     f"类心分离度 {separation:.2f}", fontsize=7.4, pad=2, color=accent)
        ax.legend(loc="upper left", bbox_to_anchor=(-0.10, 0.99), handlelength=0.9,
                  fontsize=6.0, title="情感极性", title_fontsize=6.2)
        fig.text(0.5, 0.022,
                 "叉号为类别中心；类别中心在投影空间中高度重叠，说明情感判别依赖时序局部结构而非全局均值",
                 ha="center", fontsize=6.0, color=PALETTE["slate_dark"])
        fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.10)
        reports.append(fc.save(fig, f"fig_q1_03_{key}_space", FIG))
    (OUT / "feature_space_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return reports


def fig_q1_04_mask_map() -> dict:
    """三张独立单面板图：每个模态的有效位置覆盖图。"""
    data = load_features()
    durations = np.asarray(data["durations"], dtype=float)
    labels = np.asarray(data["labels_cls"], dtype=int)
    order = np.lexsort((durations, labels))
    cmap = LinearSegmentedColormap.from_list("coverage", ["#F2F2F2", PALETTE["blue_secondary"]])
    reports = []
    summary = {}
    for key, name, accent in (("text", "文本", PALETTE["blue_main"]),
                              ("audio", "语音", PALETTE["orange_main"]),
                              ("vision", "视觉", PALETTE["teal_main"])):
        matrix = np.asarray(data[f"{key}_valid"], dtype=float)
        summary[key] = {"mean_valid": float(matrix.sum(axis=1).mean()),
                        "min_valid": int(matrix.sum(axis=1).min()),
                        "max_valid": int(matrix.sum(axis=1).max())}
        fc.setup(6.6)
        fig = plt.figure(figsize=(fc.mm_to_inch(128), fc.mm_to_inch(104)))
        ax = fig.add_subplot(111)
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
        ax.set_title(f"{name}通道有效位置覆盖\n有效位置均值 {matrix.sum(axis=1).mean():.2f} / 50",
                     fontsize=7.4, pad=6, color=accent)
        bar = fig.colorbar(im, ax=ax, fraction=0.040, pad=0.035, ticks=[0, 1])
        bar.set_label("有效标志", fontsize=6.2)
        bar.ax.set_yticklabels(["填充", "有效"], fontsize=5.8)
        fig.subplots_adjust(left=0.11, right=0.98, top=0.88, bottom=0.10)
        reports.append(fc.save(fig, f"fig_q1_04_{key}_coverage", FIG))
    (OUT / "coverage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return reports


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    reports = [fig_q1_01_alignment(), fig_q1_02_timeline()]
    reports.extend(fig_q1_03_feature_space())
    reports.extend(fig_q1_04_mask_map())
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
