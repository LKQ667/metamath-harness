#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check paper body sections follow the built-in template whitelist."""

from __future__ import annotations

import re
from pathlib import Path

from common import paper_body_region, project_arg, read_text, write_report


ALLOWED_SECTIONS = (
    "问题重述",
    "问题分析",
    "模型假设",
    "符号说明",
    "模型假设与符号说明",
    "模型建立与求解",
    "敏感度分析",
    "模型评价与改进",
    "模型总结与评价",
)
HUAWEI_FIXED_SECTIONS = ("问题重述", "模型假设与符号说明", "模型总结与评价")
HUAWEI_PROBLEM_RE = re.compile(r"^问题[一二三四五六七八九十百]+模型建立与求解$")
FORBIDDEN_TITLE_TOKENS = (
    "候选方法比较",
    "最终选择",
    "体系结构",
    "AI 痕迹检测",
    "AI痕迹检测",
    "边界讨论",
    "失效情形",
    "衔接逻辑",
    "方法论",
    "整体发现",
    "整体总结",
    "数据-结果回扣",
    "数据结果回扣",
    "可复现性",
    "运行顺序",
)
SECTION_RE = re.compile(r"(?m)^[ \t]*\\section\*?\s*\{([^{}]+)\}")
SUBSECTION_RE = re.compile(r"(?m)^[ \t]*\\subsection\*?\s*\{([^{}]+)\}")
SYMBOL_FLOAT_TABLE_RE = re.compile(r"\\begin\s*\{table\*?\}")
SYMBOL_TABLE_ENV_RE = re.compile(r"\\begin\{(tabular|tabularx|longtable)\}")
FIGURE_ENV_RE = re.compile(r"\\begin\s*\{figure\*?\}")
CAPTION_RE = re.compile(r"\\caption\b")


def strip_comments(text: str) -> str:
    return "\n".join(re.split(r"(?<!\\)%", line, maxsplit=1)[0] for line in text.splitlines())


def check_symbol_block_structure(body: str, errors: list[str]) -> None:
    """M14 源码层：第二主章节“模型假设与符号说明”的子章节顺序、符号表
    存在性、非浮动容器与内容归属。仅做可机械确定的结构判断；
    目录、注释已排除（body 来自 paper_body_region，注释在此处剔除）。"""
    cleaned = strip_comments(body)
    section_matches = list(SECTION_RE.finditer(cleaned))
    anchors = [m for m in section_matches if m.group(1).strip() == "模型假设与符号说明"]
    if not anchors:
        return  # 主章节缺失由主检查报告。
    if len(anchors) != 1 or section_matches.index(anchors[0]) != 1:
        errors.append("“模型假设与符号说明”必须唯一且为正文第二主章节。")
    anchor = anchors[0]
    end = next((m.start() for m in section_matches if m.start() > anchor.start()), len(cleaned))
    block = cleaned[anchor.end():end]
    subsections = list(SUBSECTION_RE.finditer(block))
    if [m.group(1).strip() for m in subsections] != ["模型假设", "符号说明"]:
        errors.append("第二主章节必须且只能依次包含一个“模型假设”和一个“符号说明”subsection，不得缺失、重复或插入其他subsection。")
        return
    if any(re.search(r"\\subsection\*", m.group(0)) for m in subsections):
        errors.append("模型假设与符号说明须使用模板原生带编号subsection，不得使用星号版本。")
    symbol_block = block[subsections[1].end():]
    if SYMBOL_FLOAT_TABLE_RE.search(symbol_block):
        errors.append("符号表使用了可漂移浮动容器 \\begin{table}；短表用非浮动 tabular/tabularx，超过一页用 longtable（重复表头、保存/恢复 table 计数）。")
    table_count = len(SYMBOL_TABLE_ENV_RE.findall(symbol_block))
    if table_count > 1:
        errors.append("符号说明必须只有一个逻辑符号表；多页用同一个longtable续排，不得重复建表。")
    if not table_count:
        errors.append("“符号说明”subsection 内缺少符号表（tabular/tabularx/longtable 之一）。")
    if FIGURE_ENV_RE.search(symbol_block):
        errors.append("符号说明标题与符号表之间插入了 figure 环境：数据分析图/EDA 图必须移入对应问题的模型建立与求解章节。")
    if CAPTION_RE.search(symbol_block):
        errors.append("符号表不得带 caption/编号（保持无“表1”编号语义，正式结果表编号不受影响）。")


def main() -> int:
    parser = project_arg("检查论文正文主章节必须严格遵守模板白名单")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_paper_section_whitelist", errors, args.output)

    text = read_text(tex_path)
    body, boundary_errors = paper_body_region(text)
    if boundary_errors:
        return write_report(False, "check_paper_section_whitelist", boundary_errors, args.output)

    huawei = "\\documentclass[bwprint]{gmcmthesis}" in text or "\\documentclass{gmcmthesis}" in text
    found = [match.group(1).strip() for match in SECTION_RE.finditer(strip_comments(body))]
    if huawei:
        problem_sections = []
        for title in found:
            if any(token in title for token in FORBIDDEN_TITLE_TOKENS):
                errors.append(f"正文禁止将“{title}”作为独立主章节；相关内容应并入对应“问题 X 模型建立与求解”章节或移至 README/检查结果/附录说明。")
            elif HUAWEI_PROBLEM_RE.match(title):
                problem_sections.append(title)
            elif title not in HUAWEI_FIXED_SECTIONS:
                errors.append(f"正文主章节“{title}”不在华为杯模板主结构内，禁止新增主章节。")
        missing = [title for title in HUAWEI_FIXED_SECTIONS if title not in found]
        if missing:
            errors.append("正文缺少华为杯模板要求主章节: " + "、".join(missing))
        if not problem_sections:
            errors.append("正文缺少“问题 X 模型建立与求解”主章节，必须按实际问数依次给出。")
        expected = ["问题重述", "模型假设与符号说明", *problem_sections, "模型总结与评价"]
        if found != expected or len(set(found)) != len(found):
            errors.append("正文主章节须唯一且依次为问题重述、模型假设与符号说明、各问题模型建立与求解、模型总结与评价。")
        def chinese_number(number: int) -> str:
            digits = "零一二三四五六七八九"
            if number < 10:
                return digits[number]
            if number < 100:
                tens, units = divmod(number, 10)
                return (digits[tens] if tens > 1 else "") + "十" + (digits[units] if units else "")
            return str(number)
        expected_problems = [f"问题{chinese_number(i)}模型建立与求解" for i in range(1, len(problem_sections) + 1)]
        if problem_sections != expected_problems:
            errors.append("问题主章节必须从问题一起按实际问数连续排列，不得跳号、重复或倒序。")
        check_symbol_block_structure(body, errors)
    else:
        for title in found:
            if any(token in title for token in FORBIDDEN_TITLE_TOKENS):
                errors.append(f"正文禁止将“{title}”作为独立主章节；相关内容应并入“模型建立与求解”或移至 README/检查结果/附录说明。")
            if title not in ALLOWED_SECTIONS:
                errors.append(f"正文主章节“{title}”不在模板白名单内，禁止新增主章节。")
        missing = [title for title in ALLOWED_SECTIONS if title not in found]
        if missing:
            errors.append("正文缺少模板要求主章节: " + "、".join(missing))

    return write_report(not errors, "check_paper_section_whitelist", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
