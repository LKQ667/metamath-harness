#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check appendix support material catalog only contains allowed deliverables."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


PATH_RE = re.compile(
    r"([A-Za-z]:\\|\\\\|/|\\|(?:^|[\s{（(])(?:\.\.?/|\.\.?\\)|"
    r"(?:Q\d+|scripts|data|results|figures|assets|references|论文|摘要|文献|赛题|数据预处理|灵敏度分析|检查结果)\s*[/\\])"
)
SEE_DIR_RE = re.compile(r"见\s*(?:[\w\u4e00-\u9fff-]+\s*)?(?:目录|文件夹|路径|[/\\]|scripts|data|Q\d+)", re.I)
BAD_HEADER_RE = re.compile(r"(文件\s*/\s*目录|位置|路径)")
FILENAME_RE = re.compile(r"[\w\u4e00-\u9fff.-]+\.(?:py|ipynb|m|xlsx|xls|csv|json|md|pdf|png|jpg|jpeg|svg)", re.I)
RESULT_SUFFIXES = {".xlsx", ".xls", ".csv"}
CODE_SUFFIXES = {".py", ".ipynb", ".m"}
HARD_FORBIDDEN_STEMS = (
    "buildproject",
    "run_pipeline",
    "pipeline",
    "main",
    "finalresults",
    "final_results",
    "manifest",
    "readme",
    "agent",
    "source_map",
    "python_flowchart",
    "generate_flowchart",
    "generate_flowcharts",
    "run_all_checks",
)
FORBIDDEN_SUFFIXES = {".json", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".svg"}


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


def allowed_result_names(project: Path) -> set[str]:
    allowlist = project / "检查结果" / "题目要求结果清单.md"
    if not allowlist.exists():
        return set()
    text = read_text(allowlist)
    return {item.lower() for item in FILENAME_RE.findall(text) if Path(item).suffix.lower() in RESULT_SUFFIXES}


def is_allowed_code(name: str) -> bool:
    stem = Path(name).stem.lower()
    compact = stem.replace("-", "_")
    if re.search(r"(^|_)q[1-4]($|_|\D)", compact):
        return True
    if any(token in compact for token in ("preprocess", "preprocessing", "eda", "clean")):
        return True
    if "数据预处理" in stem:
        return True
    if any(token in compact for token in ("sensitivity", "sensibility")):
        return True
    if "灵敏度" in stem:
        return True
    return False


def check_filename(name: str, allowed_results: set[str], line_no: int) -> list[str]:
    errors: list[str] = []
    path = Path(name)
    suffix = path.suffix.lower()
    stem = path.stem.lower()
    lowered = name.lower()
    if any(token in stem for token in HARD_FORBIDDEN_STEMS):
        errors.append(f"支撑材料文件目录第 {line_no} 行包含禁止放置的文件: {name}")
    if suffix in CODE_SUFFIXES and not is_allowed_code(name):
        errors.append(f"支撑材料文件目录第 {line_no} 行代码文件不属于数据预处理、灵敏度分析或 Q1-Q4: {name}")
    elif suffix in RESULT_SUFFIXES and lowered not in allowed_results:
        errors.append(f"支撑材料文件目录第 {line_no} 行结果文件未在题目要求结果清单中放行: {name}")
    elif suffix in FORBIDDEN_SUFFIXES:
        errors.append(f"支撑材料文件目录第 {line_no} 行包含禁止放置的非代码/非题目结果文件: {name}")
    elif suffix and suffix not in CODE_SUFFIXES and suffix not in RESULT_SUFFIXES and suffix not in FORBIDDEN_SUFFIXES:
        errors.append(f"支撑材料文件目录第 {line_no} 行包含未知类型文件: {name}")
    return errors


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
    allowed_results = allowed_result_names(project)
    for offset, raw in enumerate(block.splitlines(), 0):
        line_no = start_line + offset
        visible = strip_tex_commands(raw)
        if not visible.strip():
            continue
        if "&" in raw and BAD_HEADER_RE.search(visible):
            errors.append(f"支撑材料文件目录第 {line_no} 行存在诱导写路径的表头或列名；只允许纯文件名和简短说明。")
        if PATH_RE.search(visible):
            errors.append(f"支撑材料文件目录第 {line_no} 行存在路径或目录写法；只允许代码名称和重要 Excel 结果名称。")
        if SEE_DIR_RE.search(visible):
            errors.append(f"支撑材料文件目录第 {line_no} 行存在“见某目录/文件夹/路径”写法。")
        for filename in FILENAME_RE.findall(visible):
            errors.extend(check_filename(filename, allowed_results, line_no))

    return write_report(not errors, "check_support_material_catalog", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
