#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check Summary Sheet and body emphasis is complete, English and restrained."""

from __future__ import annotations

import json
import re
from pathlib import Path

from common import SUMMARY_TITLE_MARKER, project_arg, read_text, write_report


LABEL = "\\label{abstract:end}"
BOLD_RE = re.compile(r"\\(?:paperstrong|textbf)\{([^{}]*)\}")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")
MAX_BOLD_CHARS = 60
MAX_BOLD_PER_100_WORDS = 3.0
MIN_KEYWORD_BOLDS = 3
PROBLEM_RE = re.compile(r"Problem\s*(?:No\.?\s*)?([1-9][0-9]?)", re.I)


def question_count(project: Path) -> int:
    path = project / "项目状态.json"
    if not path.exists():
        return 0
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    value = state.get("question_count") if isinstance(state, dict) else None
    return value if isinstance(value, int) and value > 0 else 0


def summary_block(text: str) -> str:
    start = text.find(SUMMARY_TITLE_MARKER)
    end = text.find(LABEL)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + len(LABEL)]


def body_block(text: str) -> str:
    end = text.find(LABEL)
    return text[end + len(LABEL):] if end != -1 else ""


def check_bold_spans(block: str, where: str, errors: list[str]) -> int:
    count = 0
    for span in BOLD_RE.findall(block):
        count += 1
        stripped = span.strip()
        if not stripped:
            errors.append(f"{where}存在空的加粗命令。")
            continue
        if CJK_RE.search(stripped):
            errors.append(f"{where}加粗内容含中文，必须改为英文: {stripped}")
        if len(stripped) > MAX_BOLD_CHARS:
            errors.append(f"{where}加粗跨度过长（{len(stripped)} 字符），禁止整句加粗: {stripped[:40]}...")
        if stripped.endswith(".") or ". " in stripped:
            errors.append(f"{where}加粗内容是完整句，只能加粗短语: {stripped[:40]}...")
    return count


def main() -> int:
    parser = project_arg("检查英文论文摘要与正文加粗是否完整且克制")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []
    if not tex_path.exists():
        return write_report(False, "check_paper_emphasis", [f"缺少论文主文件: {tex_path}"], args.output)

    text = read_text(tex_path)
    summary = summary_block(text)
    if not summary:
        return write_report(False, "check_paper_emphasis", ["未找到 Summary Sheet 区块，无法检查加粗结构。"], args.output)

    total = question_count(project)
    problems = {int(item) for item in PROBLEM_RE.findall(summary)}
    if total:
        missing = [index for index in range(1, total + 1) if index not in problems]
        if missing:
            errors.append("Summary Sheet 缺少分问加粗标签，需逐问写 For Problem N 并加粗: " + "、".join(str(i) for i in missing))
    elif not problems:
        errors.append("Summary Sheet 未发现 For Problem N 形式的分问加粗标签。")

    keywords_pos = summary.rfind("Keywords")
    if keywords_pos == -1:
        errors.append("Summary Sheet 未找到 Keywords 行。")
    else:
        keyword_bolds = BOLD_RE.findall(summary[keywords_pos:])
        if len(keyword_bolds) < MIN_KEYWORD_BOLDS:
            errors.append(f"Keywords 行必须逐个关键词加粗，当前仅 {len(keyword_bolds)} 处加粗。")

    summary_bolds = check_bold_spans(summary, "Summary Sheet", errors)
    body = body_block(text)
    body_bolds = check_bold_spans(body, "正文", errors)

    body_words = len(WORD_RE.findall(re.sub(r"\\[A-Za-z]+\*?(?:\{[^{}]*\})?", " ", body)))
    density = body_bolds * 100 / max(body_words, 1)
    if density > MAX_BOLD_PER_100_WORDS:
        errors.append(
            f"正文加粗密度为每百词 {density:.2f} 处，超过 {MAX_BOLD_PER_100_WORDS:.0f} 处上限，属于机械加粗。"
        )
    if body_bolds == 0:
        errors.append("正文没有任何重点加粗；关键模型、判据与核心数值结论必须选择性加粗。")

    details = {"summary_bolds": summary_bolds, "body_bolds": body_bolds, "question_count": total, "problems_found": sorted(problems)}
    return write_report(not errors, "check_paper_emphasis", errors, args.output, details)


if __name__ == "__main__":
    raise SystemExit(main())
