#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check abstract spans at most two pages (GMCMthesis) plus layout commands."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


LABEL = "\\label{abstract:end}"
LABEL_START = "\\label{abstract:start}"
MIN_ABSTRACT_CHARS = 800
TARGET_ABSTRACT_CHARS = (850, 1050)
MAX_ABSTRACT_PAGES = 2
FORCED_BREAK_RE = re.compile(r"\\(?:newpage|clearpage|pagebreak|vfill)\b")
VSPACE_RE = re.compile(r"\\vspace\*?\s*\{([^}]*)\}")


def abstract_block(text: str) -> str:
    if "\\documentclass[bwprint]{gmcmthesis}" in text or "\\documentclass{gmcmthesis}" in text:
        start = text.find("\\begin{abstract}")
        end = text.find("\\end{abstract}", start + 1)
        if start == -1 or end == -1:
            return ""
        return text[start : end + len("\\end{abstract}")]
    start = text.find("{\\sectiontitlefont 摘要}")
    end = text.find(LABEL)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + len(LABEL)]


def abstract_page_from_aux(aux_text: str, label: str = "abstract:end") -> str | None:
    patterns = [
        rf"\\newlabel\{{{re.escape(label)}\}}\{{\{{[^{{}}]*\}}\{{([^{{}}]+)\}}",
        rf"\\newlabel\{{{re.escape(label)}\}}.*?\{{([0-9]+)\}}",
    ]
    for pattern in patterns:
        match = re.search(pattern, aux_text)
        if match:
            return match.group(1)
    return None


def text_length(block: str) -> int:
    no_comments = re.sub(r"(?<!\\)%.*", "", block)
    no_commands = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", "", no_comments)
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", no_commands))


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


def validate_abstract(text: str, aux_text: str | None) -> tuple[list[str], dict]:
    errors: list[str] = []
    huawei = "\\documentclass[bwprint]{gmcmthesis}" in text or "\\documentclass{gmcmthesis}" in text
    if text.count(LABEL) != 1:
        errors.append(f"论文主文件必须且只能包含 1 个摘要结束标记，当前为 {text.count(LABEL)} 个。")
    if huawei and text.count(LABEL_START) != 1:
        errors.append(
            f"华为杯主稿必须且只能包含 1 个摘要起始标记 `{LABEL_START}`（紧跟 `\\begin{{abstract}}` 之后），当前为 {text.count(LABEL_START)} 个。"
        )
    block = abstract_block(text)
    length = text_length(block) if block else 0
    details = {
        "effective_chars": length,
        "minimum_chars": MIN_ABSTRACT_CHARS,
        "target_chars": list(TARGET_ABSTRACT_CHARS),
        "start_page": None,
        "end_page": None,
    }
    if not block:
        errors.append("未找到摘要区域或摘要结束标记。")
    else:
        if huawei:
            if not re.search(r"\\keywords\s*\{[^{}]+\}", text):
                errors.append("华为杯主稿缺少非空 `\\keywords{...}`。")
            label_pos = text.find(LABEL)
            keywords_pos = text.find("\\keywords{")
            if label_pos != -1 and keywords_pos != -1 and label_pos < keywords_pos:
                errors.append("摘要结束标记必须放在 `\\keywords{}` 之后，确保摘要与关键词都被计入摘要页数。")
        elif "关键词" not in block or block.rfind("关键词") > block.rfind(LABEL):
            errors.append("摘要结束标记必须放在关键词之后，确保摘要与关键词都限制在第一页。")
        for line_no, line in enumerate(block.splitlines(), 1):
            if FORCED_BREAK_RE.search(line):
                errors.append(f"摘要区域第 {line_no} 行存在强制分页或填充命令。")
            for match in VSPACE_RE.finditer(line):
                if is_large_vspace(match.group(1)):
                    errors.append(f"摘要区域第 {line_no} 行存在过大的 vspace: {match.group(0)}")
        if length < MIN_ABSTRACT_CHARS:
            errors.append(
                f"摘要有效文字约 {length} 字，未达到最低要求 {MIN_ABSTRACT_CHARS} 字；"
                f"建议控制在 {TARGET_ABSTRACT_CHARS[0]}-{TARGET_ABSTRACT_CHARS[1]} 字并重新编译。"
            )

    if aux_text is None:
        errors.append("缺少 `论文/main.aux`，无法确认摘要页数；请重新编译 LaTeX。")
    else:
        end_page = abstract_page_from_aux(aux_text, "abstract:end")
        details["end_page"] = end_page
        if end_page is None:
            errors.append("`论文/main.aux` 中未找到 `abstract:end` 页码记录，请重新编译 LaTeX。")
        elif huawei:
            start_page = abstract_page_from_aux(aux_text, "abstract:start")
            details["start_page"] = start_page
            if start_page is None:
                errors.append("`论文/main.aux` 中未找到 `abstract:start` 页码记录，请重新编译 LaTeX。")
            else:
                span = int(end_page) - int(start_page) + 1
                if span > MAX_ABSTRACT_PAGES:
                    errors.append(
                        f"摘要与关键词合计跨 {span} 页（第 {start_page}–{end_page} 页），超过华为杯官方允许的 {MAX_ABSTRACT_PAGES} 页上限，必须压缩。"
                    )
        elif end_page != "1":
            errors.append(f"摘要或关键词结束标记位于第 {end_page} 页，必须压回第一页，禁止交付。")
    return errors, details


def main() -> int:
    parser = project_arg("检查摘要与关键词合计不超过两页（华为杯官方允许）且不少于最低字数")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    aux_path = project / "论文" / "main.aux"
    if not tex_path.exists():
        errors = [f"缺少论文主文件: {tex_path}"]
        return write_report(False, "check_abstract_one_page", errors, args.output)

    text = read_text(tex_path)
    aux_text = read_text(aux_path) if aux_path.exists() else None
    errors, details = validate_abstract(text, aux_text)
    return write_report(not errors, "check_abstract_one_page", errors, args.output, details)


if __name__ == "__main__":
    raise SystemExit(main())
