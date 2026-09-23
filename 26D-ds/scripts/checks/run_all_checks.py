#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""由 math-paper-huawei 自动生成；不要改写或复制门禁逻辑。"""
import hashlib
from pathlib import Path
import subprocess
import sys

EXPECTED_SHA256 = 'd9c01b50b63eeafed93c99fcf89dd863700132b86a2d6284371f4ed0238b7b04'
DEFAULT_ARGS = ['--stage', 'step5']

candidates = (
    Path.home() / '.codex' / 'skills' / 'math-paper-huawei' / 'scripts' / 'checks' / 'run_stage_gate.py',
    Path.home() / '.trae-cn' / 'skills' / 'math-paper-huawei' / 'scripts' / 'checks' / 'run_stage_gate.py',
)
RUNNER = next((path for path in candidates if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_SHA256), None)
if RUNNER is None:
    raise SystemExit('门禁源缺失或版本已变化，请从当前 math-paper-huawei Skill 重新运行 --init。')
args = [sys.executable, str(RUNNER), *DEFAULT_ARGS, *sys.argv[1:]]
raise SystemExit(subprocess.call(args))
