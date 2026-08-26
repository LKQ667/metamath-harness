#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""由 JSON 图稿生成避免重叠和错连的中文 draw.io 标准流程图。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

PALETTE = {
    "data": ("#EAF3F8", "#4F7F9F"), "model": ("#EEF6EA", "#5E8C61"),
    "solve": ("#FFF4E6", "#B7791F"), "check": ("#F3EEF8", "#7A5C99"),
    "output": ("#F8EEEE", "#A65F5F"), "neutral": ("#F7F7F7", "#667085"),
}
FONT = "html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;"


def style(role: str, shape: str) -> str:
    fill, stroke = PALETTE.get(role, PALETTE["neutral"])
    shape_style = "rhombus;" if shape == "decision" else "shape=cylinder3;" if shape == "data" else "shape=mxgraph.flowchart.document;" if shape == "document" else "rounded=1;arcSize=12;"
    return f"{shape_style}{FONT}fillColor={fill};strokeColor={stroke};strokeWidth=1.5;"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="JSON：title、nodes、edges；nodes 含 id/label，可选 role/shape")
    p.add_argument("--output", required=True, help=".drawio 输出路径")
    p.add_argument("--direction", choices=("lr", "tb"), default="lr")
    args = p.parse_args()
    spec = json.loads(Path(args.input).read_text(encoding="utf-8"))
    nodes, edges = spec.get("nodes", []), spec.get("edges", [])
    ids = [str(n.get("id", "")) for n in nodes]
    if not nodes or len(ids) != len(set(ids)) or any(not x for x in ids):
        raise SystemExit("nodes 必须非空，且每个 id 唯一")
    known = set(ids)
    if any(e.get("source") not in known or e.get("target") not in known for e in edges):
        raise SystemExit("edges 的 source/target 必须都在 nodes 中")
    mxfile = Element("mxfile", {"host": "app.diagrams.net", "agent": "math-paper-cn-drawio"})
    diagram = SubElement(mxfile, "diagram", {"id": "modeling-route", "name": str(spec.get("title", "技术路线图"))})
    model = SubElement(diagram, "mxGraphModel", {"page": "1", "pageWidth": "1600", "pageHeight": "900", "grid": "1", "gridSize": "10", "defaultFontFamily": "Microsoft YaHei"})
    root = SubElement(model, "root")
    SubElement(root, "mxCell", {"id": "0"}); SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    positions: dict[str, tuple[int, int]] = {}
    for index, node in enumerate(nodes):
        x, y = ((50 + index * 220, 180) if args.direction == "lr" else (420, 50 + index * 130))
        ident = str(node["id"])
        label = str(node.get("label", ident))
        positions[ident] = (x, y)
        cell = SubElement(root, "mxCell", {"id": ident, "value": label, "style": style(str(node.get("role", "neutral")), str(node.get("shape", "process"))), "vertex": "1", "parent": "1"})
        SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": "150", "height": "64", "as": "geometry"})
    for index, edge in enumerate(edges, 1):
        src, dst = str(edge["source"]), str(edge["target"])
        horizontal = args.direction == "lr"
        ports = "exitX=1;exitY=0.5;entryX=0;entryY=0.5;" if horizontal else "exitX=0.5;exitY=1;entryX=0.5;entryY=0;"
        value = str(edge.get("label", ""))
        cell = SubElement(root, "mxCell", {"id": f"e-{index:03d}", "value": value, "style": f"edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;endArrow=classic;endFill=1;html=1;fontFamily=Microsoft YaHei;fontSize=12;strokeColor=#52606D;strokeWidth=1.5;{ports}", "edge": "1", "parent": "1", "source": src, "target": dst})
        SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(mxfile, encoding="utf-8"))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
