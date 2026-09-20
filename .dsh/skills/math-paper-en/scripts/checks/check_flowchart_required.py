#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查所选非数据绘图模式至少包含一张可入文流程类图。"""

from __future__ import annotations

from pathlib import Path

from common import load_manifest_items, project_arg, write_report


EXPORT_SUFFIXES = {".png", ".svg", ".pdf"}
FLOW_TOKENS = ("技术路线", "路线图", "roadmap", "问题分析流程", "流程图", "框架图")


def item_text(item: dict) -> str:
    parts: list[str] = []
    for value in item.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    return "\n".join(parts).replace("\\", "/").lower()


def is_flowchart_item(item: dict) -> bool:
    chart_family = str(item.get("chart_family", "")).lower()
    text = item_text(item)
    if "flowchart" in chart_family:
        return True
    return any(token.lower() in text for token in FLOW_TOKENS)


def has_flowchart_manifest_entry(items: list[dict]) -> bool:
    return any(is_flowchart_item(item) for item in items)


def main() -> int:
    parser = project_arg("检查 Step4 前是否已按锁定模式生成流程类图、导出图和 manifest 记录。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []

    hand_dir = project / "手绘图"
    export_files = sorted([p for p in hand_dir.glob("*") if p.is_file() and p.suffix.lower() in EXPORT_SUFFIXES]) if hand_dir.exists() else []

    if not hand_dir.exists():
        errors.append("缺少 `手绘图/` 目录，无法接收流程类图产物。")
    if not export_files:
        errors.append("`手绘图/` 中缺少 PNG/SVG/PDF 导出图，不能直接入文。")

    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    flow_items = [item for item in items if is_flowchart_item(item)]
    if items and not flow_items:
        errors.append("`figures/manifest.json` 缺少流程图或技术路线图条目。")
    for item in flow_items:
        source = project / str(item.get("source", ""))
        if not source.is_file():
            errors.append(f"流程类图源不存在: {item.get('source', '')}")

    return write_report(not errors, "check_flowchart_required", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
