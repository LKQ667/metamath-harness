#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check main.tex has a recorded XeLaTeX compile-and-fix closure."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report


REQUIRED_RECORD_TOKENS = ("编译命令", "修复轮次", "最近一次编译结论")
OK_TOKENS = ("无报错", "无硬错误", "编译通过")
COMMAND_TOKENS = ("xelatex", "XeLaTeX")


def main() -> int:
    parser = project_arg("检查 main.tex 生成后是否完成 XeLaTeX 编译闭环记录。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    paper = project / "论文"
    check_dir = project / "检查结果"
    errors: list[str] = []

    required_files = [
        paper / "main.tex",
        paper / "main.log",
        paper / "main.aux",
        paper / "main.pdf",
        check_dir / "latex_compile_record.md",
    ]
    for path in required_files:
        if not path.exists():
            errors.append(f"缺少 LaTeX 编译闭环产物: {path.relative_to(project)}")

    record = check_dir / "latex_compile_record.md"
    if record.exists():
        text = read_text(record)
        for token in REQUIRED_RECORD_TOKENS:
            if token not in text:
                errors.append(f"latex_compile_record.md 缺少“{token}”。")
        if not any(token in text for token in COMMAND_TOKENS):
            errors.append("latex_compile_record.md 缺少 XeLaTeX 编译命令。")
        if not any(token in text for token in OK_TOKENS):
            errors.append("latex_compile_record.md 缺少最终无报错或编译通过结论。")
        if "TODO" in text.upper() or "待补" in text:
            errors.append("latex_compile_record.md 仍包含待补内容。")

    return write_report(not errors, "check_main_tex_compile_record", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
