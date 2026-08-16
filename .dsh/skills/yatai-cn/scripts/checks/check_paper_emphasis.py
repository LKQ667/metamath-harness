#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 yatai-cn 论文的摘要与正文粗体强调是否完整且克制。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from common import project_arg, read_text, write_report


ABSTRACT_TITLE = "{\\sectiontitlefont 摘要}"
ABSTRACT_END = "\\label{abstract:end}"
BODY_END = "\\label{body:end}"
PROBLEM_RE = re.compile(r"针对问题(?:[一二三四五六七八九十百]+|\d+|[A-Za-z])")
SENTENCE_END_RE = re.compile(r"[。！？!?]")
MAX_ABSTRACT_BOLD_RATIO = 0.40
MAX_BODY_BOLD_RATIO = 0.12
MAX_BOLD_VISIBLE_CHARS = 80


@dataclass(frozen=True)
class BoldSpan:
    start: int
    end: int
    content: str


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def extract_textbf(text: str) -> list[BoldSpan]:
    spans: list[BoldSpan] = []
    for match in re.finditer(r"\\(?:textbf|paperstrong)\s*\{", text):
        depth = 1
        index = match.end()
        while index < len(text) and depth:
            if text[index] == "{" and (index == 0 or text[index - 1] != "\\"):
                depth += 1
            elif text[index] == "}" and (index == 0 or text[index - 1] != "\\"):
                depth -= 1
            index += 1
        if depth == 0:
            spans.append(BoldSpan(match.start(), index, text[match.end(): index - 1]))
    return spans


def visible_tex(text: str) -> str:
    text = re.sub(r"\\label\{[^{}]*\}", "", text)
    text = re.sub(r"\\(?:cite|ref|eqref|includegraphics|url|href)\*?(?:\[[^\]]*\])?\{[^{}]*\}", "", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", "", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("\\%", "%").replace("~", " ")
    return re.sub(r"\s+", "", text)


def visible_count(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9%]", visible_tex(text)))


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def bold_ratio(region: str, spans: list[BoldSpan]) -> float:
    total = visible_count(region)
    bold = sum(visible_count(span.content) for span in spans)
    return bold / max(total, 1)


def check_long_or_sentence(region: str, spans: list[BoldSpan], region_name: str, full_text: str, base: int) -> list[str]:
    errors: list[str] = []
    for span in spans:
        content = visible_tex(span.content)
        if SENTENCE_END_RE.search(content):
            errors.append(
                f"{region_name}第 {line_number(full_text, base + span.start)} 行粗体包含完整句末标点，"
                "应只保留关键短语。"
            )
        previous_end = max((region.rfind(mark, 0, span.start) for mark in "。！？!?"), default=-1)
        paragraph_end = region.rfind("\n\n", 0, span.start)
        context_start = max(previous_end + 1, paragraph_end + 2)
        before_source = re.sub(
            r"\\(?:section|subsection|subsubsection)\*?\{[^{}]*\}",
            "",
            region[context_start:span.start],
        )
        before = visible_tex(before_source).strip("，,：:；;")
        after = region[span.end:span.end + 20]
        if not before and re.match(r"^\s*[。！？!?]", after):
            errors.append(
                f"{region_name}第 {line_number(full_text, base + span.start)} 行完整句被整体加粗，"
                "句末标点即使位于粗体命令外也不允许。"
            )
        if visible_count(span.content) > MAX_BOLD_VISIBLE_CHARS:
            errors.append(
                f"{region_name}第 {line_number(full_text, base + span.start)} 行单段粗体超过 "
                f"{MAX_BOLD_VISIBLE_CHARS} 个可见字符，疑似整句或整段加粗。"
            )
    return errors


def main() -> int:
    parser = project_arg("检查 APMCM 中文赛论文摘要与正文的选择性粗体强调")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []
    if not tex_path.exists():
        return write_report(False, "check_paper_emphasis", [f"缺少论文主文件: {tex_path}"], args.output)

    raw = read_text(tex_path)
    text = strip_comments(raw)
    abstract_title = text.find(ABSTRACT_TITLE)
    abstract_end = text.find(ABSTRACT_END, abstract_title + 1)
    if abstract_title == -1 or abstract_end == -1:
        return write_report(False, "check_paper_emphasis", ["无法定位摘要标题或 abstract:end 标记。"], args.output)

    abstract_start = abstract_title + len(ABSTRACT_TITLE)
    abstract = text[abstract_start:abstract_end]
    abstract_spans = extract_textbf(abstract)
    problems = list(PROBLEM_RE.finditer(abstract))
    if not problems:
        errors.append("摘要未找到“针对问题X”标签。")
    for index, problem in enumerate(problems):
        label = problem.group(0)
        containing = [span for span in abstract_spans if span.start <= problem.start() and problem.end() <= span.end]
        if not containing:
            errors.append(f"摘要第 {line_number(text, abstract_start + problem.start())} 行“{label}”未加粗。")
        elif all(visible_tex(span.content) != label for span in containing):
            errors.append(f"摘要第 {line_number(text, abstract_start + problem.start())} 行“{label}”必须单独加粗，不能连带标点或正文。")
        section_end = problems[index + 1].start() if index + 1 < len(problems) else abstract.rfind("关键词")
        section_end = len(abstract) if section_end == -1 else section_end
        evidence = [
            span for span in abstract_spans
            if problem.end() <= span.start < section_end and visible_tex(span.content) != label
        ]
        if not evidence:
            errors.append(f"摘要“{label}”段缺少重要算法、核心模型或主要结论的选择性粗体。")

    keyword_pos = abstract.rfind("关键词")
    if keyword_pos == -1:
        errors.append("摘要缺少关键词区域。")
    else:
        keyword_source = abstract[keyword_pos:]
        keyword_spans = extract_textbf(keyword_source)
        bold_texts = [visible_tex(span.content).strip("：:") for span in keyword_spans]
        all_bold_texts = [visible_tex(span.content).strip("：:") for span in abstract_spans]
        if "关键词" not in all_bold_texts:
            errors.append("“关键词”三个字必须加粗。")
        visible_keywords = visible_tex(keyword_source)
        visible_keywords = re.sub(r"^关键词[：:]?", "", visible_keywords)
        terms = [term for term in re.split(r"[；;]", visible_keywords) if term]
        for term in terms:
            if term not in bold_texts:
                errors.append(f"关键词“{term}”必须单独加粗。")

    ratio = bold_ratio(abstract, abstract_spans)
    if ratio > MAX_ABSTRACT_BOLD_RATIO:
        errors.append(f"摘要粗体覆盖率为 {ratio:.1%}，超过 {MAX_ABSTRACT_BOLD_RATIO:.0%}，疑似大面积机械加粗。")
    errors.extend(check_long_or_sentence(abstract, abstract_spans, "摘要", text, abstract_start))

    body_start = abstract_end + len(ABSTRACT_END)
    body_end = text.find("\\begin{thebibliography}", body_start)
    if body_end == -1:
        body_end = text.find(BODY_END, body_start)
    if body_end == -1:
        errors.append("无法定位正文结束位置。")
    else:
        body = text[body_start:body_end]
        body_spans = extract_textbf(body)
        body_ratio = bold_ratio(body, body_spans)
        if body_ratio > MAX_BODY_BOLD_RATIO:
            errors.append(f"正文粗体覆盖率为 {body_ratio:.1%}，超过 {MAX_BODY_BOLD_RATIO:.0%}，疑似整篇机械加粗。")
        errors.extend(check_long_or_sentence(body, body_spans, "正文", text, body_start))

    return write_report(not errors, "check_paper_emphasis", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
