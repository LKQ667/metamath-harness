#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check appendix code blocks are pure code."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


LISTING_RE = re.compile(r"\\begin\{lstlisting\}(?:\[[^\]]*\])?(.*?)\\end\{lstlisting\}", re.DOTALL)
MARKDOWN_FENCE_RE = re.compile(r"^\s*(```|~~~)")
DECORATION_RE = re.compile(r"^\s*(?:[#/%*=\\-]\s*){4,}$")
COMMENT_LINE_RE = re.compile(r"^\s*(#|//|/\*|\*|%|\"\"\"|''')")
INLINE_COMMENT_RE = re.compile(r"(?<![\"'])\s(#|//).+")


def appendix_text(text: str) -> str:
    markers = ["\\section{附录代码文件}", "\\begin{appendices}"]
    starts = [text.find(marker) for marker in markers if text.find(marker) != -1]
    if not starts:
        return ""
    return text[min(starts) :]


def listing_blocks(text: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    for match in LISTING_RE.finditer(text):
        line_no = text[: match.start(1)].count("\n") + 1
        blocks.append((line_no, match.group(1)))
    return blocks


def fallback_code_lines(text: str) -> list[tuple[int, str]]:
    appendix = appendix_text(text)
    if not appendix:
        return []
    offset = text.find(appendix)
    lines: list[tuple[int, str]] = []
    for index, line in enumerate(appendix.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            lines.append((text[:offset].count("\n") + index, line))
            continue
        if stripped.startswith("\\"):
            continue
        if stripped.startswith("{\\"):
            continue
        lines.append((text[:offset].count("\n") + index, line))
    return lines


def check_lines(lines: list[tuple[int, str]]) -> list[str]:
    errors: list[str] = []
    blank_run = 0
    for line_no, line in lines:
        stripped = line.strip()
        if not stripped:
            blank_run += 1
            if blank_run == 3:
                errors.append(f"附录代码第 {line_no} 行附近存在连续大量空行。")
            continue
        blank_run = 0
        if MARKDOWN_FENCE_RE.search(line):
            errors.append(f"附录代码第 {line_no} 行存在 Markdown 代码围栏。")
        if DECORATION_RE.search(line):
            errors.append(f"附录代码第 {line_no} 行存在装饰分隔线或格式符号。")
        if COMMENT_LINE_RE.search(line):
            errors.append(f"附录代码第 {line_no} 行存在注释行。")
        if INLINE_COMMENT_RE.search(line):
            errors.append(f"附录代码第 {line_no} 行存在行尾注释。")
    return errors


def main() -> int:
    parser = project_arg("检查论文附录代码禁止格式符号、注释和大量空行")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_appendix_code_cleanliness", errors, args.output)

    text = read_text(tex_path)
    blocks = listing_blocks(text)
    if blocks:
        for start_line, block in blocks:
            lines = [(start_line + idx, line) for idx, line in enumerate(block.splitlines())]
            errors.extend(check_lines(lines))
    else:
        errors.extend(check_lines(fallback_code_lines(text)))

    return write_report(not errors, "check_appendix_code_cleanliness", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
