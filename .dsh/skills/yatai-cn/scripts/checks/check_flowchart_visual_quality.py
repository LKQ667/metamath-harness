#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查所选模式的流程类图视觉质量 QA 字段。"""

from __future__ import annotations

from pathlib import Path

from common import load_manifest_items, project_arg, write_report


FLOWCHART_TOKENS = ("技术路线", "路线图", "流程", "flowchart", "roadmap", "问题分析")
REQUIRED_QA = (
    "color_palette_ok",
    "visual_density_ok",
    "edge_routing_ok",
    "node_overlap_ok",
    "text_fit_ok",
    "style_not_stiff_ok",
)


def flatten_values(value) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            values.append(str(key))
            values.extend(flatten_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(flatten_values(child))
    elif isinstance(value, str):
        values.append(value)
    elif value is True:
        values.append("true")
    return values


def item_text(item: dict) -> str:
    return "\n".join(flatten_values(item)).lower()


def is_flowchart_item(item: dict) -> bool:
    text = item_text(item)
    family = str(item.get("chart_family", "")).lower()
    return "flowchart" in family or any(token.lower() in text for token in FLOWCHART_TOKENS)


def main() -> int:
    parser = project_arg("检查锁定模式流程类图视觉质量 QA 字段")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []

    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    flowchart_items = [item for item in items if is_flowchart_item(item)]
    if not flowchart_items:
        errors.append("manifest 中缺少流程图或技术路线图条目。")
        return write_report(False, "check_flowchart_visual_quality", errors, args.output)

    for item in flowchart_items:
        source = str(item.get("source", "")).replace("\\", "/")
        qa = item.get("qa")
        if str(item.get("generator", "")).lower() not in {"drawio", "imagegen", "image gen", "openai-imagegen"}:
            errors.append(f"流程图 generator 与双绘图模式不兼容: {source or '未知来源'}")
        if "flowchart" not in str(item.get("chart_family", "")).lower():
            errors.append(f"流程图必须标注 chart_family=flowchart: {source or '未知来源'}")
        if not source.startswith("手绘图/"):
            errors.append(f"流程图源必须位于 手绘图/: {source or '未知来源'}")
        if not isinstance(qa, dict):
            errors.append(f"流程图 manifest 缺少 qa 对象: {source or '未知来源'}")
            continue
        for key in REQUIRED_QA:
            if qa.get(key) is not True:
                errors.append(f"流程图视觉质量字段未通过 {key}: {source or '未知来源'}")

    return write_report(not errors, "check_flowchart_visual_quality", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
