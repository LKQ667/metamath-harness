#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check visible internal paths in the paper body."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


ABS_RE = re.compile(r"([A-Za-z]:\\|/[Uu]sers/|/ho[m]e/|C:\\Users\\|F:\\|f:\\)")
PROMPT_PATH_RE = re.compile(r"(手绘图|AI绘图|ai绘图)/[^\s{}]+\.md")
INTERNAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_\\])("
    r"Q\d+/|scripts/|data/|results/|figures/|assets/|references/|"
    r"论文/|摘要/|文献/|赛题/|数据预处理/|灵敏度分析/|检查结果/"
    r")"
)
SOURCE_COMMAND_RE = re.compile(r"^\s*\\(?:includegraphics|input|include|bibliography|addbibresource)\b")


def strip_comment(line: str) -> str:
    return re.split(r"(?<!\\)%", line, maxsplit=1)[0]


def paper_body(text: str) -> str:
    end_markers = [
        "\\renewcommand{\\refname}",
        "\\begin{thebibliography}",
        "\\begin{appendices}",
    ]
    end = len(text)
    for marker in end_markers:
        pos = text.find(marker)
        if pos != -1:
            end = min(end, pos)
    return text[:end]


def main() -> int:
    parser = project_arg("检查论文正文禁止显示内部文件路径")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_paper_internal_paths", errors, args.output)

    body = paper_body(read_text(tex_path))
    for line_no, raw in enumerate(body.splitlines(), 1):
        line = strip_comment(raw)
        if SOURCE_COMMAND_RE.search(line):
            continue
        visible = PROMPT_PATH_RE.sub("", line)
        if ABS_RE.search(visible):
            errors.append(f"论文正文第 {line_no} 行存在绝对路径。")
        if INTERNAL_PATH_RE.search(visible):
            errors.append(f"论文正文第 {line_no} 行存在内部文件路径；只允许提示词相对路径。")

    return write_report(not errors, "check_paper_internal_paths", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
