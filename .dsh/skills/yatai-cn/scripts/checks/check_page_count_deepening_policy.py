#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check page-count shortfall is handled by deepening model derivation."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


PAGE_TRIGGER_TOKENS = (
    "约定页数",
    "目标页数",
    "正文页数",
    "页数不足",
    "不足页",
    "页数不够",
    "补页",
    "页数要求",
    "写满",
    "页面不足",
)
DEEPENING_MARKER = "模型建立与求解深化项"
REVIEW_TOKENS = ("变量定义", "约束来源", "推导链", "适用条件", "边界讨论", "求解细节", "结果解释")
SECTION_RE = re.compile(r"^\s*\\(?P<level>section|subsection|subsubsection)\{(?P<title>[^}]*)\}")
SUSPICIOUS_TITLE_RE = re.compile(
    r"(综合解释|预警落地|图表策略|少用.*柱状图|落地建议|创新性总结|治理含义|业务含义|"
    r"迁移应用|进一步讨论|结论稳定|风险解释边界|预防建议.*对应关系|全量提交.*质量控制|"
    r"质量控制|可复现性评价)"
)
MODEL_TITLE_RE = re.compile(r"(模型建立|模型的建立|模型求解|建立与求解|模型评价|结果分析)")
DEEPENING_POSITION_TOKENS = ("问题一", "问题二", "问题三", "问题四", "Q1", "Q2", "Q3", "Q4")
DEEPENING_SCOPE_TOKENS = ("模型建立", "模型求解", "公式推导", "约束说明", "约束来源", "结果解释")


def strip_comment(line: str) -> str:
    return re.split(r"(?<!\\)%", line, maxsplit=1)[0]


def body_before_appendix(text: str) -> str:
    markers = ("\\begin{thebibliography}", "\\begin{appendices}")
    end = len(text)
    for marker in markers:
        pos = text.find(marker)
        if pos != -1:
            end = min(end, pos)
    return text[:end]


def context_text(project: Path) -> str:
    candidates = [
        project / "README.md",
        project / "AGENT.md",
        project / "检查结果" / "三轮自查.md",
        project / "检查结果" / "推理论证复核.md",
        project / "检查结果" / "页数复核.md",
    ]
    parts: list[str] = []
    for path in candidates:
        if path.exists():
            parts.append(read_text(path))
    return "\n".join(parts)


def main() -> int:
    parser = project_arg("检查页数不足时是否只深化模型建立与求解。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    review_path = project / "检查结果" / "推理论证复核.md"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_page_count_deepening_policy", errors, args.output)

    tex = body_before_appendix(read_text(tex_path))
    joined_context = tex + "\n" + context_text(project)
    page_shortfall_triggered = any(token in joined_context for token in PAGE_TRIGGER_TOKENS)

    for line_no, raw in enumerate(tex.splitlines(), 1):
        line = strip_comment(raw)
        match = SECTION_RE.match(line)
        if not match:
            continue
        title = match.group("title")
        if SUSPICIOUS_TITLE_RE.search(title) and not MODEL_TITLE_RE.search(title):
            errors.append(f"论文正文第 {line_no} 行疑似新增弱相关凑页章节: {title}")

    if page_shortfall_triggered:
        if not review_path.exists():
            errors.append("检测到页数目标或页数不足记录，但缺少 `检查结果/推理论证复核.md`。")
        else:
            review = read_text(review_path)
            if DEEPENING_MARKER not in review:
                errors.append(f"页数不足复核缺少“{DEEPENING_MARKER}”。")
            missing = [token for token in REVIEW_TOKENS if token not in review]
            if missing:
                errors.append("页数不足深化记录缺少关键项: " + "、".join(missing))
            if not any(token in review for token in DEEPENING_POSITION_TOKENS):
                errors.append("页数不足深化记录缺少具体问题位置（问题一至问题四或 Q1-Q4）。")
            if not any(token in review for token in DEEPENING_SCOPE_TOKENS):
                errors.append("页数不足深化记录未说明内容落在模型建立、模型求解、公式推导、约束说明或结果解释中。")

    return write_report(not errors, "check_page_count_deepening_policy", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
