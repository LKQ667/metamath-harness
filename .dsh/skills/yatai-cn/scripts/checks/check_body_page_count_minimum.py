#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check paper body page count is at least 16 pages or user target."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


DEFAULT_TARGET = 16
TARGET_RE = re.compile(r"正文页数(?:目标|不少于)\s*[:：]?\s*(\d+)")


def label_page(aux_text: str, label: str) -> int | None:
    patterns = [
        rf"\\newlabel\{{{re.escape(label)}\}}\{{\{{[^{{}}]*\}}\{{(\d+)\}}",
        rf"\\newlabel\{{{re.escape(label)}\}}.*?\{{(\d+)\}}",
    ]
    for pattern in patterns:
        match = re.search(pattern, aux_text)
        if match:
            return int(match.group(1))
    return None


def target_pages(project: Path) -> int:
    target = DEFAULT_TARGET
    for rel in ("检查结果/页数复核.md", "README.md", "AGENT.md"):
        path = project / rel
        if not path.exists():
            continue
        for match in TARGET_RE.finditer(read_text(path)):
            target = max(target, int(match.group(1)))
    return target


def main() -> int:
    parser = project_arg("检查正文页数不少于 16 页或用户更高目标")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    aux_path = project / "论文" / "main.aux"
    errors: list[str] = []

    if not aux_path.exists():
        errors.append("缺少 `论文/main.aux`，无法确认正文页数；请重新编译 LaTeX。")
        return write_report(False, "check_body_page_count_minimum", errors, args.output)

    aux = read_text(aux_path)
    start = label_page(aux, "body:start")
    end = label_page(aux, "body:end")
    if start is None:
        errors.append("`论文/main.aux` 缺少 `body:start` 页码标记。")
    if end is None:
        errors.append("`论文/main.aux` 缺少 `body:end` 页码标记。")
    if errors:
        return write_report(False, "check_body_page_count_minimum", errors, args.output)

    assert start is not None and end is not None
    pages = end - start + 1
    target = target_pages(project)
    if pages < target:
        errors.append(f"正文页数为 {pages} 页，未达到不少于 {target} 页要求；不足时只能深化模型建立与求解。")

    return write_report(not errors, "check_body_page_count_minimum", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
