#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from check_stage_contract import check_gate_chain, check_step0, check_step1, check_step2, check_step3
from common import repair_hint
from run_stage_gate import file_sha256, fingerprint, initialize_contract


class StageContractTests(unittest.TestCase):
    def create_base(self, project: Path) -> dict:
        for relative, content in {
            "README.md": "项目",
            "AGENT.md": "规则",
            "data/source_map.md": "https://example.com/data",
            "文献/source_map.md": "https://example.com/paper",
            "figures/manifest.json": "{}",
        }.items():
            path = project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return {
            "drawing_mode": "drawio",
            "drawing_mode_locked": True,
            "drawing_mode_confirmed": True,
            "question_count": 1,
            "data_mode": "none",
        }

    def test_step0_accepts_complete_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.create_base(project)
            errors: list[str] = []
            check_step0(project, state, errors)
            self.assertEqual(errors, [])

    def test_step1_accepts_explicit_no_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = self.create_base(project)
            readme = project / "数据预处理" / "README.md"
            readme.parent.mkdir()
            readme.write_text(
                "原始输入\n处理规则\nEDA\n输出\n结论\n无数据依据：赛题为纯理论推导。",
                encoding="utf-8",
            )
            errors: list[str] = []
            check_step1(project, state, errors)
            self.assertEqual(errors, [])

    def test_step2_uses_dynamic_question_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = {"question_count": 2}
            for index in (1, 2):
                readme = project / f"Q{index}" / "README.md"
                readme.parent.mkdir()
                readme.write_text("\n".join(("目标", "输入", "假设", "变量", "公式", "约束", "方法", "验证")), encoding="utf-8")
            errors: list[str] = []
            check_step2(project, state, errors)
            self.assertEqual(errors, [])

    def test_step3_requires_nonempty_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            result = project / "results" / "final_results.json"
            result.parent.mkdir()
            result.write_text(json.dumps({"results": {"value": 1}}), encoding="utf-8")
            errors: list[str] = []
            check_step3(project, errors)
            self.assertEqual(errors, [])

    def test_repair_hint_distinguishes_latex_and_missing_artifact(self) -> None:
        self.assertIn("doctor", repair_hint("LaTeX 编译失败"))
        self.assertIn("必需产物", repair_hint("缺少 README.md"))

    def test_gate_chain_rejects_tampered_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state: dict = {}
            initialize_contract(project, state)
            launcher = project / "scripts" / "checks" / "run_stage_gate.py"
            launcher.write_text("被修改", encoding="utf-8")
            errors: list[str] = []
            check_gate_chain(project, state, "step0", errors)
            self.assertTrue(any("已被修改" in error for error in errors))

    def test_gate_chain_rejects_sparse_previous_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state: dict = {"stages": {}}
            initialize_contract(project, state)
            report = project / "检查结果" / "step0" / "step0_gate.json"
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({"stage": "step0", "ok": True, "checks": []}), encoding="utf-8")
            state["stages"]["step0"] = {
                "status": "passed",
                "input_fingerprint": fingerprint(project, "step0"),
                "report": report.relative_to(project).as_posix(),
                "report_sha256": file_sha256(report),
            }
            errors: list[str] = []
            check_gate_chain(project, state, "step1", errors)
            self.assertTrue(any("检查项不完整" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
