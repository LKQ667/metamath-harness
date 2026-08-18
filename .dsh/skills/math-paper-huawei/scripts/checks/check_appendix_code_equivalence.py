#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check traceable appendix-code sanitization and execution equivalence."""

from __future__ import annotations

import sys
from pathlib import Path

from common import project_arg, read_text, write_report


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from prepare_appendix_code import ConfigError, file_entries, load_config, prepare  # noqa: E402


def main() -> int:
    parser = project_arg("检查附录净化代码可追溯、可运行且与原代码结果一致")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    try:
        _, config = load_config(project)
        entries = file_entries(project, config)
        tex_path = project / "论文" / "main.tex"
        if not tex_path.exists():
            raise ConfigError(f"缺少论文主文件: {tex_path}")
        tex = read_text(tex_path).replace("\\", "/")
        for entry in entries:
            rel = str(entry["raw"]["appendix"]).replace("\\", "/")
            if rel not in tex:
                errors.append(f"论文附录未引用净化代码文件: {rel}")
        prepare(project, verify_only=True)
    except Exception as exc:
        errors.append(str(exc))
    return write_report(not errors, "check_appendix_code_equivalence", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
