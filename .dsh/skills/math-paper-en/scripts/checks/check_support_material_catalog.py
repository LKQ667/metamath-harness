#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the Supporting Material Catalog lists bare file names, not paths."""

from __future__ import annotations

import re
from pathlib import Path

from common import APPENDIX_CODE_MARKER, CATALOG_MARKER, project_arg, read_text, write_report


BS = chr(92)
COMMENT = chr(37)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
DRIVE_RE = re.compile(r"[A-Za-z]:")
PATH_TOKENS = (
    "scripts", "data", "results", "figures", "assets", "references", "code", "paper",
    "Q1", "Q2", "Q3", "Q4", "Q5",
    "论文", "摘要", "文献", "赛题", "数据预处理", "灵敏度分析", "检查结果", "手绘图",
)
SEE_DIR_RE = re.compile(r"(?:见|参见).{0,8}(?:目录|文件夹|路径)|(?:see|refer to)\s+(?:the\s+)?(?:folder|directory|path|subfolder)\b", re.I)


def looks_like_path(line: str) -> bool:
    if "/" in line or BS in line:
        return True
    if DRIVE_RE.search(line):
        return True
    return any(token + "/" in line or token + BS in line for token in PATH_TOKENS)


def catalog_block(text: str) -> tuple[str, int] | None:
    start = text.find(CATALOG_MARKER)
    if start == -1:
        return None
    end = text.find(APPENDIX_CODE_MARKER, start)
    if end == -1:
        end = text.find(BS + "subsection", start)
    if end == -1:
        end = len(text)
    return text[start:end], text[:start].count(chr(10)) + 1


def strip_tex_commands(line: str) -> str:
    line = line.split(COMMENT, 1)[0]
    line = line.replace(BS + BS, " ")
    line = line.replace("&", " ")
    line = re.sub(r"\\(?:paperstrong|textbf|emph|AppendixCodeName)\{([^{}]*)\}", lambda m: m.group(1), line)
    line = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", " ", line)
    line = line.replace(BS, " ")
    return line.replace("{", " ").replace("}", " ")


def main() -> int:
    parser = project_arg("检查 Supporting Material Catalog 禁止路径写法且必须英文")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        return write_report(False, "check_support_material_catalog", [f"缺少论文主文件: {tex_path}"], args.output)

    block_info = catalog_block(read_text(tex_path))
    if block_info is None:
        message = "未找到附录 " + CATALOG_MARKER + " 章节。"
        return write_report(False, "check_support_material_catalog", [message], args.output)

    block, start_line = block_info
    for offset, raw in enumerate(block.splitlines(), 0):
        line_no = start_line + offset
        visible = strip_tex_commands(raw)
        if not visible.strip():
            continue
        if looks_like_path(visible):
            errors.append(f"Catalog 第 {line_no} 行存在路径或目录写法；只允许代码名称和重要 Excel 结果名称。")
        if SEE_DIR_RE.search(visible):
            errors.append(f"Catalog 第 {line_no} 行存在见某目录或路径的写法。")
        if CJK_RE.search(visible):
            errors.append(f"Catalog 第 {line_no} 行含中文；附录交付内容必须英文。")

    return write_report(not errors, "check_support_material_catalog", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
