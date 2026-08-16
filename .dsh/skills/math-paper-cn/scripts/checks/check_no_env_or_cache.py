#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import project_arg, write_report


BAD_NAMES = {".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules"}
BAD_SUFFIXES = {".pyc", ".pyo", ".tmp"}


def main() -> int:
    parser = project_arg("检查交付目录中禁止环境、缓存、临时文件")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    for path in project.rglob("*"):
        if path.name in BAD_NAMES:
            errors.append(f"发现禁止目录: {path.relative_to(project)}")
        if path.is_file() and path.suffix.lower() in BAD_SUFFIXES:
            errors.append(f"发现禁止临时/缓存文件: {path.relative_to(project)}")
        if chr(0xFFFD) in path.name:
            errors.append(f"发现疑似乱码文件名: {path.relative_to(project)}")
        if path.is_file() and path.name.lower().startswith(("debug_", "preview")):
            errors.append(f"发现调试或预览文件: {path.relative_to(project)}")
    return write_report(not errors, "check_no_env_or_cache", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
