#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check Python figure QA metadata in manifest."""

from __future__ import annotations

from pathlib import Path

from common import load_manifest_items, project_arg, write_report


def is_python_item(item: dict) -> bool:
    source = str(item.get("source", "")).lower()
    return item.get("generator") == "python" or source.endswith(".py")


def main() -> int:
    parser = project_arg("检查 Python 绘图 QA 状态。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)

    for item in items:
        if not is_python_item(item):
            continue
        source = str(item.get("source", ""))
        qa = item.get("qa")
        if not isinstance(qa, dict):
            errors.append(f"Python 图缺少 qa 对象: {source or item}")
            continue
        if qa.get("cn_text_ok") is not True:
            errors.append(f"Python 图未通过中文字体/乱码检查: {source or item}")
        if qa.get("export_ok") is not True:
            errors.append(f"Python 图未通过导出格式检查: {source or item}")
        if qa.get("editable_text_ok") is not True:
            errors.append(f"Python 图未通过可编辑文本检查: {source or item}")

    return write_report(not errors, "check_python_figure_quality", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
