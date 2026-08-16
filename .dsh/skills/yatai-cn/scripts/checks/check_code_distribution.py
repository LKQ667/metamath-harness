#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that code and results are distributed into question folders."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, write_report


Q_DIR_PREFIXES = ("Q", "q")
SCRIPT_SUFFIXES = {".py", ".ipynb", ".m"}
EVIDENCE_SUFFIXES = {".md", ".json", ".csv", ".xlsx", ".xls"}


def is_question_dir(path: Path) -> bool:
    name = path.name
    if not name.startswith(Q_DIR_PREFIXES):
        return False
    tail = name[1:]
    return bool(tail) and tail.isdigit()


def has_question_evidence(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix in SCRIPT_SUFFIXES or suffix in EVIDENCE_SUFFIXES:
            return True
    return False


def main() -> int:
    parser = project_arg("检查 scripts/ 是否过度集中，并要求各 Q 目录保留本问链路。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []

    q_dirs = sorted([p for p in project.iterdir() if p.is_dir() and is_question_dir(p)], key=lambda p: p.name)
    scripts_dir = project / "scripts"
    central_scripts = sorted(scripts_dir.glob("*.py")) if scripts_dir.exists() else []

    if not q_dirs:
        errors.append("缺少 Q1/Q2 等问题目录，无法追溯逐问模型、脚本和结果。")
    else:
        missing = [p.name for p in q_dirs if not has_question_evidence(p)]
        if missing:
            errors.append(
                "以下问题目录缺少本问主脚本、包装脚本、模型说明或结果文件: "
                + "、".join(missing)
            )

    if central_scripts and q_dirs:
        missing_count = sum(1 for p in q_dirs if not has_question_evidence(p))
        if missing_count:
            script_names = "、".join(p.name for p in central_scripts[:8])
            errors.append(
                "`scripts/` 可保留共享工具和总控脚本，但当前代码/结果链路过度集中；"
                f"已发现集中脚本 {script_names}，仍需在对应 Q 目录保留本问主脚本或结果说明。"
            )

    return write_report(not errors, "check_code_distribution", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
