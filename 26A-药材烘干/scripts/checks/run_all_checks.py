#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""由 math-paper-cn 自动生成；不要改写或复制门禁逻辑。"""
import hashlib
from pathlib import Path
import subprocess
import sys

EXPECTED_SHA256 = '55e9b62a877bbe9f52c2612a94071298982eeaf58f81d4ca16f8b3484acf2b87'
DEFAULT_ARGS = ['--stage', 'step5']

candidates = (
    Path.home() / '.codex' / 'skills' / 'math-paper-cn' / 'scripts' / 'checks' / 'run_stage_gate.py',
    Path.home() / '.trae-cn' / 'skills' / 'math-paper-cn' / 'scripts' / 'checks' / 'run_stage_gate.py',
)
RUNNER = next((path for path in candidates if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_SHA256), None)
if RUNNER is None:
    raise SystemExit('门禁源缺失或版本已变化，请从当前 math-paper-cn Skill 重新运行 --init。')
args = [sys.executable, str(RUNNER), *DEFAULT_ARGS, *sys.argv[1:]]
raise SystemExit(subprocess.call(args))
