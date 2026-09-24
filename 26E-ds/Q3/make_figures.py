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
OUT = PROJECT / "Q3"
FIG = OUT / "figures"
RESULTS = OUT / "results"
POLARITY_CN = ("负向", "中性", "正向")
MODALITY_NAMES = ("文本", "语音", "视觉")


def load_valid() -> dict:
    return dict(np.load(RESULTS / "q3_valid_outputs.npz", allow_pickle=True))


def load_a4() -> dict:
    return dict(np.load(RESULTS / "a4_outputs.npz", allow_pickle=True))


def load_training() -> dict:
    return json.loads((RESULTS / "q3_training_report.json").read_text(encoding="utf-8"))


def fig_q3_01_modality_heatmap() -> dict:
    data = load_valid()
    alpha = np.asarray(data["alpha"], dtype=float)
    labels = np.asarray(data["labels_cls"], dtype=int)
    order = np.lexsort((-alpha[:, 0], labels))
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(84)))
    grid = fig.add_gridspec(1, 4, width_ratios=[1.15, 1.0, 0.92, 0.92], wspace=0.36)

    ax = fig.add_subplot(grid[0, 0])
    im = ax.imshow(alpha[order].T, aspect="auto", cmap="magma", interpolation="nearest",
                   extent=[0, len(order), 3, 0], vmin=0.0, vmax=1.0)
    ax.set_yticks([0.5, 1.5, 2.5])
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("验证集样本（按极性、文本作用程度排序）")
    ax.set_title("(a) 逐样本模态作用程度", fontsize=7.2, pad=6)
    starts = np.concatenate([[0], np.where(np.diff(labels[order]) != 0)[0] + 1])
    ends = np.concatenate([starts[1:], [len(order)]])
    for start, end in zip(starts, ends):
        ax.axvline(start, color="white", lw=0.7, linestyle="--")
        ax.text(0.5 * (start + end), -0.22, POLARITY_CN[labels[order][start]], ha="center",
                va="bottom", fontsize=6.0, color=PALETTE["slate_dark"])
    bar = fig.colorbar(im, ax=ax, fraction=0.036, pad=0.035)
    bar.set_label("模态作用程度", fontsize=6.2)
    bar.ax.tick_params(labelsize=5.8)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "x")
    y = np.arange(3)[::-1]
    for index, (name, color) in enumerate(zip(MODALITY_NAMES, (C["文本"], C["语音"], C["视觉"]))):
        values = alpha[:, index]
        mean = float(values.mean())
        low, high = np.percentile(values, [25, 75])
        ax.hlines(y[index], low, high, color=color, lw=4.0, alpha=0.35, zorder=2)
        ax.scatter([mean], [y[index]], color=color, s=44, zorder=4, edgecolor="white", linewidth=0.6)
        ax.annotate(f"均值 {mean:.3f}，四分位距 {high - low:.3f}", xy=(mean, y[index]),
                    xytext=(0, 12), textcoords="offset points", fontsize=5.9, ha="center", color=color)
    ax.set_yticks(y)
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("模态作用程度")
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.85, 2.65)
    ax.set_title("(b) 模态作用程度的分布", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    for class_index, (name, color, marker) in enumerate(zip(POLARITY_CN,
                                                            (PALETTE["red_strong"], PALETTE["neutral_mid"],
                                                             PALETTE["blue_main"]),
                                                            ("o", "s", "^"))):
        mask = labels == class_index
        if mask.sum() == 0:
            continue
        values = alpha[mask].mean(axis=0)
        xs = np.arange(3)
        ax.plot(xs, values, marker=marker, ms=4.4, lw=1.7, color=color, label=name, zorder=3)
        for x, value in zip(xs, values):
            ax.annotate(f"{value:.3f}", xy=(x, value), xytext=(0, 7), textcoords="offset points",
                        fontsize=5.7, ha="center", color=color)
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(MODALITY_NAMES)
    ax.set_ylabel("平均模态作用程度")
    ax.set_ylim(0, 0.62)
    ax.set_title("(c) 不同极性下的模态作用", fontsize=7.2, pad=6)
    ax.legend(loc="upper right", handlelength=1.2, fontsize=5.9)

    ax = fig.add_subplot(grid[0, 3])
    fc.soften(ax, "y")
    dominant = alpha.argmax(axis=1)
    counts = [int((dominant == index).sum()) for index in range(3)]
    x = np.arange(3)
    for index, (name, color, count) in enumerate(zip(MODALITY_NAMES,
                                                     (C["文本"], C["语音"], C["视觉"]), counts)):
        ax.hlines(index, 0, count, color=color, lw=2.6, zorder=2)
        ax.scatter([count], [index], color=color, s=40, zorder=3)
        ax.annotate(f"{count} 条（{count / len(dominant) * 100:.1f}%）", xy=(count, index),
                    xytext=(6, -1), textcoords="offset points", fontsize=5.9, va="center", color=color)
    fc.soften(ax, "x")
    ax.set_yticks(x)
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("被判定为主要参考模态的样本数 / 条")
    ax.set_xlim(0, max(counts) * 1.75)
    ax.set_ylim(-0.7, 2.7)
    ax.set_title("(d) 主要参考模态构成", fontsize=7.2, pad=6)
    return fc.save(fig, "fig_q3_01_modality_heatmap", FIG)


def fig_q3_02_modality_space() -> dict:
    data = load_valid()
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
    ax.text(centroid[0], centroid[1], centroid[2] + 0.03,
            f"总体重心（{centroid[0]:.3f}, {centroid[1]:.3f}, {centroid[2]:.3f}）",
            fontsize=6.0, color=PALETTE["slate_dark"])
    corr = float(np.corrcoef(alpha[:, 0], reg)[0, 1])
    fig.text(0.5, 0.025,
             f"文本作用程度与预测情感强度的皮尔逊相关系数为 {corr:+.3f}，说明文本通道主导强度的连续变化方向",
             ha="center", fontsize=6.2, color=PALETTE["slate_dark"])
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.10)
    return fc.save(fig, "fig_q3_02_modality_space", FIG)


def fig_q3_03_temporal_evidence() -> dict:
    data = load_valid()
    beta = np.asarray(data["beta"], dtype=float)
    contribution = np.asarray(data["contribution"], dtype=float)
    labels = np.asarray(data["labels_cls"], dtype=int)
    reg = np.asarray(data["labels_reg"], dtype=float)
    positions = np.arange(1, 51)
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(84)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0], wspace=0.36)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    mean_curve = beta.mean(axis=0)
    low, high = np.percentile(beta, [25, 75], axis=0)
    ax.fill_between(positions, low, high, color=PALETTE["blue_secondary"], alpha=0.20,
                    label="四分位区间", zorder=2)
    ax.plot(positions, mean_curve, color=PALETTE["blue_main"], lw=1.8, label="平均位置重要性", zorder=3)
    uniform = 1.0 / 50.0
    ax.axhline(uniform, color=PALETTE["neutral_mid"], linestyle="--", lw=1.0, zorder=1)
    peak = int(np.argmax(mean_curve))
    ax.scatter([peak + 1], [mean_curve[peak]], color=PALETTE["red_strong"], s=34, zorder=4)
    ax.annotate(f"峰值位置 {peak + 1}（{mean_curve[peak]:.4f}）",
                xy=(peak + 1, mean_curve[peak]), xytext=(14, -16), textcoords="offset points",
                fontsize=6.0, color=PALETTE["red_strong"],
                arrowprops=dict(arrowstyle="-", color=PALETTE["red_strong"], lw=0.7))
    ax.set_xlabel("序列位置")
    ax.set_ylabel("位置重要性")
    ax.set_xlim(0.5, 50.5)
    ax.set_ylim(-0.002, float(mean_curve.max()) * 1.12)
    ax.set_title("(a) 位置重要性分布（均匀基线 %.4f）" % uniform, fontsize=7.2, pad=6)
    ax.legend(loc="upper right", handlelength=1.4, fontsize=5.9)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "y")
    for modality_index, (name, color, marker) in enumerate(zip(MODALITY_NAMES,
                                                               (C["文本"], C["语音"], C["视觉"]),
                                                               ("o", "s", "^"))):
        curve = contribution[:, modality_index, :].mean(axis=0)
        ax.plot(positions, curve, color=color, lw=1.7, marker=marker, ms=2.4, label=name, zorder=3)
    ax.set_xlabel("序列位置")
    ax.set_ylabel("逐位置模态贡献")
    ax.set_xlim(0.5, 50.5)
    ax.set_title("(b) 逐位置模态贡献分解", fontsize=7.2, pad=6)
    ax.legend(loc="upper right", handlelength=1.4, fontsize=5.9)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    front = contribution[:, :, :17].sum(axis=2)
    middle = contribution[:, :, 17:34].sum(axis=2)
    back = contribution[:, :, 34:].sum(axis=2)
    totals = contribution.sum(axis=2)
    ratios = np.stack([front, middle, back], axis=2) / np.maximum(totals[:, :, None], 1e-9)
    x = np.arange(3)
    for modality_index, (name, color) in enumerate(zip(MODALITY_NAMES,
                                                       (C["文本"], C["语音"], C["视觉"]))):
        values = ratios[:, modality_index, :].mean(axis=0) * 100
        ax.plot(x, values, marker="o", ms=4.4, lw=1.7, color=color, label=name, zorder=3)
        for xi, value in zip(x, values):
            ax.annotate(f"{value:.1f}", xy=(xi, value), xytext=(0, 7), textcoords="offset points",
                        fontsize=5.7, ha="center", color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(("序列前段\n（位置 1–17）", "序列中段\n（位置 18–34）", "序列后段\n（位置 35–50）"),
                       fontsize=6.0)
    ax.set_ylabel("该时段贡献占该模态总贡献的比例 / %")
    ax.set_ylim(17, 56)
    ax.set_title("(c) 三模态证据的时段分布", fontsize=7.2, pad=6)
    ax.legend(loc="upper right", ncol=3, handlelength=1.2, fontsize=5.9)
    return fc.save(fig, "fig_q3_03_temporal_evidence", FIG)


def fig_q3_04_evidence_network() -> dict:
    training = load_training()
    deletion = training["deletion_test"]
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(86)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.0, 1.05], wspace=0.40)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    ks = [item["top_k"] for item in deletion]
    top = [item["value_shift_top"] for item in deletion]
    rnd = [item["value_shift_random"] for item in deletion]
    gain = [item["value_gain"] for item in deletion]
    ax.plot(ks, top, marker="o", ms=4.6, lw=1.8, color=PALETTE["red_strong"],
            label="删除最重要位置", zorder=3)
    ax.plot(ks, rnd, marker="s", ms=4.6, lw=1.8, color=PALETTE["neutral_mid"],
            label="删除随机位置", zorder=3)
    ax.fill_between(ks, rnd, top, color=PALETTE["red_soft"], alpha=0.35, zorder=2)
    for index, k in enumerate(ks):
        ax.annotate(f"定位增益 {gain[index]:+.4f}", xy=(k, 0.5 * (top[index] + rnd[index])),
                    xytext=(9, 0), textcoords="offset points", fontsize=5.9,
                    color=PALETTE["slate_dark"], va="center")
    ax.set_xlabel("删除位置数 K")
    ax.set_ylabel("情感强度预测值偏移量")
    ax.set_xticks(ks)
    ax.set_xlim(0, 15)
    ax.set_title("(a) 证据定位的删除实验", fontsize=7.2, pad=6)
    ax.legend(loc="upper left", handlelength=1.4, fontsize=5.9)

    ax = fig.add_subplot(grid[0, 1])
    ax.set_axis_off()
    alpha_mean = training["modality_alpha_mean"]
    beta_mean = np.asarray(training["position_beta_mean"], dtype=float)
    dominant = int(np.argmax(alpha_mean))
    top_positions = np.argsort(-beta_mean)[:3] + 1
    nodes = {
        "evidence": (0.5, 0.88),
        "text": (0.16, 0.60),
        "audio": (0.50, 0.60),
        "vision": (0.84, 0.60),
        "prediction": (0.5, 0.28),
    }
    ax.set_xlim(0, 1)
    ax.set_ylim(0.05, 1.0)
    ax.text(nodes["evidence"][0], nodes["evidence"][1], "输入证据",
            ha="center", va="center", fontsize=6.6, color="white",
            bbox=dict(boxstyle="round,pad=0.34", facecolor=PALETTE["slate_dark"], edgecolor="none"))
    for index, (name, color) in enumerate(zip(MODALITY_NAMES, (C["文本"], C["语音"], C["视觉"]))):
        key = ("text", "audio", "vision")[index]
        width = 0.18 + 0.5 * alpha_mean[index]
        ax.text(nodes[key][0], nodes[key][1], f"{name}\n{alpha_mean[index]:.3f}",
                ha="center", va="center", fontsize=6.2, color="white",
                bbox=dict(boxstyle="round,pad=0.32", facecolor=color, edgecolor="none",
                          alpha=0.55 + 0.45 * alpha_mean[index] / max(alpha_mean)))
        ax.annotate("", xy=nodes[key], xytext=nodes["evidence"],
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=0.6 + 4.0 * alpha_mean[index],
                                    shrinkA=12, shrinkB=12, alpha=0.85))
    ax.text(nodes["prediction"][0], nodes["prediction"][1],
            f"情感预测\n极性 + 强度\n主要参考模态：{MODALITY_NAMES[dominant]}",
            ha="center", va="center", fontsize=6.2, color="white",
            bbox=dict(boxstyle="round,pad=0.36", facecolor=PALETTE["blue_main"], edgecolor="none"))
    for key in ("text", "audio", "vision"):
        ax.annotate("", xy=nodes["prediction"], xytext=nodes[key],
                    arrowprops=dict(arrowstyle="-|>", color=PALETTE["neutral_dark"], lw=1.0,
                                    shrinkA=12, shrinkB=14, alpha=0.7))
    ax.text(0.5, 0.10, f"关键证据位置：第 " + "、".join(str(int(item)) for item in top_positions) + " 位",
            ha="center", fontsize=6.2, color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.28", facecolor="#F2F2F2",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    ax.set_title("(b) 解释证据链结构（线宽为模态作用程度）", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    per_class = training["per_class"]
    x = np.arange(3)
    width = 0.26
    for modality_index, (name, color) in enumerate(zip(MODALITY_NAMES,
                                                       (C["文本"], C["语音"], C["视觉"]))):
        values = []
        for class_index, class_name in enumerate(POLARITY_CN):
            entry = per_class.get(class_name)
            values.append(entry["mean_alpha"][modality_index] if entry else np.nan)
        offset = (modality_index - 1) * width
        ax.hlines(np.arange(3) + offset, 0, values, color=color, lw=2.2, zorder=2)
        ax.scatter(values, np.arange(3) + offset, color=color, s=32, zorder=3)
        for y, value in zip(np.arange(3) + offset, values):
            ax.annotate(f"{value:.3f}", xy=(value, y), xytext=(6, -1), textcoords="offset points",
                        fontsize=5.7, va="center", color=color)
    ax.set_yticks(np.arange(3))
    ax.set_yticklabels(POLARITY_CN)
    ax.set_xlabel("平均模态作用程度")
    ax.set_xlim(0, 0.60)
    ax.set_ylim(-0.55, 2.55)
    ax.set_title("(c) 逐极性模态作用对比", fontsize=7.2, pad=6)
    ax.text(0.98, 0.04, "每类内自上而下依次为\n文本、语音、视觉", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=5.7, color=PALETTE["slate_dark"])
    return fc.save(fig, "fig_q3_04_evidence_network", FIG)


def fig_q3_05_sample_card() -> dict:
    data = load_a4()
    alpha = np.asarray(data["alpha"], dtype=float)
    beta = np.asarray(data["beta"], dtype=float)
    reg = np.asarray(data["regression"], dtype=float)
    prob = np.asarray(data["prob"], dtype=float)
    durations = np.asarray(data["durations"], dtype=float)
    ids = [str(item) for item in data["ids"]]
    labels = prob.argmax(axis=1)
    chosen = int(np.argmax(beta.max(axis=1)))
    duration = durations[chosen]
    centers = (np.arange(50) + 0.5) * duration / 50.0

    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(88)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.35, 1.0, 1.0], wspace=0.38)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    contribution = np.asarray(data["contribution"], dtype=float)[chosen]
    bottom = np.zeros(50)
    for modality_index, (name, color) in enumerate(zip(MODALITY_NAMES,
                                                       (C["文本"], C["语音"], C["视觉"]))):
        ax.plot(centers, contribution[modality_index], color=color, lw=1.7, label=name, zorder=3)
        ax.fill_between(centers, bottom, contribution[modality_index], color=color, alpha=0.22, zorder=2)
    top_positions = np.argsort(-beta[chosen])[:3]
    ceiling = max(contribution[:, top_positions].sum(axis=0).max() * 1.55, 0.002)
    for rank, position in enumerate(top_positions):
        ax.axvspan(position * duration / 50.0, (position + 1) * duration / 50.0,
                   color=PALETTE["gold_main"], alpha=0.28, zorder=1)
        ax.annotate(f"证据{rank + 1}　第{int(position) + 1}位",
                    xy=(centers[position], ceiling * (0.96 - 0.14 * rank)),
                    fontsize=5.8, ha="center", va="top", color=PALETTE["slate_dark"])
    ax.set_xlabel("时间 / 秒")
    ax.set_ylabel("逐位置模态贡献")
    ax.set_xlim(0, duration)
    ax.set_ylim(-0.0002, ceiling)
    ax.set_title(f"(a) 典型样本关键证据定位（样本 {ids[chosen]}，时长 {duration:.2f} 秒）",
                 fontsize=7.2, pad=6)
    ax.legend(loc="upper right", handlelength=1.4, fontsize=5.9)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "x")
    y = np.arange(3)[::-1]
    for index, (name, color) in enumerate(zip(MODALITY_NAMES, (C["文本"], C["语音"], C["视觉"]))):
        ax.hlines(y[index], 0, alpha[chosen, index], color=color, lw=2.6, zorder=2)
        ax.scatter([alpha[chosen, index]], [y[index]], color=color, s=38, zorder=3)
        ax.annotate(f"{alpha[chosen, index]:.3f}", xy=(alpha[chosen, index], y[index]),
                    xytext=(6, -1), textcoords="offset points", fontsize=6.0, va="center", color=color)
    ax.set_yticks(y)
    ax.set_yticklabels(MODALITY_NAMES)
    ax.set_xlabel("模态作用程度")
    ax.set_xlim(0, max(0.6, float(alpha[chosen].max()) * 1.4))
    ax.set_ylim(-0.7, 2.7)
    ax.set_title("(b) 三模态作用程度", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    ax.set_axis_off()
    top3 = [int(item) + 1 for item in np.argsort(-beta[chosen])[:3]]
    lines = [
        f"样本编号：{ids[chosen]}",
        f"片段时长：{duration:.3f} 秒",
        f"情感极性：{POLARITY_CN[labels[chosen]]}（置信度 {prob[chosen, labels[chosen]]:.4f}）",
        f"情感强度：{reg[chosen]:+.4f}",
        f"主要参考模态：{MODALITY_NAMES[int(np.argmax(alpha[chosen]))]}",
        "关键证据位置：" + "、".join(str(item) for item in top3),
        "关键证据时间窗：",
    ]
    for position in top3:
        start = (position - 1) * duration / 50.0
        end = position * duration / 50.0
        lines.append(f"    第 {position} 位　[{start:.2f}, {end:.2f}) 秒")
    lines.append(f"视觉关键帧：第 {int(top3[0] * duration / 50.0 * 5) + 1} 帧（5 帧/秒）")
    ax.text(0.02, 0.96, "\n".join(lines), transform=ax.transAxes, fontsize=6.2, va="top",
            family="Microsoft YaHei", color=PALETTE["black"],
            bbox=dict(boxstyle="round,pad=0.55", facecolor="#FAFAFA",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.7))
    ax.set_title("(c) 典型样本解释卡", fontsize=7.2, pad=6)
    return fc.save(fig, "fig_q3_05_sample_card", FIG)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    reports = [fig_q3_01_modality_heatmap(), fig_q3_02_modality_space(),
               fig_q3_03_temporal_evidence(), fig_q3_04_evidence_network(),
               fig_q3_05_sample_card()]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
