#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that the paper uses the APMCM Chinese-track template style."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report


REQUIRED_TEMPLATE_MARKERS = [
    "\\titlefont",
    "\\sectiontitlefont",
    "\\keywordfont",
    "\\appendixtitlefont",
]


def main() -> int:
    parser = project_arg("检查 main.tex 是否偏离 yatai-cn / APMCM 中文赛模板。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    tex_path = project / "论文" / "main.tex"

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_template_adherence", errors, args.output)

    text = read_text(tex_path)
    if "\\tableofcontents" in text:
        errors.append("APMCM 中文赛论文默认不生成目录，`main.tex` 中禁止出现 `\\tableofcontents`。")
    if (project / "论文" / "main.toc").exists():
        errors.append("发现 `论文/main.toc`，说明生成过目录页；最终模板不得保留目录产物。")
    if "\\maketitle" in text:
        errors.append("禁止改用普通 article 的 `\\maketitle`，必须复用技能模板标题区。")
    if "\\begin{abstract}" in text or "\\end{abstract}" in text:
        errors.append("禁止改用普通 `abstract` 环境，必须复用技能模板的摘要落版结构。")

    missing = [marker for marker in REQUIRED_TEMPLATE_MARKERS if marker not in text]
    if missing:
        errors.append(
            "缺少技能内置模板关键样式命令，疑似没有以 `assets/templates/main.tex` 为基座: "
            + "、".join(missing)
        )

    return write_report(not errors, "check_template_adherence", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
