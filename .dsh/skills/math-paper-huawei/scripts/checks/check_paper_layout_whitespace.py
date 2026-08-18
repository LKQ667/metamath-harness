#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check risky whitespace commands in the paper body."""

from __future__ import annotations

import re
from pathlib import Path

from common import paper_body_region, project_arg, read_text, write_report


FORCED_BREAK_RE = re.compile(r"\\(?:newpage|clearpage|pagebreak|vfill)\b")
VSPACE_RE = re.compile(r"\\vspace\*?\s*\{([^}]*)\}")
EMPTY_FLOAT_RE = re.compile(
    r"\\begin\{(figure|table)\}.*?\\end\{\1\}",
    re.DOTALL,
)


def strip_comment(line: str) -> str:
    return re.split(r"(?<!\\)%", line, maxsplit=1)[0]


def is_large_vspace(value: str) -> bool:
    compact = value.replace(" ", "")
    if any(unit in compact for unit in ("textheight", "pageheight", "paperheight", "fill")):
        return True
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(cm|mm|in|pt|em|ex|\\baselineskip)", compact)
    if not match:
        return True
    amount = float(match.group(1))
    unit = match.group(2)
    limits = {
        "cm": 1.0,
        "mm": 10.0,
        "in": 0.4,
        "pt": 24.0,
        "em": 2.0,
        "ex": 4.0,
        "\\baselineskip": 1.0,
    }
    return amount > limits[unit]


def main() -> int:
    parser = project_arg("检查论文正文禁止大半页空白和高风险留白命令")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_paper_layout_whitespace", errors, args.output)

    body, boundary_errors = paper_body_region(read_text(tex_path))
    if boundary_errors:
        return write_report(False, "check_paper_layout_whitespace", boundary_errors, args.output)
    lines = body.splitlines()
    abstract_end = body.find("\\label{abstract:end}")
    first_section = body.find("\\section{问题重述}")
    blank_run = 0
    offset = 0
    for line_no, raw in enumerate(lines, 1):
        line = strip_comment(raw)
        line_start = offset
        offset += len(raw) + 1
        if not line.strip():
            blank_run += 1
            if blank_run == 6:
                errors.append(f"论文正文第 {line_no} 行附近存在连续大量空行，可能造成大段留白。")
            continue
        blank_run = 0
        for match in FORCED_BREAK_RE.finditer(line):
            command = match.group(0)
            allowed_abstract_break = (
                command in ("\\newpage", "\\clearpage")
                and abstract_end != -1
                and first_section != -1
                and abstract_end < line_start < first_section
            )
            if not allowed_abstract_break:
                errors.append(f"论文正文第 {line_no} 行存在强制分页或填充命令，禁止制造大半页空白。")
        for match in VSPACE_RE.finditer(line):
            if is_large_vspace(match.group(1)):
                errors.append(f"论文正文第 {line_no} 行存在过大的 vspace: {match.group(0)}")

    for match in EMPTY_FLOAT_RE.finditer(body):
        block = match.group(0)
        if not re.search(r"\\includegraphics|\\begin\{tabular\}|\\begin\{longtable\}", block):
            line_no = body[: match.start()].count("\n") + 1
            errors.append(f"论文正文第 {line_no} 行附近存在空的 {match.group(1)} 环境。")

    return write_report(not errors, "check_paper_layout_whitespace", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
