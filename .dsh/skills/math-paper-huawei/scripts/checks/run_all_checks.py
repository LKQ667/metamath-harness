#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""兼容入口：运行 math-paper-huawei step5 全量回归。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gate_registry import all_check_names


CHECKS = all_check_names()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="运行 math-paper-huawei step5 全量回归")
    parser.add_argument("--project", required=True, help="数学建模项目根目录")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    proc = subprocess.run(
        [
            sys.executable,
            str(base / "run_stage_gate.py"),
            "--project",
            str(Path(args.project).resolve()),
            "--stage",
            "step5",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(proc.stdout, end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
