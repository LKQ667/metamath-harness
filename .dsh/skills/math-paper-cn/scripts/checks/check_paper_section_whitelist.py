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
    "模型建立与求解",
    "敏感度分析",
    "模型评价与改进",
)
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
SECTION_RE = re.compile(r"(?m)^\\section\*?\{([^{}]+)\}")


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

    found = [match.group(1).strip() for match in SECTION_RE.finditer(body)]
    for title in found:
        if any(token in title for token in FORBIDDEN_TITLE_TOKENS):
            errors.append(f"正文禁止将“{title}”作为独立主章节；相关内容应并入“五、模型建立与求解”或移至 README/检查结果/附录说明。")
        if title not in ALLOWED_SECTIONS:
            errors.append(f"正文主章节“{title}”不在模板白名单内，禁止新增主章节。")

    missing = [title for title in ALLOWED_SECTIONS if title not in found]
    if missing:
        errors.append("正文缺少模板要求主章节: " + "、".join(missing))

    return write_report(not errors, "check_paper_section_whitelist", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
