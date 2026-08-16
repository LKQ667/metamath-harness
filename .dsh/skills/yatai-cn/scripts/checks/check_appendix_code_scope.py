#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check appendix code only contains complete Q1-Q4 and sensitivity code."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


LISTING_RE = re.compile(r"\\begin\{lstlisting\}(?:\[[^\]]*\])?(.*?)\\end\{lstlisting\}", re.DOTALL)
REQUIRED_BLOCKS = {
    "Q1": re.compile(r"(Q1|问题一|第一问)", re.I),
    "Q2": re.compile(r"(Q2|问题二|第二问)", re.I),
    "Q3": re.compile(r"(Q3|问题三|第三问)", re.I),
    "Q4": re.compile(r"(Q4|问题四|第四问)", re.I),
    "灵敏度分析": re.compile(r"(灵敏度|sensitivity|sensibility)", re.I),
}
FORBIDDEN_TOKENS = (
    "buildproject",
    "run_pipeline",
    "generate_flowchart",
    "generate_flowcharts",
    "python_flowchart",
    "data_preprocess",
    "data_preprocessing",
    "数据预处理",
    "manifest",
    "finalresults",
    "final_results",
    "data.xlsx",
    "source_map",
    "run_all_checks",
    "check_",
)


def appendix_text(text: str) -> tuple[str, int]:
    marker = "\\section{附录代码文件}"
    start = text.find(marker)
    if start == -1:
        return "", 0
    return text[start:], text[:start].count("\n") + 1


def listing_contexts(text: str) -> list[tuple[int, str, str]]:
    contexts: list[tuple[int, str, str]] = []
    previous_end = 0
    for match in LISTING_RE.finditer(text):
        line_no = text[: match.start(1)].count("\n") + 1
        context = text[previous_end : match.start()]
        contexts.append((line_no, context[-500:], match.group(1)))
        previous_end = match.end()
    return contexts


def main() -> int:
    parser = project_arg("检查附录代码范围只包含完整 Q1-Q4 和灵敏度分析代码。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_appendix_code_scope", errors, args.output)

    appendix, start_line = appendix_text(read_text(tex_path))
    if not appendix:
        errors.append("未找到附录“附录代码文件”。")
        return write_report(False, "check_appendix_code_scope", errors, args.output)

    lowered = appendix.lower()
    for token in FORBIDDEN_TOKENS:
        if token.lower() in lowered:
            errors.append(f"附录代码文件包含禁止放置的对象或脚本: {token}")

    blocks = listing_contexts(appendix)
    if not blocks:
        errors.append("附录代码文件缺少 lstlisting 代码块，无法确认完整 Q1-Q4 与灵敏度分析代码。")
    found: set[str] = set()
    for line_no, context, code in blocks:
        label_text = context + "\n" + code[:300]
        for name, pattern in REQUIRED_BLOCKS.items():
            if pattern.search(label_text):
                found.add(name)
        if "完整" not in context and "代码" not in context:
            errors.append(f"附录代码第 {start_line + line_no - 1} 行附近缺少“完整代码”类标题说明。")

    missing = [name for name in REQUIRED_BLOCKS if name not in found]
    if missing:
        errors.append("附录代码文件未覆盖完整代码块: " + "、".join(missing))

    return write_report(not errors, "check_appendix_code_scope", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
