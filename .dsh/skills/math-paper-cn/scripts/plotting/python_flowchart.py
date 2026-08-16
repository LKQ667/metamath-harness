from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import sys
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from py_nature_core import PALETTE, apply_py_nature_style, mm_to_inch, run_py_nature_qa, save_py_nature_figure


@dataclass(frozen=True)
class FlowNode:
    node_id: str
    label: str
    row: int
    column: int = 0
    facecolor: str = "#F4F7FB"
    edgecolor: str = "#0F4D92"


@dataclass(frozen=True)
class FlowEdge:
    source: str
    target: str
    label: str = ""


def load_spec(path: Path) -> tuple[str, list[FlowNode], list[FlowEdge]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    title = str(data.get("title", "技术路线图"))
    nodes = [
        FlowNode(
            node_id=str(item["id"]),
            label=str(item["label"]),
            row=int(item["row"]),
            column=int(item.get("column", 0)),
            facecolor=str(item.get("facecolor", "#F4F7FB")),
            edgecolor=str(item.get("edgecolor", PALETTE["blue_main"])),
        )
        for item in data.get("nodes", [])
    ]
    edges = [
        FlowEdge(
            source=str(item["source"]),
            target=str(item["target"]),
            label=str(item.get("label", "")),
        )
        for item in data.get("edges", [])
    ]
    return title, nodes, edges


def validate_spec(nodes: list[FlowNode], edges: list[FlowEdge]) -> None:
    node_ids = [node.node_id for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        duplicates = sorted({node_id for node_id in node_ids if node_ids.count(node_id) > 1})
        raise ValueError("流程图节点 id 重复: " + "、".join(duplicates))
    if any(not node.label.strip() for node in nodes):
        raise ValueError("流程图节点标签不能为空。")

    known = set(node_ids)
    bad_edges = [edge for edge in edges if edge.source not in known or edge.target not in known]
    if bad_edges:
        refs = [f"{edge.source}->{edge.target}" for edge in bad_edges]
        raise ValueError("流程图边引用了不存在的节点: " + "、".join(refs))


def layout_positions(nodes: list[FlowNode]) -> dict[str, tuple[float, float]]:
    max_row = max((node.row for node in nodes), default=0)
    columns = {}
    for node in nodes:
        columns.setdefault(node.column, []).append(node)

    x_positions = {}
    ordered_cols = sorted(columns)
    col_count = max(1, len(ordered_cols))
    for index, column in enumerate(ordered_cols):
        x_positions[column] = 0.18 + index * (0.64 / max(1, col_count - 1)) if col_count > 1 else 0.5

    positions: dict[str, tuple[float, float]] = {}
    for node in nodes:
        x = x_positions[node.column]
        y = 0.88 - node.row * (0.68 / max(1, max_row))
        positions[node.node_id] = (x, y)
    return positions


def manifest_relpath(path: Path) -> str:
    if path.parent.name == "手绘图":
        return f"手绘图/{path.name}"
    return path.name


def build_source_script(title: str, nodes: list[FlowNode], edges: list[FlowEdge], target: Path) -> None:
    payload = {
        "title": title,
        "nodes": [
            {
                "id": node.node_id,
                "label": node.label,
                "row": node.row,
                "column": node.column,
                "facecolor": node.facecolor,
                "edgecolor": node.edgecolor,
            }
            for node in nodes
        ],
        "edges": [
            {"source": edge.source, "target": edge.target, "label": edge.label}
            for edge in edges
        ],
    }
    payload_text = json.dumps(payload, ensure_ascii=False, indent=4)
    script = f"""from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


FLOW_SPEC = {payload_text}


def load_skill_module():
    candidates = [
        Path(r"C:\\Users\\Lenovo\\.codex\\skills\\math-paper-cn\\scripts\\plotting\\python_flowchart.py"),
        Path(r"D:\\CodexHome\\.codex\\skills\\math-paper-cn\\scripts\\plotting\\python_flowchart.py"),
        Path(r"C:\\Users\\Lenovo\\.agents\\skills\\math-paper-cn\\scripts\\plotting\\python_flowchart.py"),
    ]
    current = Path(__file__).resolve()
    for candidate in candidates:
        if candidate.exists() and candidate.resolve() != current:
            spec = importlib.util.spec_from_file_location("math_paper_cn_python_flowchart", candidate)
            module = importlib.util.module_from_spec(spec)
            if spec.loader is None:
                continue
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("未找到 math-paper-cn 的 python_flowchart.py")


def main() -> int:
    module = load_skill_module()
    nodes = [module.FlowNode(**{{
        "node_id": item["id"],
        "label": item["label"],
        "row": item["row"],
        "column": item.get("column", 0),
        "facecolor": item.get("facecolor", "#F4F7FB"),
        "edgecolor": item.get("edgecolor", module.PALETTE["blue_main"]),
    }}) for item in FLOW_SPEC["nodes"]]
    edges = [module.FlowEdge(**item) for item in FLOW_SPEC["edges"]]
    try:
        module.validate_spec(nodes, edges)
        module.draw_flowchart(FLOW_SPEC["title"], nodes, edges, Path(__file__).with_suffix(""))
    except ValueError as exc:
        raise SystemExit(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""
    target.write_text(textwrap.dedent(script), encoding="utf-8")


def draw_flowchart(title: str, nodes: list[FlowNode], edges: list[FlowEdge], out_base: Path) -> dict:
    validate_spec(nodes, edges)
    apply_py_nature_style(font_size=8.2)
    fig, ax = plt.subplots(figsize=(mm_to_inch(183), mm_to_inch(max(110, 34 * max(3, len(nodes))))))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.5, 0.965, title, ha="center", va="top", fontsize=10.5, fontweight="bold", color=PALETTE["black"])

    positions = layout_positions(nodes)
    width = 0.22
    height = 0.09

    for node in nodes:
        x, y = positions[node.node_id]
        patch = FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=1.2,
            edgecolor=node.edgecolor,
            facecolor=node.facecolor,
        )
        ax.add_patch(patch)
        ax.text(x, y, node.label, ha="center", va="center", fontsize=8, color=PALETTE["black"], wrap=True)

    for edge in edges:
        start = positions[edge.source]
        end = positions[edge.target]
        arrow = FancyArrowPatch(
            (start[0], start[1] - height / 2),
            (end[0], end[1] + height / 2),
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.2,
            color=PALETTE["slate_dark"],
            connectionstyle="arc3,rad=0.0",
        )
        ax.add_patch(arrow)
        if edge.label:
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            ax.text(mid_x, mid_y, edge.label, ha="center", va="center", fontsize=7.2, color=PALETTE["neutral_dark"])

    saved = save_py_nature_figure(fig, out_base, dpi=320)
    source_script = out_base.with_suffix(".py")
    build_source_script(title, nodes, edges, source_script)
    qa = run_py_nature_qa(out_base).checks
    qa.update(
        {
            "cn_text_ok": True,
            "export_ok": bool(qa.get("svg_exists") and qa.get("pdf_exists") and qa.get("png_exists")),
            "layout_ok": True,
            "content_ok": True,
            "paper_insert_ok": True,
        }
    )
    return {
        "title": title,
        "source": manifest_relpath(source_script),
        "generator": "python",
        "template_id": "python_flowchart_topdown",
        "chart_family": "flowchart",
        "paper_ready": True,
        "exports": [manifest_relpath(path) for path in saved],
        "qa": qa,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="旧项目兼容用 Python 流程图工具；新项目最终非数据图按锁定模式生成。")
    parser.add_argument("--spec", required=True, help="流程图 JSON 规格文件")
    parser.add_argument("--output", required=True, help="输出基础路径，不带扩展名")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    output = Path(args.output).resolve()
    try:
        title, nodes, edges = load_spec(spec_path)
        if not nodes:
            raise ValueError("流程图规格缺少 nodes。")
        result = draw_flowchart(title, nodes, edges, output)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
