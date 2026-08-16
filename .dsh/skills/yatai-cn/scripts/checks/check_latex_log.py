#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import project_arg, read_text, write_report


BAD_TOKENS = [
    "! Undefined control sequence",
    "! LaTeX Error",
    "Fatal error",
    "File ended while scanning",
    "Missing character",
    "File `",
    "not found",
    "Rerun to get cross-references right",
]


def main() -> int:
    parser = project_arg("检查 LaTeX log 硬错误")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    logs = list((project / "论文").rglob("*.log")) if (project / "论文").exists() else []
    if not logs:
        errors.append("缺少论文/*.log，无法确认 LaTeX 编译质量")
    for log in logs:
        text = read_text(log)
        for token in BAD_TOKENS:
            if token in text:
                errors.append(f"{log} 包含 LaTeX 风险: {token}")
    return write_report(not errors, "check_latex_log", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
