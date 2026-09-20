#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 LaTeX log 是否包含真正的硬错误，忽略宏包 Info 行。"""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


BAD_TOKENS = (
    "! Undefined control sequence",
    "! LaTeX Error",
    "Fatal error",
    "File ended while scanning",
    "Missing character",
    "not found",
    "Rerun to get cross-references right",
)
INFO_LINE_RE = re.compile(r"\bInfo:", re.I)


def scan_log(text: str) -> list[str]:
    hits: list[str] = []
    for line in text.splitlines():
        if INFO_LINE_RE.search(line):
            continue
        for token in BAD_TOKENS:
            if token in line:
                hits.append(token + " -> " + line.strip()[:140])
    return hits


def main() -> int:
    parser = project_arg("检查 LaTeX log 硬错误")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    logs = list((project / "论文").rglob("*.log")) if (project / "论文").exists() else []
    if not logs:
        errors.append("缺少论文/*.log，无法确认 LaTeX 编译质量")
    for log in logs:
        for hit in scan_log(read_text(log)):
            errors.append(f"{log} 包含 LaTeX 风险: {hit}")
    return write_report(not errors, "check_latex_log", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
