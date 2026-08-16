#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
from pathlib import Path
from common import iter_project_files, project_arg, read_text, write_report


ABS_RE = re.compile(r"([A-Za-z]:\\|/[Uu]sers/|/ho[m]e/|C:\\Users\\|F:\\|f:\\)")
PROMPT_PATH_RE = re.compile(r"(手绘图|AI绘图|ai绘图)/[^\s{}]+\.md")


def main() -> int:
    parser = project_arg("检查项目文件中禁止硬编码绝对路径")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    for path in iter_project_files(project, (".py", ".tex", ".md", ".json", ".csv")):
        rel = path.relative_to(project)
        for line_no, line in enumerate(read_text(path).splitlines(), 1):
            normalized = PROMPT_PATH_RE.sub("", line)
            if ABS_RE.search(normalized):
                errors.append(f"{rel}:{line_no} 存在绝对路径")
    return write_report(not errors, "check_no_absolute_paths", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
