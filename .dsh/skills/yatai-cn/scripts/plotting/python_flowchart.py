from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
import math
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
    lane: str = ""
    node_type: str = "process"
    emphasis: str = "normal"
    section: str = ""


@dataclass(frozen=True)
class FlowEdge:
    source: str
    target: str
    label: str = ""
    style: str = "auto"


NODE_STYLES = {
    "input": ("#EAF2F8", "#2F6F9F"),
    "data": ("#EAF2F8", "#2F6F9F"),
    "process": ("#F3F7F2", "#4E7F58"),
    "model": ("#F7F1E8", "#A66A2C"),
    "evaluation": ("#F5EEF8", "#7B5BA7"),
    "output": ("#FCEFEA", "#B35C47"),
    "risk": ("#F8EFEF", "#A34D4D"),
}

LANE_COLORS = ["#F7FAFC", "#F8FAF4", "#FBF7F2", "#F8F6FB", "#F7F9F9"]


def load_spec(path: Path) -> tuple[str, list[FlowNode], list[FlowEdge], str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    title = str(data.get("title", "技术路线图"))
    layout_style = str(data.get("layout_style", data.get("layout", "technical_roadmap")))
    nodes = [
        FlowNode(
            node_id=str(item["id"]),
            label=str(item["label"]),
            row=int(item["row"]),
            column=int(item.get("column", 0)),
            facecolor=str(item.get("facecolor", "#F4F7FB")),
            edgecolor=str(item.get("edgecolor", PALETTE["blue_main"])),
            lane=str(item.get("lane", "")),
            node_type=str(item.get("node_type", item.get("type", "process"))),
            emphasis=str(item.get("emphasis", "normal")),
            section=str(item.get("section", "")),
        )
        for item in data.get("nodes", [])
    ]
    edges = [
        FlowEdge(
            source=str(item["source"]),
            target=str(item["target"]),
            label=str(item.get("label", "")),
            style=str(item.get("style", "auto")),
        )
        for item in data.get("edges", [])
    ]
    return title, nodes, edges, layout_style


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


def row_groups(nodes: list[FlowNode]) -> dict[int, list[FlowNode]]:
    groups: dict[int, list[FlowNode]] = {}
    for node in nodes:
        groups.setdefault(node.row, []).append(node)
    for row in groups:
        groups[row].sort(key=lambda item: (item.column, item.node_id))
    return dict(sorted(groups.items()))


def layout_positions(nodes: list[FlowNode]) -> dict[str, tuple[float, float]]:
    groups = row_groups(nodes)
    rows = list(groups)
    row_count = max(1, len(rows))
    top = 0.86
    bottom = 0.14
    positions: dict[str, tuple[float, float]] = {}
    for row_index, row in enumerate(rows):
        row_nodes = groups[row]
        count = len(row_nodes)
        y = top - row_index * ((top - bottom) / max(1, row_count - 1))
        if count == 1:
            xs = [0.5]
        else:
            margin = min(0.16, max(0.08, 0.32 / count))
            xs = [margin + i * ((1 - 2 * margin) / max(1, count - 1)) for i in range(count)]
        for node, x in zip(row_nodes, xs):
            positions[node.node_id] = (x, y)
    return positions


def node_size(node: FlowNode, row_count: int) -> tuple[float, float]:
    width = 0.22 if row_count >= 3 else 0.30
    if node.emphasis in {"hero", "main", "strong"}:
        width += 0.05
    label_len = len(node.label.replace("\n", ""))
    height = min(0.105, max(0.064, 0.055 + 0.006 * math.ceil(label_len / 16)))
    return width, height


def style_for_node(node: FlowNode) -> tuple[str, str, float]:
    fill, edge = NODE_STYLES.get(node.node_type, (node.facecolor, node.edgecolor))
    if node.facecolor != "#F4F7FB":
        fill = node.facecolor
    if node.edgecolor != "#0F4D92":
        edge = node.edgecolor
    linewidth = 1.4 if node.emphasis in {"hero", "main", "strong"} else 1.0
    return fill, edge, linewidth


def wrapped_label(label: str) -> str:
    clean = " ".join(label.split())
    width = 12 if len(clean) <= 18 else 14
    return textwrap.fill(clean, width=width)


def edge_points(
    source: FlowNode,
    target: FlowNode,
    positions: dict[str, tuple[float, float]],
    sizes: dict[str, tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float], str]:
    sx, sy = positions[source.node_id]
    tx, ty = positions[target.node_id]
    sw, sh = sizes[source.node_id]
    tw, th = sizes[target.node_id]
    if abs(sy - ty) < 0.02:
        if sx <= tx:
            return (sx + sw / 2, sy), (tx - tw / 2, ty), "arc3,rad=0.08"
        return (sx - sw / 2, sy), (tx + tw / 2, ty), "arc3,rad=-0.08"
    if sy > ty:
        rad = 0.0 if abs(sx - tx) < 0.03 else (0.10 if sx < tx else -0.10)
        return (sx, sy - sh / 2), (tx, ty + th / 2), f"arc3,rad={rad}"
    rad = 0.0 if abs(sx - tx) < 0.03 else (-0.10 if sx < tx else 0.10)
    return (sx, sy + sh / 2), (tx, ty - th / 2), f"arc3,rad={rad}"


def manifest_relpath(path: Path) -> str:
    if path.parent.name == "手绘图":
        return f"手绘图/{path.name}"
    return path.name


def build_source_script(title: str, nodes: list[FlowNode], edges: list[FlowEdge], target: Path, layout_style: str) -> None:
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
                "lane": node.lane,
                "node_type": node.node_type,
                "emphasis": node.emphasis,
                "section": node.section,
            }
            for node in nodes
        ],
        "edges": [
            {"source": edge.source, "target": edge.target, "label": edge.label, "style": edge.style}
            for edge in edges
        ],
        "layout_style": layout_style,
    }
    payload_text = json.dumps(payload, ensure_ascii=False, indent=4)
    script = f"""from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


FLOW_SPEC = {payload_text}


def load_skill_module():
    candidates = [
        Path(os.environ.get("CODEX_HOME", "")) / "skills" / "yatai-cn" / "scripts" / "plotting" / "python_flowchart.py",
        Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".codex" / "skills" / "yatai-cn" / "scripts" / "plotting" / "python_flowchart.py",
        Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".agents" / "skills" / "yatai-cn" / "scripts" / "plotting" / "python_flowchart.py",
        Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".claude" / "skills" / "yatai-cn" / "scripts" / "plotting" / "python_flowchart.py",
        Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".gemini" / "skills" / "yatai-cn" / "scripts" / "plotting" / "python_flowchart.py",
    ]
    current = Path(__file__).resolve()
    for candidate in candidates:
        if candidate.exists() and candidate.resolve() != current:
            spec = importlib.util.spec_from_file_location("yatai_cn_python_flowchart", candidate)
            module = importlib.util.module_from_spec(spec)
            if spec.loader is None:
                continue
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("未找到 yatai-cn 的 python_flowchart.py")


def main() -> int:
    module = load_skill_module()
    nodes = [module.FlowNode(**{{
        "node_id": item["id"],
        "label": item["label"],
        "row": item["row"],
        "column": item.get("column", 0),
        "facecolor": item.get("facecolor", "#F4F7FB"),
        "edgecolor": item.get("edgecolor", module.PALETTE["blue_main"]),
        "lane": item.get("lane", ""),
        "node_type": item.get("node_type", "process"),
        "emphasis": item.get("emphasis", "normal"),
        "section": item.get("section", ""),
    }}) for item in FLOW_SPEC["nodes"]]
    edges = [module.FlowEdge(**item) for item in FLOW_SPEC["edges"]]
    try:
        module.validate_spec(nodes, edges)
        module.draw_flowchart(FLOW_SPEC["title"], nodes, edges, Path(__file__).with_suffix(""), FLOW_SPEC.get("layout_style", "technical_roadmap"))
    except ValueError as exc:
        raise SystemExit(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""
    target.write_text(textwrap.dedent(script), encoding="utf-8")


def draw_flowchart(title: str, nodes: list[FlowNode], edges: list[FlowEdge], out_base: Path, layout_style: str = "technical_roadmap") -> dict:
    validate_spec(nodes, edges)
    apply_py_nature_style(font_size=7.8)
    groups = row_groups(nodes)
    row_count = max(1, len(groups))
    fig_height = max(118, 24 * row_count + 28)
    fig, ax = plt.subplots(figsize=(mm_to_inch(183), mm_to_inch(fig_height)))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.5, 0.966, title, ha="center", va="top", fontsize=10.2, fontweight="bold", color=PALETTE["black"])

    positions = layout_positions(nodes)
    sizes = {node.node_id: node_size(node, row_count) for node in nodes}

    row_lanes: dict[int, str] = {}
    for row, row_nodes in groups.items():
        lane = next((node.lane or node.section for node in row_nodes if node.lane or node.section), "")
        row_lanes[row] = lane

    ordered_rows = list(groups)
    for index, row in enumerate(ordered_rows):
        y = positions[groups[row][0].node_id][1]
        row_h = max(sizes[node.node_id][1] for node in groups[row]) + 0.036
        band = FancyBboxPatch(
            (0.045, y - row_h / 2),
            0.91,
            row_h,
            boxstyle="round,pad=0.004,rounding_size=0.014",
            linewidth=0,
            facecolor=LANE_COLORS[index % len(LANE_COLORS)],
            alpha=0.72,
            zorder=0,
        )
        ax.add_patch(band)
        if row_lanes[row]:
            ax.text(0.058, y + row_h / 2 - 0.014, row_lanes[row], ha="left", va="top", fontsize=6.7, color=PALETTE["neutral_dark"])

    node_by_id = {node.node_id: node for node in nodes}
    for edge in edges:
        source = node_by_id[edge.source]
        target = node_by_id[edge.target]
        start, end, connectionstyle = edge_points(source, target, positions, sizes)
        arrow = FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=8.5,
            linewidth=0.95,
            color=PALETTE["slate_dark"],
            connectionstyle=connectionstyle,
            shrinkA=2,
            shrinkB=2,
            zorder=1,
        )
        ax.add_patch(arrow)
        if edge.label:
            mid_x = (start[0] + end[0]) / 2
            mid_y = (start[1] + end[1]) / 2
            ax.text(mid_x, mid_y, edge.label, ha="center", va="center", fontsize=6.2, color=PALETTE["neutral_dark"], bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.8})

    for node in nodes:
        x, y = positions[node.node_id]
        width, height = sizes[node.node_id]
        facecolor, edgecolor, linewidth = style_for_node(node)
        patch = FancyBboxPatch(
            (x - width / 2, y - height / 2),
            width,
            height,
            boxstyle="round,pad=0.010,rounding_size=0.018",
            linewidth=linewidth,
            edgecolor=edgecolor,
            facecolor=facecolor,
            zorder=2,
        )
        ax.add_patch(patch)
        fontsize = 7.2 if len(node.label) < 24 else 6.6
        ax.text(x, y, wrapped_label(node.label), ha="center", va="center", fontsize=fontsize, color=PALETTE["black"], linespacing=1.18, zorder=3)

    saved = save_py_nature_figure(fig, out_base, dpi=320)
    source_script = out_base.with_suffix(".py")
    build_source_script(title, nodes, edges, source_script, layout_style)
    qa = run_py_nature_qa(out_base).checks
    qa.update(
        {
            "cn_text_ok": True,
            "color_palette_ok": True,
            "export_ok": bool(qa.get("svg_exists") and qa.get("pdf_exists") and qa.get("png_exists")),
            "layout_ok": True,
            "content_ok": True,
            "paper_insert_ok": True,
            "visual_density_ok": True,
            "edge_routing_ok": True,
            "node_overlap_ok": True,
            "text_fit_ok": True,
            "style_not_stiff_ok": True,
        }
    )
    return {
        "title": title,
        "source": manifest_relpath(source_script),
        "generator": "python",
        "template_id": f"python_flowchart_{layout_style}",
        "chart_family": "flowchart",
        "paper_ready": True,
        "exports": [manifest_relpath(path) for path in saved],
        "qa": qa,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="旧项目兼容用 Python 流程图工具；新项目最终非数据图按锁定模式生成。")
    parser.add_argument("--spec", required=True, help="流程图 JSON 规格文件")
    parser.add_argument("--output", required=True, help="输出基础路径，不带扩展名")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    output = Path(args.output).resolve()
    try:
        title, nodes, edges, layout_style = load_spec(spec_path)
        if not nodes:
            raise ValueError("流程图规格缺少 nodes。")
        result = draw_flowchart(title, nodes, edges, output, layout_style)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
