#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查论文是否保持华为杯 GMCMthesis 内置模板身份与官方结构。"""

from __future__ import annotations

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
    if "\\tableofcontents" in text or "\\maketoc" in text:
        errors.append("华为杯论文默认不生成目录，`main.tex` 中禁止出现 `\\tableofcontents` 或 `\\maketoc`。")
    if (project / "论文" / "main.toc").exists():
        errors.append("发现 `论文/main.toc`，说明生成过目录页；最终模板不得保留目录产物。")
    if "\\maketitle" not in text:
        errors.append("华为杯封面必须由 GMCMthesis 模板的 `\\maketitle` 生成，不得删除或另造封面。")
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
