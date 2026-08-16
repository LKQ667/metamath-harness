#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check manifest contract for Python-generated paper figures."""

from __future__ import annotations

from pathlib import Path

from common import load_manifest_items, project_arg, write_report

REQUIRED_EXPORT_SUFFIXES = {".svg", ".pdf", ".png"}


def is_python_item(item: dict) -> bool:
    source = str(item.get("source", "")).lower()
    return item.get("generator") == "python" or source.endswith(".py")


def main() -> int:
    parser = project_arg("检查 Python 绘图最小契约。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)

    for item in items:
        if not is_python_item(item):
            continue
        source = str(item.get("source", ""))
        if item.get("generator") != "python":
            errors.append(f"Python 图缺少 generator=python: {source or item}")
        if not item.get("template_id"):
            errors.append(f"Python 图缺少 template_id: {source or item}")
        if not item.get("chart_family"):
            errors.append(f"Python 图缺少 chart_family: {source or item}")
        if item.get("paper_ready") is not True:
            errors.append(f"Python 图未标记 paper_ready=true: {source or item}")

        source_path = project / source if source else None
        if not source:
            errors.append(f"Python 图缺少 source: {item}")
        elif source_path is not None and not source_path.exists():
            errors.append(f"Python 图源不存在: {source}")

        raw_exports = item.get("exports") or []
        exports = list(raw_exports.values()) if isinstance(raw_exports, dict) else raw_exports
        if not exports:
            errors.append(f"Python 图缺少导出文件: {source or item}")
            continue
        suffixes = {Path(exp).suffix.lower() for exp in exports}
        missing = sorted(REQUIRED_EXPORT_SUFFIXES - suffixes)
        if missing:
            errors.append(f"Python 图导出格式不完整 {source or item}: 缺少 {'、'.join(missing)}")
        for rel in exports:
            if not (project / rel).exists():
                errors.append(f"Python 图导出文件不存在: {rel}")

    return write_report(not errors, "check_python_figure_contract", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
