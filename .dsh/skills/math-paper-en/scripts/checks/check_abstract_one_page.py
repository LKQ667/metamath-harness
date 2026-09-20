#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the COMAP Summary Sheet stays on page 1 and is written full enough."""

from __future__ import annotations

import re
from pathlib import Path

from common import SUMMARY_TITLE_MARKER, project_arg, read_text, write_report


LABEL = "\\label{abstract:end}"
KEYWORDS_MARKER = "Keywords"
MIN_SUMMARY_WORDS = 320
TARGET_SUMMARY_WORDS = (400, 520)
FORCED_BREAK_RE = re.compile(r"\\(?:newpage|clearpage|pagebreak|vfill)\b")
VSPACE_RE = re.compile(r"\\vspace\*?\s*\{([^}]*)\}")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def summary_block(text: str) -> str:
    start = text.find(SUMMARY_TITLE_MARKER)
    end = text.find(LABEL)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + len(LABEL)]


def summary_end_page(aux_text: str) -> str | None:
    patterns = [
        r"\\newlabel\{abstract:end\}\{\{[^{}]*\}\{([^{}]+)\}",
        r"\\newlabel\{abstract:end\}.*?\{([0-9]+)\}",
    ]
    for pattern in patterns:
        match = re.search(pattern, aux_text)
        if match:
            return match.group(1)
    return None


def count_words(block: str) -> int:
    no_comments = re.sub(r"(?<!\\)%.*", "", block)
    no_commands = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", no_comments)
    return len(WORD_RE.findall(no_commands))


def is_large_vspace(value: str) -> bool:
    compact = value.replace(" ", "")
    if any(unit in compact for unit in ("textheight", "pageheight", "paperheight", "fill")):
        return True
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(cm|mm|in|pt|em|ex|\\baselineskip)", compact)
    if not match:
        return True
    amount = float(match.group(1))
    unit = match.group(2)
    limits = {"cm": 1.0, "mm": 10.0, "in": 0.4, "pt": 24.0, "em": 2.0, "ex": 4.0, "\\baselineskip": 1.0}
    return amount > limits[unit]


def validate_summary(text: str, aux_text: str | None) -> tuple[list[str], dict]:
    errors: list[str] = []
    if text.count(LABEL) != 1:
        errors.append(f"论文主文件必须且只能包含 1 个 `{LABEL}`，当前为 {text.count(LABEL)} 个。")
    block = summary_block(text)
    words = count_words(block) if block else 0
    details = {
        "effective_words": words,
        "minimum_words": MIN_SUMMARY_WORDS,
        "target_words": list(TARGET_SUMMARY_WORDS),
        "end_page": None,
    }
    if not block:
        errors.append("未找到 `{\\sectiontitlefont Summary}` 区块或 Summary Sheet 结束标记。")
    else:
        if CJK_RE.search(block):
            errors.append("Summary Sheet 出现中文字符；美赛交付物必须全英文。")
        if KEYWORDS_MARKER not in block or block.rfind(KEYWORDS_MARKER) > block.rfind(LABEL):
            errors.append("`\\label{abstract:end}` 必须放在 Keywords 之后，确保 Summary 与 Keywords 都在第一页。")
        for line_no, line in enumerate(block.splitlines(), 1):
            if FORCED_BREAK_RE.search(line):
                errors.append(f"Summary Sheet 第 {line_no} 行存在强制分页或填充命令。")
            for match in VSPACE_RE.finditer(line):
                if is_large_vspace(match.group(1)):
                    errors.append(f"Summary Sheet 第 {line_no} 行存在过大的 vspace: {match.group(0)}")
        if words < MIN_SUMMARY_WORDS:
            errors.append(
                f"Summary Sheet 有效英文约 {words} 词，低于最低要求 {MIN_SUMMARY_WORDS} 词；"
                f"建议 {TARGET_SUMMARY_WORDS[0]}-{TARGET_SUMMARY_WORDS[1]} 词并铺满第一页。"
            )

    if aux_text is None:
        errors.append("缺少 `论文/main.aux`，无法确认 Summary Sheet 是否独占第一页；请重新编译 LaTeX。")
    else:
        page = summary_end_page(aux_text)
        details["end_page"] = page
        if page is None:
            errors.append("`论文/main.aux` 中未找到 `abstract:end` 页码记录，请重新编译 LaTeX。")
        elif page != "1":
            errors.append(f"Summary Sheet 或 Keywords 结束于第 {page} 页，必须压回第 1 页，禁止交付。")
    return errors, details


def main() -> int:
    parser = project_arg("检查 Summary Sheet 独占第一页并尽量写满")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    aux_path = project / "论文" / "main.aux"
    if not tex_path.exists():
        return write_report(False, "check_abstract_one_page", [f"缺少论文主文件: {tex_path}"], args.output)

    errors, details = validate_summary(read_text(tex_path), read_text(aux_path) if aux_path.exists() else None)
    return write_report(not errors, "check_abstract_one_page", errors, args.output, details)


if __name__ == "__main__":
    raise SystemExit(main())
