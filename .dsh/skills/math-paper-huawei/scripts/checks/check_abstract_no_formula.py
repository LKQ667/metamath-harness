#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
from pathlib import Path
from common import iter_project_files, project_arg, read_text, write_report


FORMULA_PATTERNS = [r"\$[^$]+\$", r"\\begin\{equation\}", r"\\\[", r"\\\(", r"\\frac", r"\\sum", r"\\int"]


def abstract_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for m in re.finditer(r"(摘要.*?)(关键词|\\section\{|一、|##)", text, flags=re.S):
        blocks.append(m.group(1))
    return blocks


def main() -> int:
    parser = project_arg("检查摘要区域禁止公式")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    files = iter_project_files(project, (".tex", ".md"))
    main_tex = project / "论文" / "main.tex"
    if main_tex.exists():
        main_text = read_text(main_tex)
        if "\\documentclass[bwprint]{gmcmthesis}" in main_text or "\\documentclass{gmcmthesis}" in main_text:
            return write_report(
                True,
                "check_abstract_no_formula",
                [],
                args.output,
                {"profile": "huawei", "note": "华为杯不启用国赛摘要禁公式硬门，摘要允许必要符号。"},
            )
    found = False
    for path in files:
        for block in abstract_blocks(read_text(path)):
            found = True
            for pattern in FORMULA_PATTERNS:
                if re.search(pattern, block):
                    errors.append(f"{path} 摘要含公式或复杂符号: {pattern}")
    if not found:
        errors.append("未找到摘要区域")
    return write_report(not errors, "check_abstract_no_formula", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
