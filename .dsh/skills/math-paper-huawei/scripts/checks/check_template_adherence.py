#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查论文是否保持华为杯 GMCMthesis 内置模板身份与官方结构。"""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


REQUIRED_TEMPLATE_MARKERS = [
    "\\documentclass[bwprint]{gmcmthesis}",
    "\\baominghao{",
    "\\schoolname{",
    "\\membera{",
    "\\begin{abstract}",
    "\\keywords{",
    "\\begin{thebibliography}",
    "\\begin{appendices}",
]


def main() -> int:
    parser = project_arg("检查 main.tex 是否偏离华为杯内置模板。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    tex_path = project / "论文" / "main.tex"

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_template_adherence", errors, args.output)

    text = read_text(tex_path)
    if "\\maketitle" not in text:
        errors.append("华为杯封面必须由 GMCMthesis 模板的 `\\maketitle` 生成，不得删除或另造封面。")
    maketoc_match = re.search(r"(?m)^[ \t]*\\maketoc\b", text)
    if maketoc_match is None:
        errors.append("华为杯目录必须由 GMCMthesis 模板原生的 `\\maketoc` 生成（位于摘要之后），不得省略。")
    else:
        end_abstract = text.find("\\end{abstract}")
        if end_abstract != -1 and maketoc_match.start() < end_abstract:
            errors.append("`\\maketoc` 必须位于摘要之后（官方顺序：封面→摘要→目录→正文，与官方示例 example.tex 一致）。")
    if "\\tableofcontents" in text:
        errors.append("目录必须使用模板原生 `\\maketoc`，禁止直接调用 `\\tableofcontents` 或手写目录环境。")
    if "\\begin{abstract}" not in text or "\\end{abstract}" not in text:
        errors.append("华为杯模板必须使用 gmcmthesis 提供的 `abstract` 环境。")

    missing = [marker for marker in REQUIRED_TEMPLATE_MARKERS if marker not in text]
    if missing:
        errors.append(
            "缺少华为杯模板关键结构，疑似没有以 `assets/templates/main.tex` 为基座: "
            + "、".join(missing)
        )

    return write_report(not errors, "check_template_adherence", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
