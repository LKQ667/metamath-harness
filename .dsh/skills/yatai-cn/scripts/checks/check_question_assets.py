#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check each question folder has result.md and traceable question figures."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


SCRIPT_SUFFIXES = {".py", ".ipynb", ".m"}
FIGURE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}
REQUIRED_RESULT_SECTIONS = [
    "问题目标",
    "输入数据",
    "核心假设",
    "模型思路",
    "关键公式通俗解释",
    "运行命令",
    "输出文件",
    "核心数值结果",
    "图表清单",
    "结果解释",
    "局限与下一问衔接",
]


def is_question_dir(path: Path) -> bool:
    return path.is_dir() and re.fullmatch(r"Q\d+", path.name, flags=re.IGNORECASE) is not None


def has_script(path: Path) -> bool:
    return any(p.is_file() and p.suffix.lower() in SCRIPT_SUFFIXES for p in path.rglob("*"))


def question_figures(path: Path) -> list[Path]:
    fig_dir = path / "figures"
    if not fig_dir.exists():
        return []
    return [p for p in fig_dir.rglob("*") if p.is_file() and p.suffix.lower() in FIGURE_SUFFIXES]


def has_no_figure_exemption(text: str) -> bool:
    return "不出图理由" in text and "可复现结果来源" in text


def main() -> int:
    parser = project_arg("检查每个 Q 目录的 result.md、脚本和本问图片。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    q_dirs = sorted([p for p in project.iterdir() if is_question_dir(p)], key=lambda p: int(p.name[1:]))

    if not q_dirs:
        errors.append("缺少 Q1/Q2 等问题目录。")

    for q_dir in q_dirs:
        result_path = q_dir / "result.md"
        readme_path = q_dir / "README.md"
        figures_dir = q_dir / "figures"
        if not readme_path.exists():
            errors.append(f"{q_dir.name} 缺少 README.md。")
        if not has_script(q_dir):
            errors.append(f"{q_dir.name} 缺少本问主脚本或包装脚本。")
        if not result_path.exists():
            errors.append(f"{q_dir.name} 缺少 result.md，无法完整交接本问信息。")
            result_text = ""
        else:
            result_text = read_text(result_path)
            missing = [section for section in REQUIRED_RESULT_SECTIONS if section not in result_text]
            if missing:
                errors.append(f"{q_dir.name}/result.md 缺少栏目: " + "、".join(missing))
        if not figures_dir.exists():
            errors.append(f"{q_dir.name} 缺少 figures/ 子目录。")
        figures = question_figures(q_dir)
        if not figures and not has_no_figure_exemption(result_text):
            errors.append(f"{q_dir.name}/figures/ 缺少本问图片；若确实不出图，result.md 必须写明“不出图理由”和“可复现结果来源”。")

    return write_report(not errors, "check_question_assets", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
