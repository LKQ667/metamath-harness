#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查论文是否保持华数杯内置模板身份与官方结构。"""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report


REQUIRED_TEMPLATE_MARKERS = [
    "\\documentclass{JXUSTmodeling}",
    "\\suoshuleibie{",
    "\\cansaibianhao{",
    "\\biaoti{",
    "\\keyword{",
    "\\begin{abstract}",
    "AI工具使用声明",
    "\\begin{thebibliography}",
    "\\begin{appendixx}",
    "AI工具使用详情",
]


def main() -> int:
    parser = project_arg("检查 main.tex 是否偏离华数杯内置模板。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    tex_path = project / "论文" / "main.tex"

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_template_adherence", errors, args.output)

    text = read_text(tex_path)
    if "\\tableofcontents" in text:
        errors.append("华数杯内置模板不生成目录，`main.tex` 中禁止出现 `\\tableofcontents`。")
    if (project / "论文" / "main.toc").exists():
        errors.append("发现 `论文/main.toc`，说明生成过目录页；最终模板不得保留目录产物。")
    if "\\maketitle" in text:
        errors.append("禁止改用普通 article 的 `\\maketitle`，必须复用 JXUSTmodeling 首页。")
    if "\\begin{abstract}" not in text or "\\end{abstract}" not in text:
        errors.append("华数杯模板必须使用 JXUSTmodeling 提供的 `abstract` 环境。")

    missing = [marker for marker in REQUIRED_TEMPLATE_MARKERS if marker not in text]
    if missing:
        errors.append(
            "缺少华数杯模板关键结构，疑似没有以 `assets/templates/main.tex` 为基座: "
            + "、".join(missing)
        )

    return write_report(not errors, "check_template_adherence", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
