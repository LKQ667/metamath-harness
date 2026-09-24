"""数据预处理阶段的论文用图：100 个用例的结构画像。

产出 `fig_dataset_profile`（四语义面板）与 `fig_dag_layers`（单面板热图），
分别支撑“用例规模与并行度分布”和“流水线工作量随分层的分布”两段论述。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from figures_common import (  # noqa: E402
    PALETTE,
    PROFILE,
    add_panel_label,
    apply_py_nature_style,
    compose_multi_panel,
    finalize,
    load_profile,
    mm_to_inch,
)
from graph_utils import build_op_dag, contract_copy, load_graph, op_cost, topological  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402

OUT = ROOT / "数据预处理" / "figures"
QA = ROOT / "检查结果" / "figure_qa"
SUITE_CANDIDATES = [ROOT / "赛题" / "_附件解压", ROOT.parent / "_hw_suite"]


def suite_data():
    for candidate in SUITE_CANDIDATES:
        if (candidate / "data" / "config.txt").is_file():
            return candidate / "data"
    raise FileNotFoundError("未找到赛题附件解压目录")


def figure_profile(rows):
    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig, axes = compose_multi_panel(
        "hero_top_support_bottom",
        panel_specs=["hero", "s1", "s2", "s3"],
        width_mm=183,
        height_mm=118,
    )
    ops = np.array([float(r["ops_core"]) for r in rows])
    width = np.array([float(r["parallel_width"]) for r in rows])
    ddr = np.array([float(r["ddr_bytes"]) for r in rows]) / 1024.0
    m = np.array([float(r["cycles_m"]) for r in rows])
    v = np.array([float(r["cycles_v"]) for r in rows])
    total = m + v
    share_m = np.divide(m, total, out=np.zeros_like(m), where=total > 0) * 100.0
    critical = np.array([float(r["critical_path"]) for r in rows])
    cycles = np.array([float(r["cycles_total"]) for r in rows])

    ax = axes["hero"]
    ax.scatter(ops, width, s=14, color=PALETTE["blue_main"], alpha=0.8, linewidths=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.axhline(2.0, color=PALETTE["red_strong"], linewidth=1.0, linestyle="--")
    ax.text(ops.min() * 1.15, 2.2, "并行宽度 2 倍线", fontsize=6.5, color=PALETTE["red_strong"])
    ax.set_xlabel("核内操作数（个）")
    ax.set_ylabel("并行宽度（倍）")
    add_panel_label(ax, "a")

    ax = axes["support_1"]
    ax.hist(ddr, bins=18, color=PALETTE["blue_secondary"], alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("DDR 张量总量（KB）")
    ax.set_ylabel("用例数（个）")
    add_panel_label(ax, "b")

    ax = axes["support_2"]
    ax.hist(share_m, bins=18, color=PALETTE["teal_main"], alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("矩阵流水线工作量占比（%）")
    ax.set_ylabel("用例数（个）")
    add_panel_label(ax, "c")

    ax = axes["support_3"]
    ax.scatter(cycles, critical, s=14, color=PALETTE["violet_main"], alpha=0.8, linewidths=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("总工作量（周期）")
    ax.set_ylabel("关键路径（周期）")
    add_panel_label(ax, "d")

    axes["legend"].set_axis_off()
    axes["legend"].text(
        0.02,
        0.95,
        "结构画像要点",
        fontsize=7.5,
        fontweight="bold",
        va="top",
        color=PALETTE["black"],
    )
    axes["legend"].text(
        0.02,
        0.78,
        "核内操作 552～35705 个\n"
        "并行宽度中位数 43 倍\n"
        "矩阵流水线占主导\n"
        "关键路径远短于总工作量",
        fontsize=6.8,
        va="top",
        color=PALETTE["neutral_dark"],
        linespacing=1.7,
    )
    return finalize(fig, OUT / "fig_dataset_profile", QA)


def figure_layers(rows):
    """按最长路径分层，展示各层矩阵与向量工作量的相对占比。"""
    data_dir = suite_data()
    heavy = sorted(rows, key=lambda r: -float(r["cycles_total"]))[:12]
    matrix = []
    labels = []
    for row in heavy:
        graph = load_graph(data_dir / f"{row['case']}.json")
        op_by_id, preds, succs, eligible = build_op_dag(graph)
        cpreds, csuccs = contract_copy(preds, succs, eligible)
        order = topological(eligible, cpreds, csuccs)
        level = {}
        for node in order:
            best = 0
            for pre in cpreds[node]:
                if pre in level and level[pre] + 1 > best:
                    best = level[pre] + 1
            level[node] = best
        max_level = max(level.values()) if level else 0
        bins = 12
        buckets = [[0.0, 0.0] for _ in range(bins)]
        for node in eligible:
            index = min(bins - 1, int(level[node] * bins / (max_level + 1)))
            cost = float(op_cost(op_by_id[node]))
            if op_by_id[node]["pipe"] == "PIPE_M":
                buckets[index][0] += cost
            else:
                buckets[index][1] += cost
        total = sum(a + b for a, b in buckets) or 1.0
        matrix.append([(a + b) / total * 100.0 for a, b in buckets])
        labels.append(row["case"].replace("case_", ""))

    apply_py_nature_style(font_size=7.0, profile=PROFILE)
    fig = plt.figure(figsize=(mm_to_inch(183), mm_to_inch(88)))
    ax = fig.add_subplot(111)
    im = ax.imshow(np.array(matrix), cmap="Blues", aspect="auto", vmin=0.0, vmax=60.0)
    ax.set_xticks(range(12))
    ax.set_xticklabels([f"{i + 1}" for i in range(12)])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlabel("归一化最长路径分层（由早到晚，等分为 12 段）")
    ax.set_ylabel("总工作量最大的 12 个用例")
    colorbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    colorbar.set_label("该层工作量占全图比例（%）", fontsize=6.5)
    return finalize(fig, OUT / "fig_dag_layers", QA)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_profile()
    saved_a, _ = figure_profile(rows)
    saved_b, _ = figure_layers(rows)
    print(json_dumps({"fig_dataset_profile": [str(p) for p in saved_a], "fig_dag_layers": [str(p) for p in saved_b]}))


def json_dumps(value):
    import json

    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    main()
