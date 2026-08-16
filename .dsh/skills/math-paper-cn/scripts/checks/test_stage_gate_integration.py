#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNNER = Path(__file__).with_name("run_stage_gate.py")


@unittest.skipUnless(shutil.which("xelatex") and shutil.which("latexmk"), "需要现有 XeLaTeX 做无下载集成测试")
class StageGateIntegrationTests(unittest.TestCase):
    def test_step0_gate_records_environment_and_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-paper-stage0-") as tmp:
            project = Path(tmp)
            files = {
                "README.md": "项目说明",
                "AGENT.md": "项目规则",
                "data/source_map.md": "数据名称 | 用途 | 来源类型 | 具体依据\n附件 | 建模 | 官方 | https://example.com/data",
                "文献/source_map.md": "文献 | https://example.com/paper",
                "figures/manifest.json": json.dumps(
                    {
                        "drawing_mode": "drawio",
                        "drawing_mode_locked": True,
                        "items": [],
                    },
                    ensure_ascii=False,
                ),
                "项目状态.json": json.dumps(
                    {
                        "drawing_mode": "drawio",
                        "drawing_mode_locked": True,
                        "drawing_mode_confirmed": True,
                        "question_count": 1,
                        "data_mode": "none",
                    },
                    ensure_ascii=False,
                ),
            }
            for relative, content in files.items():
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(RUNNER), "--project", str(project), "--stage", "step0"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            report_path = project / "检查结果" / "step0" / "step0_gate.json"
            report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else "缺少阶段报告"
            self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + report_text)
            state = json.loads((project / "项目状态.json").read_text(encoding="utf-8"))
            self.assertEqual(state["stages"]["step0"]["status"], "passed")
            self.assertEqual(state["latex_backend"]["source"], "host")
            self.assertEqual(state["latex_backend"]["smoke_test"], {})
            self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
