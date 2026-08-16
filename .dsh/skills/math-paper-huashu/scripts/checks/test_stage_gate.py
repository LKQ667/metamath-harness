#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from run_stage_gate import (
    STAGES,
    fingerprint,
    file_sha256,
    initialize_project,
    initialize_contract,
    invalidate_stale,
    migrate_state,
    run_through,
    save_state,
    verify_delivery,
    write_attestation,
)


class StageGateStateTests(unittest.TestCase):
    def test_fingerprint_changes_with_stage_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "README.md").write_text("一", encoding="utf-8")
            before = fingerprint(project, "step0")
            (project / "README.md").write_text("二", encoding="utf-8")
            self.assertNotEqual(before, fingerprint(project, "step0"))

    def test_report_changes_do_not_invalidate_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "README.md").write_text("固定", encoding="utf-8")
            before = fingerprint(project, "step0")
            report = project / "检查结果" / "step0"
            report.mkdir(parents=True)
            (report / "step0_gate.json").write_text("{}", encoding="utf-8")
            self.assertEqual(before, fingerprint(project, "step0"))

    def test_stale_stage_invalidates_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "README.md").write_text("当前", encoding="utf-8")
            state = {
                "stages": {
                    stage: {
                        "status": "passed",
                        "input_fingerprint": fingerprint(project, stage),
                    }
                    for stage in STAGES
                }
            }
            (project / "README.md").write_text("变化", encoding="utf-8")
            self.assertEqual(invalidate_stale(project, state), 0)
            self.assertTrue(all(state["stages"][stage]["status"] == "stale" for stage in STAGES))

    def test_legacy_state_migration_uses_existing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "Q1").mkdir()
            (project / "Q2").mkdir()
            data = project / "data"
            data.mkdir()
            (data / "clean.csv").write_text("x\n1\n", encoding="utf-8")
            state: dict = {}
            migrate_state(project, state)
            self.assertEqual(state["question_count"], 2)
            self.assertEqual(state["data_mode"], "data")

    def test_legacy_state_migration_does_not_guess_drawing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state: dict = {}
            migrate_state(Path(tmp), state)
            self.assertNotIn("drawing_mode", state)

    def test_target_stage_is_always_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "README.md").write_text("固定", encoding="utf-8")
            state = {
                "stages": {
                    "step0": {
                        "status": "passed",
                        "input_fingerprint": fingerprint(project, "step0"),
                    }
                }
            }
            save_state(project, state)
            with (
                patch("run_stage_gate.validate_registry", return_value=[]),
                patch("run_stage_gate.run_one_stage", return_value=True) as run,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(run_through(project, "step0"), 0)
                run.assert_called_once()

    def test_failed_final_recheck_clears_completed_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = {"status": "completed", "stages": {}}
            save_state(project, state)
            with (
                patch("run_stage_gate.validate_registry", return_value=[]),
                patch("run_stage_gate.run_one_stage", return_value=False),
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(run_through(project, "step5"), 1)
            updated = __import__("json").loads((project / "项目状态.json").read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "failed")

    def test_invalid_state_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state_path = project / "项目状态.json"
            state_path.write_text("{broken", encoding="utf-8")
            with patch("run_stage_gate.validate_registry", return_value=[]), redirect_stdout(StringIO()):
                self.assertEqual(run_through(project, "step0"), 2)
            self.assertEqual(state_path.read_text(encoding="utf-8"), "{broken")

    def test_missing_project_returns_usage_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            with redirect_stdout(StringIO()):
                self.assertEqual(run_through(missing, "step0"), 2)

    def test_init_installs_project_local_launchers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(StringIO()):
            project = Path(tmp)
            self.assertEqual(initialize_project(project), 0)
            for name in ("run_stage_gate.py", "run_all_checks.py", "verify_delivery.py"):
                self.assertTrue((project / "scripts" / "checks" / name).is_file())
            state = __import__("json").loads((project / "项目状态.json").read_text(encoding="utf-8"))
            self.assertEqual(state["workflow_version"], 3)
            self.assertEqual(state["gate_contract"]["version"], 3)

    def test_delivery_verification_rejects_missing_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(StringIO()):
            project = Path(tmp)
            self.assertEqual(initialize_project(project), 0)
            ok, errors = verify_delivery(project)
            self.assertFalse(ok)
            self.assertTrue(any("completed" in error for error in errors))

    def test_contract_upgrade_invalidates_passed_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state = {
                "status": "completed",
                "gate_contract": {"version": 1},
                "stages": {stage: {"status": "passed"} for stage in STAGES},
            }
            initialize_contract(project, state)
            self.assertEqual(state["status"], "in_progress")
            self.assertTrue(all(state["stages"][stage]["status"] == "stale" for stage in STAGES))

    def test_delivery_verification_rejects_sparse_forged_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state: dict = {"status": "completed", "stages": {}}
            initialize_contract(project, state)
            for stage in STAGES:
                report = project / "检查结果" / stage / f"{stage}_gate.json"
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(json.dumps({"stage": stage, "ok": True, "checks": []}), encoding="utf-8")
                state["stages"][stage] = {
                    "status": "passed",
                    "input_fingerprint": fingerprint(project, stage),
                    "report": report.relative_to(project).as_posix(),
                    "report_sha256": file_sha256(report),
                }
            save_state(project, state)
            write_attestation(project, state)
            ok, errors = verify_delivery(project)
            self.assertFalse(ok)
            self.assertTrue(any("检查项不完整" in error for error in errors))

    def test_delivery_verification_rejects_report_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            state: dict = {"status": "completed", "stages": {}}
            initialize_contract(project, state)
            for stage in STAGES:
                state["stages"][stage] = {
                    "status": "passed",
                    "input_fingerprint": fingerprint(project, stage),
                    "report": "../outside.json",
                }
            save_state(project, state)
            ok, errors = verify_delivery(project)
            self.assertFalse(ok)
            self.assertTrue(any("路径非法" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
