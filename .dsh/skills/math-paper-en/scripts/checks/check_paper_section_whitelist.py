#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the paper body sections follow the COMAP whitelist."""

from __future__ import annotations

import re
from pathlib import Path

from common import paper_body_region, project_arg, read_text, write_report


ALLOWED_SECTIONS = (
    "Introduction",
    "Assumptions and Justifications",
    "Notations",
    "Model Design and Solution",
    "Sensitivity Analysis",
    "Model Evaluation",
    "Conclusions",
)
EXTENDABLE_SECTIONS = ("Model Design and Solution",)
FORBIDDEN_TITLE_TOKENS = (
    "Candidate Method",
    "Comparison of Method",
    "Final Selection",
    "Selection of Model",
    "Architecture",
    "AI Trace",
    "AI Detection",
    "Boundary Discussion",
    "Reproducibility",
    "Reproducible",
    "Run Order",
    "Execution Order",
    "Methodology",
    "Overall Finding",
    "Summary of Finding",
    "Data-Result Link",
    "Bridge to",
    "Limitations and Future Work",
    "Acknowledg",
)
SECTION_RE = re.compile(r"(?m)^\\section\*?\{([^{}]+)\}")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def section_allowed(title: str) -> bool:
    if title in ALLOWED_SECTIONS:
        return True
    return any(title.startswith(item) for item in EXTENDABLE_SECTIONS)


def main() -> int:
    parser = project_arg("检查论文正文主章节必须严格遵守 COMAP 章节白名单")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        return write_report(False, "check_paper_section_whitelist", [f"缺少论文主文件: {tex_path}"], args.output)

    text = read_text(tex_path)
    body, boundary_errors = paper_body_region(text)
    if boundary_errors:
        return write_report(False, "check_paper_section_whitelist", boundary_errors, args.output)

    found = [match.group(1).strip() for match in SECTION_RE.finditer(body)]
    for title in found:
        if CJK_RE.search(title):
            errors.append(f"章节标题含中文，美赛论文全文必须英文: {title}")
        if any(token.lower() in title.lower() for token in FORBIDDEN_TITLE_TOKENS):
            errors.append(
                f"正文禁止把该标题作为独立主章节: {title}；"
                "相关内容应并入 Model Design and Solution、Conclusions 或移到 README/检查结果/附录说明。"
            )
        if not section_allowed(title):
            errors.append(f"正文主章节不在 COMAP 白名单内，禁止新增主章节: {title}")

    covered = set()
    for title in found:
        for allowed in ALLOWED_SECTIONS:
            if title == allowed or title.startswith(allowed):
                covered.add(allowed)
    missing = [title for title in ALLOWED_SECTIONS if title not in covered]
    if missing:
        errors.append("正文缺少模板要求主章节: " + "、".join(missing))

    return write_report(not errors, "check_paper_section_whitelist", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
