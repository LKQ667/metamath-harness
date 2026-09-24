from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

import fig_common as fc

PALETTE = fc.PALETTE
C = fc.MODALITY_COLORS
FIG = PROJECT / "figures"
DATA = PROJECT / "data" / "processed"
POLARITY_CN = ("负向", "中性", "正向")
POLARITY_EN = ("Negative", "Neutral", "Positive")


def load_summary() -> dict:
    return json.loads((DATA / "eda_summary.json").read_text(encoding="utf-8"))


def fig01_data_overview() -> dict:
    summary = load_summary()
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(74)))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.05, 0.95, 1.0], wspace=0.40)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    labels = np.asarray([summary["attachments"]["a2_splits"][key]["reg_mean"] for key in ("train", "valid", "test")])
    stds = np.asarray([summary["attachments"]["a2_splits"][key]["reg_std"] for key in ("train", "valid", "test")])
    x = np.arange(3)
    ax.errorbar(x, labels, yerr=stds, fmt="o", color=PALETTE["blue_main"], ms=6, lw=1.6,
                capsize=3.2, elinewidth=1.1, zorder=3)
    ax.axhline(0.0, color=PALETTE["neutral_mid"], linestyle="--", linewidth=0.8, zorder=1)
    summary_text = "\n".join(
        f"{name}：均值 {labels[index]:.3f}，标准差 {stds[index]:.3f}"
        for index, name in enumerate(("训练集", "验证集", "测试集"))
    )
    ax.text(0.5, 0.045, summary_text, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=6.0, color=PALETTE["slate_dark"], linespacing=1.45,
            bbox=dict(boxstyle="round,pad=0.30", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    ax.set_xticks(x)
    ax.set_xticklabels(("训练集", "验证集", "测试集"))
    ax.set_ylabel("连续情感强度（均值±标准差）")
    ax.set_xlim(-0.55, 2.55)
    ax.set_ylim(-1.75, 1.45)
    ax.set_title("(a) 三个划分的情感强度分布一致性", fontsize=7.2, pad=6)
    ax.text(0.02, 0.965, "虚线为中性基线 0", transform=ax.transAxes, fontsize=5.9,
            color=PALETTE["neutral_mid"], va="top")

    ax = fig.add_subplot(grid[0, 1])
    counts = np.asarray([[summary["attachments"]["a2_splits"][key]["cls_counts"][name]
                          for name in ("negative", "neutral", "positive")]
                         for key in ("train", "valid", "test")], dtype=float)
    ratio = counts / counts.sum(axis=1, keepdims=True) * 100.0
    colors = (PALETTE["red_strong"], PALETTE["neutral_mid"], PALETTE["blue_main"])
    markers = ("o", "s", "^")
    for column, (name, color, marker) in enumerate(zip(POLARITY_CN, colors, markers)):
        ax.plot(np.arange(3), ratio[:, column], marker=marker, color=color, lw=1.8, ms=5.5,
                label=name, zorder=3)
        for index in range(3):
            offset = 9 if column != 2 else 10
            ax.annotate(f"{ratio[index, column]:.1f}%", xy=(index, ratio[index, column]),
                        xytext=(-2, offset), textcoords="offset points", fontsize=5.8, color=color, ha="center")
    fc.soften(ax, "y")
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(("训练集", "验证集", "测试集"))
    ax.set_ylabel("类别占比 / %")
    ax.set_ylim(0, 88)
    ax.set_xlim(-0.45, 2.45)
    ax.legend(loc="upper center", ncol=3, handlelength=1.1, columnspacing=0.9,
              bbox_to_anchor=(0.5, 1.0))
    ax.set_title("(b) 情感极性类别占比", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 2])
    inventory = np.genfromtxt(DATA.parent / "raw" / "a1_media_inventory.csv", delimiter=",",
                              names=True, dtype=None, encoding="utf-8-sig")
    durations = np.asarray(inventory["duration_sec"], dtype=float)
    words = np.asarray(inventory["text_words"], dtype=float)
    labels_reg = np.asarray(inventory["label"], dtype=float)
    palette = np.where(labels_reg > 0, PALETTE["blue_main"],
                       np.where(labels_reg < 0, PALETTE["red_strong"], PALETTE["neutral_mid"]))
    ax.scatter(durations, words, s=17, c=palette, alpha=0.85, edgecolor="white", linewidth=0.35, zorder=3)
    fc.soften(ax, "both")
    slope = np.polyfit(durations, words, 1)
    xs = np.linspace(durations.min(), durations.max(), 50)
    ax.plot(xs, np.polyval(slope, xs), color=PALETTE["slate_dark"], linestyle="--", lw=1.1, zorder=2)
    r = float(np.corrcoef(durations, words)[0, 1])
    ax.set_xlabel("片段时长 / 秒")
    ax.set_ylabel("转写词数 / 词")
    ax.set_title("(c) 附件1 片段时长与转写长度", fontsize=7.2, pad=6)
    ax.set_ylim(0, 78)
    ax.set_xlim(0, 33)
    ax.text(0.03, 0.97, f"皮尔逊相关系数 r = {r:.3f}\n样本数 n = {len(durations)}",
            transform=ax.transAxes, fontsize=6.0, va="top", color=PALETTE["slate_dark"],
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))
    handles = [Line2D([], [], marker="o", linestyle="", color=color, ms=4.5, label=name)
               for color, name in zip((PALETTE["red_strong"], PALETTE["neutral_mid"], PALETTE["blue_main"]),
                                      POLARITY_CN)]
    ax.legend(handles=handles, loc="lower right", handlelength=1.0, title="情感极性",
              title_fontsize=6.2)

    return fc.save(fig, "fig01_data_overview", FIG)


def fig02_modality_statistics() -> dict:
    summary = load_summary()
    stats = {(item["split"], item["modality"]): item for item in summary["modality_stats"]}
    fc.setup(6.8)
    fig = plt.figure(figsize=(fc.mm_to_inch(183), fc.mm_to_inch(76)))
    grid = fig.add_gridspec(1, 3, width_ratios=[0.98, 1.02, 1.10], wspace=0.40)

    ax = fig.add_subplot(grid[0, 0])
    fc.soften(ax, "y")
    names = ("文本", "语音", "视觉")
    keys = ("text", "audio", "vision")
    for name, key, color, marker in zip(names, keys, (C["文本"], C["语音"], C["视觉"]), ("o", "s", "^")):
        values = [stats[("train", key)]["zero_ratio"] * 100, stats[("valid", key)]["zero_ratio"] * 100,
                  stats[("test", key)]["zero_ratio"] * 100]
        ax.plot(np.arange(3), values, marker=marker, color=color, lw=1.8, ms=5.5, label=name, zorder=3)
        for index, value in enumerate(values):
            ax.annotate(f"{value:.1f}", xy=(index, value), xytext=(-2, 8), textcoords="offset points",
                        fontsize=5.8, color=color, ha="center")
    ax.set_xticks(np.arange(3))
    ax.set_xticklabels(("训练集", "验证集", "测试集"))
    ax.set_ylabel("全零元素占比 / %")
    ax.set_xlim(-0.45, 2.45)
    ax.set_ylim(-4, 84)
    ax.legend(loc="upper center", ncol=3, handlelength=1.1, columnspacing=0.8,
              bbox_to_anchor=(0.5, 1.0))
    ax.set_title("(a) 三模态零值占比", fontsize=7.2, pad=6)

    ax = fig.add_subplot(grid[0, 1])
    fc.soften(ax, "y")
    dim_var = {key: stats[("train", key)]["dim_var_max"] / max(stats[("train", key)]["dim_var_median"], 1e-9)
               for key in keys}
    values = [dim_var[key] for key in keys]
    y = np.arange(3)[::-1]
    for index, (value, name, color) in enumerate(zip(values, names, (C["文本"], C["语音"], C["视觉"]))):
        ax.hlines(y[index], 1.0, value, color=color, lw=2.2, zorder=2)
        ax.scatter([value], [y[index]], color=color, s=30, zorder=3)
        ax.annotate(f"{value:,.0f} 倍", xy=(value, y[index]), xytext=(6, -2),
                    textcoords="offset points", fontsize=6.2, color=color)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlim(1.0, 4.0e7)
    ax.set_ylim(-0.9, 3.6)
    ax.set_xlabel("最大维度方差 / 中位维度方差（对数轴）")
    ax.set_title("(b) 维度方差量纲差异", fontsize=7.2, pad=6)
    ax.text(0.02, 0.98, "语音第 0 维量纲为 0–500，\n标准化前需单独做符号对数压缩",
            transform=ax.transAxes, fontsize=5.9, color=PALETTE["slate_dark"], va="top",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor=PALETTE["neutral_mid"], linewidth=0.5))

    ax = fig.add_subplot(grid[0, 2])
    fc.soften(ax, "y")
    corr = summary["modality_correlation"]["train"]
    pairs = (("文本–语音", "text_audio"), ("文本–视觉", "text_vision"), ("语音–视觉", "audio_vision"),
             ("文本–强度", "text_reg"), ("语音–强度", "audio_reg"), ("视觉–强度", "vision_reg"))
    y = np.arange(len(pairs))[::-1]
    for index, (label, key) in enumerate(pairs):
        value = corr[key]
        color = PALETTE["blue_main"] if value >= 0 else PALETTE["red_strong"]
        ax.hlines(y[index], 0, value, color=color, lw=2.0, zorder=2)
        ax.scatter([value], [y[index]], color=color, s=26, zorder=3)
        if value >= 0:
            text_x, align = value + 0.05, "left"
        else:
            text_x, align = value - 0.05, "right"
        ax.annotate(f"{value:+.3f}", xy=(text_x, y[index]), ha=align, va="center",
                    fontsize=6.0, color=color)
    ax.axvline(0, color=PALETTE["neutral_dark"], lw=0.9)
    ax.axvspan(-0.15, 0.15, color=PALETTE["neutral_light"], alpha=0.45, zorder=0)
    ax.set_yticks(y)
    ax.set_yticklabels([item[0] for item in pairs])
    ax.set_xlabel("样本级均值特征的皮尔逊相关系数")
    ax.set_xlim(-1.25, 1.05)
    ax.set_ylim(-0.85, 6.35)
    ax.set_title("(c) 模态间与模态–强度相关", fontsize=7.2, pad=6)
    ax.text(-0.15, 6.02, "弱相关带", ha="center", va="bottom", fontsize=5.8,
            color=PALETTE["neutral_dark"])

    return fc.save(fig, "fig02_modality_statistics", FIG)


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    reports = [fig01_data_overview(), fig02_modality_statistics()]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
