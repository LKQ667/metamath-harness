#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check AI figure prompt path layout in the paper."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report
from ai_prompt_common import PROMPT_PATH_RE
import re
ABS_RE = re.compile(r"([A-Za-z]:\\|/[Uu]sers/|/ho[m]e/)")
MAX_PROMPT_LINE = 96


def strip_comment(line: str) -> str:
    return re.split(r"(?<!\\)%", line, maxsplit=1)[0]


def main() -> int:
    parser = project_arg("检查 AI 绘图提示词路径的正文排版是否稳定。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_ai_prompt_layout", errors, args.output)

    for line_no, raw in enumerate(read_text(tex_path).splitlines(), 1):
        line = strip_comment(raw)
        refs = PROMPT_PATH_RE.findall(line)
        if not refs:
            continue
        if ABS_RE.search(line):
            errors.append(f"论文第 {line_no} 行 AI 提示词路径附近存在绝对路径。")
        if len(refs) > 1:
            errors.append(f"论文第 {line_no} 行同时出现 {len(refs)} 个 AI 提示词路径；应每行只显示 1 个相对路径。")
        if len(line.strip()) > MAX_PROMPT_LINE:
            errors.append(f"论文第 {line_no} 行 AI 提示词路径行过长；应使用独立小段或换行排版。")

    return write_report(not errors, "check_ai_prompt_layout", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
