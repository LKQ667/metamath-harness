#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the body length contract and the COMAP 25-page hard limit."""

from __future__ import annotations

import json
import re
from pathlib import Path

from common import aux_label_page, paper_body_region, project_arg, read_text, write_report


DEFAULT_BODY_TARGET = 12
MAX_TOTAL_PAGES = 25
TARGET_RE = re.compile(r"正文页数(?:目标|不少于)\s*[:：]?\s*(\d+)")


def target_pages(project: Path) -> int:
    target = DEFAULT_BODY_TARGET
    state_path = project / "项目状态.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
        value = state.get("body_pages") if isinstance(state, dict) else None
        if isinstance(value, int) and value > 0:
            target = max(target, value)
    for rel in ("检查结果/页数复核.md", "README.md", "AGENT.md"):
        path = project / rel
        if not path.exists():
            continue
        for match in TARGET_RE.finditer(read_text(path)):
            target = max(target, int(match.group(1)))
    return target


def main() -> int:
    parser = project_arg("检查正文页数达标且总页数不超过 COMAP 25 页上限")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    aux_path = project / "论文" / "main.aux"
    errors: list[str] = []

    if not tex_path.exists():
        return write_report(False, "check_body_page_count_minimum", [f"缺少论文主文件: {tex_path}"], args.output)
    _, boundary_errors = paper_body_region(read_text(tex_path))
    if boundary_errors:
        return write_report(False, "check_body_page_count_minimum", boundary_errors, args.output)
    if not aux_path.exists():
        return write_report(
            False,
            "check_body_page_count_minimum",
            ["缺少 `论文/main.aux`，无法确认页数；请重新编译 LaTeX。"],
            args.output,
        )

    aux = read_text(aux_path)
    start = aux_label_page(aux, "body:start")
    end = aux_label_page(aux, "body:end")
    appendix = aux_label_page(aux, "appendix:start")
    total = aux_label_page(aux, "paper:end")
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
        errors.append(f"正文必须从第 1 页开始（Summary Sheet 即第 1 页），当前 `body:start` 位于第 {start} 页。")
    if end < start:
        errors.append("`body:end` 页码早于 `body:start`，正文页码边界无效。")
    if appendix != end + 1:
        errors.append(f"附录必须另起下一页：正文结束页为 {end}，附录起始页应为 {end + 1}，当前为 {appendix}。")

    pages = end - start + 1
    target = target_pages(project)
    if pages < target:
        errors.append(
            f"正文页数为 {pages} 页，未达到不少于 {target} 页要求；"
            "不足时只能深化 Model Design and Solution，不得新增主章节或堆砌图表。"
        )
    if total is None:
        errors.append("`论文/main.aux` 缺少 `paper:end` 页码标记，无法核对 COMAP 页数上限。")
    else:
        if total > MAX_TOTAL_PAGES:
            errors.append(f"全文共 {total} 页，超过 COMAP 25 页硬上限，必须压缩后重新编译。")
        details = {"body_pages": pages, "total_pages": total, "target": target, "max_total_pages": MAX_TOTAL_PAGES}
        return write_report(not errors, "check_body_page_count_minimum", errors, args.output, details)

    return write_report(not errors, "check_body_page_count_minimum", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
