#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check ordinary 1D/2D bar charts are explicitly justified."""

from __future__ import annotations

import re
from pathlib import Path

from common import load_manifest_items, project_arg, write_report


BAR_RE = re.compile(r"(?<![a-z0-9])(bar|bar_chart|column|1d_bar|2d_bar|vertical_bar|horizontal_bar)(?![a-z0-9])")
BAR_CN_RE = re.compile(r"(柱状图|条形图)")
EXCLUDE_RE = re.compile(r"(tornado|lollipop|histogram|heatmap|sobol|forest|interval)")


def is_python_item(item: dict) -> bool:
    source = str(item.get("source", "")).lower()
    return item.get("generator") == "python" or source.endswith(".py")


def ordinary_bar_item(item: dict) -> bool:
    fields = [
        str(item.get("chart_family", "")),
        str(item.get("template_id", "")),
        str(item.get("source", "")),
        str(item.get("title", "")),
    ]
    text = " ".join(fields).lower()
    if EXCLUDE_RE.search(text):
        return False
    return bool(BAR_RE.search(text) or BAR_CN_RE.search(" ".join(fields)))


def valid_exception(item: dict) -> bool:
    exc = item.get("bar_exception")
    if not isinstance(exc, dict):
        return False
    required = (
        "necessary",
        "category_count_small",
        "zero_baseline_required",
        "absolute_height_comparison",
    )
    return all(exc.get(key) is True for key in required) and bool(str(exc.get("reason", "")).strip())


def main() -> int:
    parser = project_arg("检查普通一维、二维柱状图必须有必要性例外记录")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)

    for item in items:
        if not is_python_item(item) or not ordinary_bar_item(item):
            continue
        source = str(item.get("source") or item.get("title") or item)
        if not valid_exception(item):
            errors.append(
                "Python 普通柱状图缺少完整 bar_exception 必要性记录: "
                f"{source}；需同时说明 necessary、category_count_small、zero_baseline_required、"
                "absolute_height_comparison 和 reason。"
            )

    return write_report(not errors, "check_python_bar_chart_policy", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
