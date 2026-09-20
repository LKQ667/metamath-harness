#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that the paper uses the built-in math-paper-en English template."""

from __future__ import annotations

import re
from pathlib import Path

from common import APPENDIX_CODE_MARKER, CATALOG_MARKER, project_arg, read_text, write_report


REQUIRED_TEMPLATE_MARKERS = (
    "\\titlefont",
    "\\sectiontitlefont",
    "\\keywordfont",
    "\\appendixtitlefont",
    "\\paperstrong",
    "\\label{body:start}",
    "\\label{body:end}",
    "\\label{appendix:start}",
    "\\label{paper:end}",
    "\\begin{thebibliography}",
    "\\begin{appendices}",
)
FORBIDDEN_PACKAGES = ("ctex", "CJK", "xeCJK", "zhnumber", "zhspacing")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
MAX_CJK_LINE_REPORTS = 8


def main() -> int:
    parser = project_arg("检查 main.tex 是否偏离 math-paper-en 英文内置模板。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    tex_path = project / "论文" / "main.tex"

    if not tex_path.exists():
        return write_report(False, "check_template_adherence", [f"缺少论文主文件: {tex_path}"], args.output)

    text = read_text(tex_path)
    if "\\maketitle" in text:
        errors.append("禁止改用普通 article 的 `\\maketitle`，必须复用技能模板的标题区。")
    if "\\begin{abstract}" in text or "\\end{abstract}" in text:
        errors.append("禁止改用普通 `abstract` 环境，必须复用技能模板的 Summary Sheet 结构。")
    for package in FORBIDDEN_PACKAGES:
        pattern = r"\\usepackage(?:\[[^\]]*\])?\{" + re.escape(package) + r"\}"
        if re.search(pattern, text):
            errors.append(f"美赛论文必须全英文，禁止加载中文宏包 `{package}`。")
    if "fontspec" not in text:
        errors.append("缺少 `fontspec`，英文模板必须显式设置英文主字体。")
    if CATALOG_MARKER not in text or APPENDIX_CODE_MARKER not in text:
        errors.append(f"附录必须保留 `{CATALOG_MARKER}` 与 `{APPENDIX_CODE_MARKER}` 结构。")

    reported = 0
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        if CJK_RE.search(stripped):
            errors.append(f"main.tex 第 {line_no} 行含中文字符，美赛交付论文必须全英文。")
            reported += 1
            if reported >= MAX_CJK_LINE_REPORTS:
                errors.append("中文行过多，已截断后续同类报错；请整篇排查并替换为英文。")
                break

    missing = [marker for marker in REQUIRED_TEMPLATE_MARKERS if marker not in text]
    if missing:
        errors.append(
            "缺少技能内置模板关键结构或样式命令，疑似没有以 `assets/templates/main.tex` 为基座: "
            + "、".join(missing)
        )

    return write_report(not errors, "check_template_adherence", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
