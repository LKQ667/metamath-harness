#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check paper body page count is strictly greater than 25 pages (>=26) or user target."""

from __future__ import annotations

import re
from pathlib import Path

from common import aux_label_page, paper_body_region, project_arg, read_text, write_report


DEFAULT_TARGET = 26
TARGET_RE = re.compile(r"正文页数(?:目标|不少于)\s*[:：]?\s*(\d+)")


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
    parser = project_arg("检查正文页数大于 25 页（不少于 26 页）或用户更高目标")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    aux_path = project / "论文" / "main.aux"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_body_page_count_minimum", errors, args.output)
    _, boundary_errors = paper_body_region(read_text(tex_path))
    if boundary_errors:
        return write_report(False, "check_body_page_count_minimum", boundary_errors, args.output)
    if not aux_path.exists():
        errors.append("缺少 `论文/main.aux`，无法确认正文页数；请重新编译 LaTeX。")
        return write_report(False, "check_body_page_count_minimum", errors, args.output)

    aux = read_text(aux_path)
    start = aux_label_page(aux, "body:start")
    end = aux_label_page(aux, "body:end")
    appendix = aux_label_page(aux, "appendix:start")
    if start is None:
        errors.append("`论文/main.aux` 缺少 `body:start` 页码标记。")
    if end is None:
        errors.append("`论文/main.aux` 缺少 `body:end` 页码标记。")
    if appendix is None:
        errors.append("`论文/main.aux` 缺少 `appendix:start` 页码标记。")
    if errors:
        return write_report(False, "check_body_page_count_minimum", errors, args.output)

    assert start is not None and end is not None and appendix is not None
    if start != 1:
        errors.append(f"正文必须从论文第 1 页开始，当前 `body:start` 位于第 {start} 页。")
    if end < start:
        errors.append("`body:end` 页码早于 `body:start`，正文页码边界无效。")
    if appendix != end + 1:
        errors.append(f"附录必须另起下一页：正文结束页为 {end}，附录起始页应为 {end + 1}，当前为 {appendix}。")
    pages = end - start + 1
    target = target_pages(project)
    if pages < target:
        errors.append(f"正文页数为 {pages} 页，未达到大于 25 页（不少于 {target} 页）的硬约束；不足时只能深化模型建立与求解。")

    return write_report(not errors, "check_body_page_count_minimum", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
