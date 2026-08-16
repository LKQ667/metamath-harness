#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check result spreadsheets in support catalog are explicitly required by the problem."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


RESULT_FILE_RE = re.compile(r"[\w\u4e00-\u9fff.-]+\.(?:xlsx|xls|csv)", re.I)
REQUIRED_FIELDS = ("题目原文依据", "允许文件名", "对应问题", "是否必须提交", "是否必须输出")


def catalog_block(text: str) -> str:
    start = text.find("支撑材料文件目录")
    if start == -1:
        return ""
    end = text.find("\\section{附录代码文件}", start)
    if end == -1:
        end = text.find("\\subsection", start)
    if end == -1:
        end = len(text)
    return text[start:end]


def main() -> int:
    parser = project_arg("检查支撑材料目录中的结果 Excel/CSV 是否有题目要求清单放行。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    allowlist_path = project / "检查结果" / "题目要求结果清单.md"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_required_result_artifact_allowlist", errors, args.output)

    catalog = catalog_block(read_text(tex_path))
    result_files = sorted({name.lower() for name in RESULT_FILE_RE.findall(catalog)})
    if not result_files:
        return write_report(True, "check_required_result_artifact_allowlist", errors, args.output)

    if not allowlist_path.exists():
        errors.append("支撑材料目录包含结果 Excel/CSV，但缺少 `检查结果/题目要求结果清单.md`。")
        return write_report(False, "check_required_result_artifact_allowlist", errors, args.output)

    allowlist = read_text(allowlist_path)
    if "题目原文依据" not in allowlist or "允许文件名" not in allowlist or "对应问题" not in allowlist:
        errors.append("题目要求结果清单缺少“题目原文依据 / 允许文件名 / 对应问题”字段。")
    if "是否必须提交" not in allowlist and "是否必须输出" not in allowlist:
        errors.append("题目要求结果清单缺少“是否必须提交”或“是否必须输出”字段。")
    allowed_files = {name.lower() for name in RESULT_FILE_RE.findall(allowlist)}
    for filename in result_files:
        if filename not in allowed_files:
            errors.append(f"结果文件未被题目要求结果清单放行: {filename}")
    if "禁止编造" not in allowlist and "不得编造" not in allowlist:
        errors.append("题目要求结果清单缺少禁止编造说明。")

    return write_report(not errors, "check_required_result_artifact_allowlist", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
