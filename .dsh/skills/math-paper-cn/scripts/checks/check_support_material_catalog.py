#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check appendix support material catalog does not contain paths."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


PATH_RE = re.compile(
    r"([A-Za-z]:\\|\\\\|/|\\|(?:^|[\s{（(])(?:\.\.?/|\.\.?\\)|"
    r"(?:Q\d+|scripts|data|results|figures|assets|references|论文|摘要|文献|赛题|数据预处理|灵敏度分析|检查结果)\s*[/\\])"
)
SEE_DIR_RE = re.compile(r"见\s*(?:[\w\u4e00-\u9fff-]+\s*)?(?:目录|文件夹|路径|[/\\]|scripts|data|Q\d+)", re.I)


def catalog_block(text: str) -> tuple[str, int] | None:
    start = text.find("支撑材料文件目录")
    if start == -1:
        return None
    end = text.find("\\section{附录代码文件}", start)
    if end == -1:
        end = text.find("\\subsection", start)
    if end == -1:
        end = len(text)
    start_line = text[:start].count("\n") + 1
    return text[start:end], start_line


def strip_tex_commands(line: str) -> str:
    line = re.sub(r"(?<!\\)%.*$", "", line)
    line = re.sub(r"\\(?:textbf|emph|AppendixCodeName)\{([^{}]*)\}", r"\1", line)
    line = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", " ", line)
    line = line.replace("{", " ").replace("}", " ")
    return line


def main() -> int:
    parser = project_arg("检查支撑材料文件目录禁止路径写法")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_support_material_catalog", errors, args.output)

    block_info = catalog_block(read_text(tex_path))
    if block_info is None:
        errors.append("未找到附录“支撑材料文件目录”。")
        return write_report(False, "check_support_material_catalog", errors, args.output)

    block, start_line = block_info
    for offset, raw in enumerate(block.splitlines(), 0):
        line_no = start_line + offset
        visible = strip_tex_commands(raw)
        if not visible.strip():
            continue
        if PATH_RE.search(visible):
            errors.append(f"支撑材料文件目录第 {line_no} 行存在路径或目录写法；只允许代码名称和重要 Excel 结果名称。")
        if SEE_DIR_RE.search(visible):
            errors.append(f"支撑材料文件目录第 {line_no} 行存在“见某目录/文件夹/路径”写法。")

    return write_report(not errors, "check_support_material_catalog", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
