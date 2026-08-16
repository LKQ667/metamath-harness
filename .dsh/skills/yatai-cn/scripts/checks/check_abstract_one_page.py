#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check abstract page boundary and high-risk layout commands."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


LABEL = "\\label{abstract:end}"
FORCED_BREAK_RE = re.compile(r"\\(?:newpage|clearpage|pagebreak|vfill)\b")
VSPACE_RE = re.compile(r"\\vspace\*?\s*\{([^}]*)\}")


def abstract_block(text: str) -> str:
    start = text.find("{\\sectiontitlefont 摘要}")
    if start == -1:
        start = text.find("摘要")
    end = text.find(LABEL)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + len(LABEL)]


def abstract_page_from_aux(aux_text: str) -> str | None:
    patterns = [
        r"\\newlabel\{abstract:end\}\{\{[^{}]*\}\{([^{}]+)\}",
        r"\\newlabel\{abstract:end\}.*?\{([0-9]+)\}",
    ]
    for pattern in patterns:
        match = re.search(pattern, aux_text)
        if match:
            return match.group(1)
    return None


def first_section_page_from_aux(aux_text: str) -> tuple[str | None, str | None]:
    pattern = re.compile(r"\\@writefile\{toc\}\{\\contentsline \{section\}\{(?:\\numberline \{[^{}]*\})?([^{}]*)\}\{([^{}]+)\}")
    match = pattern.search(aux_text)
    if match:
        return match.group(1), match.group(2)
    return None, None


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


def main() -> int:
    parser = project_arg("检查摘要限制在第一页并尽量写满")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    aux_path = project / "论文" / "main.aux"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_abstract_one_page", errors, args.output)

    text = read_text(tex_path)
    if LABEL not in text:
        errors.append("摘要关键词后缺少页码检查标记 `\\label{abstract:end}`。")
    block = abstract_block(text)
    if not block:
        errors.append("未找到摘要区域或摘要结束标记。")
    else:
        for line_no, line in enumerate(block.splitlines(), 1):
            if FORCED_BREAK_RE.search(line):
                errors.append(f"摘要区域第 {line_no} 行存在强制分页或填充命令。")
            for match in VSPACE_RE.finditer(line):
                if is_large_vspace(match.group(1)):
                    errors.append(f"摘要区域第 {line_no} 行存在过大的 vspace: {match.group(0)}")
        length = text_length(block)
        if length < 700:
            errors.append(f"摘要有效文字约 {length} 字，未接近写满第一页；建议 800-1000 字。")
        if length > 1100:
            errors.append(f"摘要有效文字约 {length} 字，可能超过一页；建议 800-1000 字。")

    if aux_path.exists():
        aux_text = read_text(aux_path)
        page = abstract_page_from_aux(aux_text)
        if page is None:
            errors.append("`论文/main.aux` 中未找到 `abstract:end` 页码记录，请重新编译 LaTeX。")
        elif page != "1":
            errors.append(f"摘要结束标记位于第 {page} 页，摘要必须限制在第一页内。")
        first_title, first_page = first_section_page_from_aux(aux_text)
        if first_page is None:
            errors.append("`论文/main.aux` 中未找到正文第一节页码记录，请重新编译 LaTeX。")
        elif first_page == "1":
            title = first_title or "正文第一节"
            errors.append(f"正文第一节“{title}”仍位于第 1 页；关键词结束后必须另开一页。")
        elif first_page != "2":
            errors.append(f"正文第一节位于第 {first_page} 页；摘要后正文第一节应从第 2 页开始。")
    else:
        errors.append("缺少 `论文/main.aux`，无法确认摘要页与正文第一页边界；请重新编译 LaTeX。")

    return write_report(not errors, "check_abstract_one_page", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
