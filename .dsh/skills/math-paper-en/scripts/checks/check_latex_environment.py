#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在 step0 快速探测 LaTeX；缺失时延后到首次论文编译前自动安装。"""

from __future__ import annotations

import sys
from pathlib import Path

from common import project_arg, write_report


LATEX_DIR = Path(__file__).resolve().parents[1] / "latex"
sys.path.insert(0, str(LATEX_DIR))

from latex_runtime import discover, sanitized  # noqa: E402


def inspect_environment(project: Path) -> tuple[list[str], dict]:
    """只做本地探测，不访问网络、不创建运行时目录。"""
    toolchain = discover(project)
    if toolchain is None:
        return [], {
            "available": False,
            "deferred_install": True,
            "install_stage": "step4_first_compile",
        }
    return [], sanitized(toolchain)


def main() -> int:
    parser = project_arg("快速探测 LaTeX 环境；缺失时延后安装")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    details: dict = {}
    try:
        errors, details = inspect_environment(project)
    except Exception as exc:
        errors.append(f"LaTeX 环境探测失败: {exc}")
    public_details = {
        "source": details.get("source"),
        "version": details.get("version"),
        "managed": details.get("managed"),
        "fonts": details.get("fonts", []),
        "available": details.get("available", bool(details.get("source"))),
        "deferred_install": details.get("deferred_install", False),
        "install_stage": details.get("install_stage"),
    } if details else {}
    smoke = details.get("smoke_test") if details else None
    if isinstance(smoke, dict):
        public_details["smoke_test"] = {
            key: smoke.get(key)
            for key in ("ok", "pdf_created", "log_created", "aux_created", "template")
        }
    return write_report(
        not errors,
        "check_latex_environment",
        errors,
        args.output,
        details=public_details,
    )


if __name__ == "__main__":
    raise SystemExit(main())
