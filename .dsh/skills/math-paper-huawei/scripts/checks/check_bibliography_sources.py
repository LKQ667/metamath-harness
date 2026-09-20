#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查文献来源可追溯性，并阻止学习资料与赛事合规资料进入最终参考文献。"""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


SOURCE_TOKENS = ["doi", "http://", "https://", "GB/T", "ASTM", "ISBN", "出版社", "标准"]

# 赛事论文格式规范、模板说明、参赛规则：属于合规资料，不是论文论证证据。
COMPLIANCE_MARKERS = (
    "论文格式规范",
    "格式规范",
    "竞赛论文格式",
    "竞赛规则",
    "参赛规则",
    "参赛须知",
    "评阅规则",
    "评审规则",
    "模板说明",
    "模板使用说明",
    "写作规范",
    "论文模板",
)
COMPLIANCE_CONTEXT = ("竞赛", "大赛", "赛事", "研究生数学建模", "华为杯", "全国大学生", "GMCM", "CUMCM", "组委会")
# 技术标准：与题目直接相关的 GB/T、ASTM 等，不属于赛事格式规范。
TECH_STANDARD_RE = re.compile(
    r"(?:GB\s*/?\s*T|GB\s*/\s*Z|ASTM|ISO|IEC|ANSI|IEEE\s*Std|SJ/T|YB/T|DL/T)\s*[-—]?\s*\d",
    re.IGNORECASE,
)
TEXTBOOK_TITLES = ("数学模型", "数学建模", "数学建模方法与分析", "数学建模算法与应用")
# 版次仅在分类比较时统一空白写法后匹配，覆盖“第5版”“第 5 版”“第五版”；不改写原文。
EDITION_RE = re.compile(r"第\s*(?:[0-9]+|[一二三四五六七八九十百]+)\s*版")
TEXTBOOK_COMPACT_MARKERS = ("教材", "修订版", "高等学校教材", "规划教材")
BIB_ENV_BEGIN = "\\begin{thebibliography}"
BIB_ENV_END = "\\end{thebibliography}"
BIBITEM_RE = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^{}]*)\}")


def strip_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def bibitem_entries(text: str) -> tuple[list[tuple[str, str]], bool]:
    """在 thebibliography 环境内切分条目；条目必须终止于 \\end{thebibliography}，
    后续附录文字不归入末条。返回 ((bibkey, 条目文本), ...) 与环境是否正确闭合。"""
    begin = text.find(BIB_ENV_BEGIN)
    if begin == -1:
        return [], True
    end = text.find(BIB_ENV_END, begin)
    if end == -1:
        return [], False
    region = text[begin:end]
    matches = list(BIBITEM_RE.finditer(region))
    entries: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(region)
        entries.append((match.group(1).strip(), region[match.end():stop]))
    return entries, True


def is_tech_standard(text: str) -> bool:
    return bool(TECH_STANDARD_RE.search(text))


def is_compliance_material(text: str) -> bool:
    if is_tech_standard(text):
        return False
    if any(marker in text for marker in COMPLIANCE_MARKERS) and any(context in text for context in COMPLIANCE_CONTEXT):
        return True
    return bool(re.search(r"(?:竞赛|赛事|大赛)\s*论文\s*模板", text))


def is_textbook_placeholder(text: str) -> bool:
    if is_tech_standard(text):
        return False
    compact = re.sub(r"\s+", "", text)
    if not any(title in compact for title in TEXTBOOK_TITLES):
        return False
    if EDITION_RE.search(compact):
        return True
    return any(marker in compact for marker in TEXTBOOK_COMPACT_MARKERS)


def classify(text: str) -> str:
    if is_compliance_material(text):
        return "赛事合规资料"
    if is_textbook_placeholder(text):
        return "通用数学建模教材"
    return ""


def has_source_signal(entry: str) -> bool:
    lowered = entry.lower()
    return any(token.lower() in lowered for token in SOURCE_TOKENS)


def main() -> int:
    parser = project_arg("检查文献来源可追溯性并阻止学习/合规资料进入最终参考文献")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    facts: list[dict] = []

    source_map = project / "文献" / "source_map.md"
    if not source_map.exists():
        errors.append(f"缺少文献来源映射: {source_map}")
    else:
        text = read_text(source_map)
        for token in ["来源链接", "可信等级", "支撑章节"]:
            if token not in text:
                errors.append(f"source_map.md 缺少字段: {token}")

    refs = list((project / "论文").rglob("*.tex")) if (project / "论文").exists() else []
    ref_text = strip_comments("\n".join(read_text(path) for path in refs))
    entries, closed = bibitem_entries(ref_text)
    if BIB_ENV_BEGIN in ref_text and not closed:
        errors.append("thebibliography 环境缺少 \\end{thebibliography}，条目边界无法确定；请先修复参考文献环境。")
    elif not entries:
        if "\\bibitem" not in ref_text and "参考文献" not in ref_text:
            errors.append("论文中未发现参考文献")
        elif not any(token.lower() in ref_text.lower() for token in SOURCE_TOKENS):
            errors.append("参考文献缺少 DOI/URL/标准号/出版社等可追溯信息")
    for index, (key, entry) in enumerate(entries, 1):
        if not has_source_signal(entry):
            errors.append(
                f"第 {index} 条参考文献（{key or '未命名'}）缺少 DOI/URL/标准号/出版社等可追溯来源信息；"
                "请补全真实来源。来源映射无法机器核实时，在 文献/source_map.md 登记 bibkey、来源与具体支撑段落并人工复核。"
            )
        kind = classify(entry)
        if not kind:
            continue
        facts.append({"index": index, "key": key, "kind": kind, "snippet": re.sub(r"\s+", " ", entry)[:80]})
        if kind == "赛事合规资料":
            errors.append(
                f"第 {index} 条参考文献属于赛事论文格式规范/模板说明/参赛规则类合规资料，"
                "不进入最终参考文献；请移出 thebibliography，只作为内部合规依据。"
            )
        else:
            errors.append(
                f"第 {index} 条参考文献是通用数学建模教材，默认不进入最终参考文献；"
                "请转为内部学习资料，或改引该理论真正不可替代的原始论文、权威专著或领域标准。"
            )

    return write_report(
        not errors,
        "check_bibliography_sources",
        errors,
        args.output,
        {
            "rejected": facts,
            "bibitem_count": len(entries),
            "note": "来源信号与相关性支撑为两道独立核对：程序核对信号存在性，相关性支撑以 source_map 登记与人工复核为准。",
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
