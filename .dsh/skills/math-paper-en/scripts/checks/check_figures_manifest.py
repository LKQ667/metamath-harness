#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import load_manifest_items, project_arg, write_report


FLOW_TOKENS = ("技术路线", "路线图", "roadmap", "问题分析流程", "流程图", "框架图")


def is_flowchart_item(item: dict) -> bool:
    chart_family = str(item.get("chart_family", "")).lower()
    values: list[str] = []
    for value in item.values():
        if isinstance(value, str):
            values.append(value)
    text = "\n".join(values).lower()
    return "flowchart" in chart_family or any(token.lower() in text for token in FLOW_TOKENS)


def main() -> int:
    parser = project_arg("检查 figures/manifest.json 和图源文件")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    for item in items:
        source = item.get("source")
        raw_exports = item.get("exports") or []
        exports = list(raw_exports.values()) if isinstance(raw_exports, dict) else raw_exports
        if not source:
            errors.append(f"manifest 条目缺少 source: {item}")
            continue
        source_path = project / source
        if not source_path.exists():
            errors.append(f"图源不存在: {source}")
        if is_flowchart_item(item):
            generator = str(item.get("generator", "")).lower()
            expected = {"python": ".py", "drawio": ".drawio"}.get(generator)
            if expected and source_path.suffix.lower() != expected:
                errors.append(f"流程图源与 generator 不匹配: {source}")
            if generator in {"imagegen", "image gen", "openai-imagegen"} and source_path.suffix.lower() != ".png":
                errors.append(f"AI 流程图必须是可严格校验的 PNG: {source}")
            if "手绘图" not in source_path.parts:
                errors.append(f"流程图源应位于手绘图目录: {source}")
        if not exports:
            errors.append(f"图源缺少导出文件: {source}")
        for rel in exports:
            if not (project / rel).exists():
                errors.append(f"导出图不存在: {rel}")
        if item.get("paper_ready") is not True:
            errors.append(f"图未标记 paper_ready=true: {source}")
    return write_report(not errors, "check_figures_manifest", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
