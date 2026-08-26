#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check appendix code blocks are pure code."""

from __future__ import annotations

import re
import tokenize
from pathlib import Path

from common import load_json, project_arg, read_text, write_report


LISTING_RE = re.compile(
    r"\\begin\{(lstlisting|Python|Matlab)\}(?:\[[^\]]*\])?(?:\{[^{}]*\})?(.*?)\\end\{\1\}",
    re.DOTALL,
)
MARKDOWN_FENCE_RE = re.compile(r"^\s*(```|~~~)")
DECORATION_RE = re.compile(r"^\s*(?:[#/%*=\\-]\s*){4,}$")
COMMENT_LINE_RE = re.compile(r"^\s*(#|//|/\*|\*|%|\"\"\"|''')")
INLINE_COMMENT_RE = re.compile(r"(?<![\"'])\s(#|//).+")
CODING_RE = re.compile(r"^#.*coding[:=]\s*[-\w.]+")


def appendix_text(text: str) -> str:
    markers = ["\\section{附录代码文件}", "\\begin{appendices}"]
    starts = [text.find(marker) for marker in markers if text.find(marker) != -1]
    if not starts:
        return ""
    return text[min(starts) :]


def listing_blocks(text: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    for match in LISTING_RE.finditer(text):
        line_no = text[: match.start(2)].count("\n") + 1
        blocks.append((line_no, match.group(2)))
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


def check_python_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = read_text(path)
    lines = text.splitlines()
    blank_run = 0
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            blank_run += 1
            if blank_run == 3:
                errors.append(f"{path} 第 {line_no} 行附近存在连续大量空行。")
        else:
            blank_run = 0
        if MARKDOWN_FENCE_RE.search(line):
            errors.append(f"{path} 第 {line_no} 行存在 Markdown 代码围栏。")
        if DECORATION_RE.search(line):
            errors.append(f"{path} 第 {line_no} 行存在装饰分隔线或格式符号。")
    try:
        tree = __import__("ast").parse(text, filename=str(path))
    except SyntaxError as exc:
        return errors + [f"附录 Python 文件语法错误 {path}: {exc}"]
    for node in __import__("ast").walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], __import__("ast").Expr):
            value = body[0].value
            if isinstance(value, __import__("ast").Constant) and isinstance(value.value, str):
                errors.append(f"{path} 存在文档字符串。")
                break
    try:
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type != tokenize.COMMENT:
                    continue
                line = lines[token.start[0] - 1] if token.start[0] <= len(lines) else ""
                allowed = token.start[0] == 1 and line.startswith("#!")
                allowed = allowed or (token.start[0] <= 2 and CODING_RE.match(line) is not None)
                if not allowed:
                    errors.append(f"{path} 第 {token.start[0]} 行存在注释。")
    except tokenize.TokenError as exc:
        errors.append(f"附录 Python 文件词法解析失败 {path}: {exc}")
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
    config_path = project / "检查结果" / "附录代码复核.json"
    if config_path.exists():
        try:
            config = load_json(config_path)
        except Exception as exc:
            errors.append(f"附录代码复核配置解析失败: {exc}")
        else:
            files = config.get("files", []) if isinstance(config, dict) else []
            for item in files:
                if not isinstance(item, dict) or not item.get("appendix"):
                    errors.append("附录代码复核配置的 files 条目缺少 appendix。")
                    continue
                path = (project / str(item["appendix"])).resolve()
                try:
                    path.relative_to((project / "论文" / "附录代码").resolve())
                except ValueError:
                    errors.append(f"附录净化文件不在 `论文/附录代码/` 下: {item['appendix']}")
                    continue
                if not path.exists():
                    errors.append(f"附录净化文件不存在: {path}")
                    continue
                errors.extend(check_python_file(path))

    return write_report(not errors, "check_appendix_code_cleanliness", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
