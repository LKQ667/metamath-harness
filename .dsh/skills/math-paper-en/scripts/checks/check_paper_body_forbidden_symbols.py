#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check forbidden bullet and checkbox symbols in the paper body."""

from __future__ import annotations

import re
from pathlib import Path

from common import paper_body_region, project_arg, read_text, write_report


FORBIDDEN = {"•": "项目符号", "☐": "复选框式无序列表符号"}


def strip_comment(line: str) -> str:
    return re.split(r"(?<!\\)%", line, maxsplit=1)[0]


def main() -> int:
    parser = project_arg("检查论文正文禁止项目符号和复选框式无序列表符号")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_paper_body_forbidden_symbols", errors, args.output)

    body, boundary_errors = paper_body_region(read_text(tex_path))
    if boundary_errors:
        return write_report(False, "check_paper_body_forbidden_symbols", boundary_errors, args.output)
    for line_no, raw in enumerate(body.splitlines(), 1):
        line = strip_comment(raw)
        for symbol, name in FORBIDDEN.items():
            if symbol in line:
                errors.append(f"论文正文第 {line_no} 行存在禁止的{name}。")

    return write_report(not errors, "check_paper_body_forbidden_symbols", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
