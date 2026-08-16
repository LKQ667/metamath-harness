#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查技术路线图记录与锁定模式一致并通过版式/内容门禁。"""

from __future__ import annotations

from pathlib import Path

from common import load_manifest_items, project_arg, write_report


ROADMAP_TOKENS = ("技术路线", "路线图", "roadmap", "问题分析流程")


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


def is_roadmap_item(item: dict) -> bool:
    text = item_text(item)
    return any(token.lower() in text for token in ROADMAP_TOKENS)


def main() -> int:
    parser = project_arg("检查技术路线图 manifest 是否记录锁定模式来源和版式质量。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []

    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    roadmap_items = [item for item in items if is_roadmap_item(item)]
    if not roadmap_items:
        errors.append("manifest 中缺少技术路线图条目，无法核验箭头和布局质量。")
        return write_report(False, "check_roadmap_quality_notes", errors, args.output)

    for item in roadmap_items:
        source = str(item.get("source", "")).lower()
        qa = item.get("qa")
        if str(item.get("generator", "")).lower() not in {"drawio", "imagegen", "image gen", "openai-imagegen"}:
            errors.append("技术路线图 generator 必须与 Draw.io/AI 锁定模式一致。")
        if "flowchart" not in str(item.get("chart_family", "")).lower():
            errors.append("技术路线图 manifest 必须标注 `chart_family=flowchart` 或等价值。")
        if not isinstance(qa, dict):
            errors.append("技术路线图 manifest 必须包含 qa 对象。")
            continue
        if qa.get("cn_text_ok") is not True:
            errors.append("技术路线图未通过中文乱码检查。")
        if qa.get("layout_ok") is not True:
            errors.append("技术路线图未通过布局检查，如标签错位、重叠或裁切。")
        if qa.get("content_ok", qa.get("content_consistency_ok")) is not True:
            errors.append("技术路线图未通过内容检查，主线或节点信息不完整。")
        if "paper_insert_ok" in qa and qa.get("paper_insert_ok") is not True:
            errors.append("技术路线图记录了论文回填状态，但未标记通过。")

    return write_report(not errors, "check_roadmap_quality_notes", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
