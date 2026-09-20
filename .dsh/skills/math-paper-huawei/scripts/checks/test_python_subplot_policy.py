#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_python_subplot_policy.py")


def python_item(source: str, template_id: str, panel_count) -> dict:
    item = {
        "generator": "python",
        "source": source,
        "template_id": template_id,
        "chart_family": "line_band",
        "paper_ready": True,
    }
    if panel_count is not None:
        item["panel_count"] = panel_count
    return item


class PythonSubplotPolicyTests(unittest.TestCase):
    def run_gate(self, policy: str, items: list[dict], sources: dict | None = None, notes: str = "") -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            state = {"subplot_policy": policy}
            if notes:
                state["user_notes"] = notes
            (project / "项目状态.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            (project / "figures" / "manifest.json").write_text(
                json.dumps({"subplot_policy": policy, "items": items}, ensure_ascii=False), encoding="utf-8"
            )
            for name, code in (sources or {}).items():
                (project / name).write_text(code, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            return json.loads(proc.stdout)

    def test_single_panel_passes_in_all_modes(self):
        items = [python_item("Q1/plot1.py", "trend_confidence_template", 1)]
        for policy in ("默认（模型自行判断）", "少用子图", "禁用子图"):
            with self.subTest(policy=policy):
                report = self.run_gate(policy, items, {"Q1/plot1.py": "fig, ax = plt.subplots()\n"})
                self.assertTrue(report["ok"], report["errors"])

    def test_sparse_allows_four_multi_panel(self):
        items = [python_item(f"Q1/plot{i}.py", "multi_panel_hero_support_template", 4) for i in range(1, 5)]
        sources = {f"Q1/plot{i}.py": "fig, axes = compose_multi_panel('two_by_two')\n" for i in range(1, 5)}
        report = self.run_gate("少用子图", items, sources)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(len(report["details"]["multi_panel"]), 4)

    def test_sparse_rejects_five_multi_panel(self):
        items = [python_item(f"Q1/plot{i}.py", "multi_panel_hero_support_template", 4) for i in range(1, 6)]
        sources = {f"Q1/plot{i}.py": "fig, axes = compose_multi_panel('two_by_two')\n" for i in range(1, 6)}
        report = self.run_gate("少用子图", items, sources)
        self.assertFalse(report["ok"])
        self.assertIn("最多 4 张", report["errors"][0])

    def test_sparse_negation_in_notes_does_not_relax(self):
        # S02：否定性补充要求不是放宽许可
        items = [python_item(f"Q1/plot{i}.py", "multi_panel_hero_support_template", 4) for i in range(1, 6)]
        sources = {f"Q1/plot{i}.py": "fig, axes = compose_multi_panel('two_by_two')\n" for i in range(1, 6)}
        report = self.run_gate("少用子图", items, sources, notes="少用子图，不允许放宽上限")
        self.assertFalse(report["ok"])
        self.assertTrue(any("最多 4 张" in error for error in report["errors"]))

    def run_gate_with_state(self, policy: str, items: list[dict], sources: dict | None = None, state_extra: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            state = {"subplot_policy": policy}
            state.update(state_extra or {})
            (project / "项目状态.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            (project / "figures" / "manifest.json").write_text(
                json.dumps({"subplot_policy": policy, "items": items}, ensure_ascii=False), encoding="utf-8"
            )
            for name, code in (sources or {}).items():
                (project / name).write_text(code, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            return json.loads(proc.stdout)

    def test_sparse_explicit_override_caps_at_exact_integer(self):
        # S03：明确限额 8 张，实际 9 张失败；8 张通过
        items = [python_item(f"Q1/plot{i}.py", "multi_panel_hero_support_template", 4) for i in range(1, 10)]
        sources = {f"Q1/plot{i}.py": "fig, axes = compose_multi_panel('two_by_two')\n" for i in range(1, 10)}
        state = {"subplot_sparse_max": 8, "subplot_sparse_override_request": "经确认本期允许多面板最多 8 张"}
        report = self.run_gate_with_state("少用子图", items, sources, state)
        self.assertFalse(report["ok"])
        self.assertTrue(any("最多 8 张" in error for error in report["errors"]))
        report_ok = self.run_gate_with_state("少用子图", items[:8], sources, state)
        self.assertTrue(report_ok["ok"], report_ok["errors"])
        self.assertEqual(report_ok["details"]["sparse_limit"], 4)

    def test_sparse_override_requires_both_fields(self):
        items = [python_item("Q1/plot1.py", "multi_panel_hero_support_template", 4)]
        report = self.run_gate_with_state("少用子图", items, {"Q1/plot1.py": "fig, axes = compose_multi_panel('x')\n"},
                                          {"subplot_sparse_max": 8})
        self.assertFalse(report["ok"])
        self.assertTrue(any("配置不完整" in error for error in report["errors"]))
        report_empty = self.run_gate_with_state("少用子图", items, {"Q1/plot1.py": "fig, axes = compose_multi_panel('x')\n"},
                                                {"subplot_sparse_max": None, "subplot_sparse_override_request": ""})
        self.assertFalse(report_empty["ok"])

    def test_sparse_zero_override_bans_multi_panel(self):
        items = [python_item("Q1/plot1.py", "multi_panel_hero_support_template", 4)]
        state = {"subplot_sparse_max": 0, "subplot_sparse_override_request": "本期完全不要多面板"}
        report = self.run_gate_with_state("少用子图", items, {"Q1/plot1.py": "fig, axes = compose_multi_panel('x')\n"}, state)
        self.assertFalse(report["ok"])
        self.assertTrue(any("最多 0 张" in error for error in report["errors"]))

    def test_disabled_ignores_sparse_override(self):
        # S08：禁用子图时覆盖值不解除限制
        items = [python_item("Q1/plot1.py", "network_resilience_template", 3)]
        state = {"subplot_sparse_max": 8, "subplot_sparse_override_request": "允许多面板"}
        report = self.run_gate_with_state("禁用子图", items, {"Q1/plot1.py": "fig, axes = compose_multi_panel('x')\n"}, state)
        self.assertFalse(report["ok"])
        self.assertTrue(any("panel_count" in error for error in report["errors"]))

    def test_default_stage_without_argument_reports_step3_scope(self):
        items = [python_item("Q1/plot1.py", "trend_confidence_template", 1)]
        report = self.run_gate("默认", items, {"Q1/plot1.py": "fig, ax = plt.subplots()\n"})
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["stage"], "step3")
        self.assertEqual(report["details"]["stage_source"], "default_step3")

    def test_explicit_stage_step3_same_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            (project / "项目状态.json").write_text(json.dumps({"subplot_policy": "默认（模型自行判断）"}, ensure_ascii=False), encoding="utf-8")
            (project / "figures" / "manifest.json").write_text(
                json.dumps({"items": [python_item("Q1/plot1.py", "trend_confidence_template", 1)]}, ensure_ascii=False), encoding="utf-8"
            )
            (project / "Q1" / "plot1.py").write_text("fig, ax = plt.subplots()\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project), "--stage", "step3"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            report = json.loads(proc.stdout)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["details"]["stage_source"], "explicit")

    def test_disabled_rejects_two_panel(self):
        items = [python_item("Q1/plot1.py", "network_resilience_template", 3)]
        report = self.run_gate("禁用子图", items, {"Q1/plot1.py": "fig, axes = compose_multi_panel('single_row_with_legend')\n"})
        self.assertFalse(report["ok"])
        self.assertTrue(any("panel_count" in error for error in report["errors"]))
        self.assertTrue(any("compose_multi_panel" in error for error in report["errors"]))

    def test_disabled_ignores_uncalled_helper_and_unrelated_draft(self):
        # S04/R02：合法单图 + 未调用的多面板辅助函数 + 无关草稿不造成失败
        items = [python_item("Q1/plot1.py", "trend_confidence_template", 1)]
        sources = {
            "Q1/plot1.py": (
                "fig, ax = plt.subplots()\n"
                "ax.plot([1, 2], [3, 4])\n"
                "def helper():\n"
                "    fig, axes = compose_multi_panel('two_by_two')\n"
                "    return axes\n"
            ),
            "Q1/unused.py": "def helper():\n    fig, axes = compose_multi_panel('two_by_two')\n    return axes\n",
            "Q1/draft_old.py": "import matplotlib.pyplot as plt\nplt.subplots(2, 2)\n",
        }
        report = self.run_gate("禁用子图", items, sources)
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(any("未调用定义 helper" in item["reason"] for item in report["details"]["review_items"]))

    def test_disabled_flags_positional_and_inset_calls(self):
        # S05/R03：位置参数 2×2、add_subplot(221)、inset 都识别为实际多面板
        items = [python_item("Q1/plot1.py", "trend_confidence_template", 1)]
        for code, call in (
            ("import matplotlib.pyplot as plt\nfig, axes = plt.subplots(2, 2)\n", "subplots(2, 2)"),
            ("fig = plt.figure()\nax = fig.add_subplot(221)\n", "add_subplot(221)"),
            ("fig = plt.figure()\nax = fig.add_subplot(2, 2, 1)\n", "add_subplot(2, 2,"),
            ("fig, ax = plt.subplots()\nax.inset_axes([0.6, 0.6, 0.3, 0.3])\n", "inset_axes"),
        ):
            with self.subTest(call=call):
                report = self.run_gate("禁用子图", items, {"Q1/plot1.py": code})
                self.assertFalse(report["ok"])
                self.assertTrue(any(call in error for error in report["errors"]))

    def test_disabled_allows_single_panel_auxiliary_axes(self):
        # S06：colorbar/legend/同域 twinx 不因额外 Axes 误伤
        items = [python_item("Q1/plot1.py", "spatial_contour_flow_template", 1)]
        code = (
            "import matplotlib.pyplot as plt\n"
            "fig, ax = plt.subplots()\n"
            "ax.plot([1, 2], [3, 4], label='curve')\n"
            "ax.legend()\n"
            "ax2 = ax.twinx()\n"
            "ax2.plot([1, 2], [5, 6])\n"
            "fig.colorbar(ax.collections[0] if ax.collections else None, ax=ax)\n"
        )
        report = self.run_gate("禁用子图", items, {"Q1/plot1.py": code})
        self.assertTrue(report["ok"], report["errors"])

    def test_disabled_scans_only_manifest_sources(self):
        # R02：扫描范围限定为 manifest 入文图 source，不再遍历全项目
        items = [python_item("Q1/plot1.py", "trend_confidence_template", 1)]
        sources = {"Q1/plot1.py": "fig, ax = plt.subplots()\n", "Q1/hidden_draft.py": "fig, axes = compose_multi_panel('x')\n"}
        report = self.run_gate("禁用子图", items, sources)
        self.assertTrue(report["ok"], report["errors"])

    def test_default_does_not_cap_multi_panel(self):
        items = [python_item(f"Q1/plot{i}.py", "multi_panel_hero_support_template", 4) for i in range(1, 8)]
        sources = {f"Q1/plot{i}.py": "fig, axes = compose_multi_panel('two_by_two')\n" for i in range(1, 8)}
        report = self.run_gate("默认（模型自行判断）", items, sources)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(len(report["details"]["multi_panel"]), 7)

    def test_panel_count_mismatch_fails(self):
        items = [python_item("Q1/plot1.py", "trend_confidence_template", 2)]
        report = self.run_gate("默认", items, {"Q1/plot1.py": "fig, ax = plt.subplots()\n"})
        self.assertFalse(report["ok"])
        self.assertIn("panel_count 与模板语义不一致", report["errors"][0])

    def test_missing_panel_count_fails(self):
        items = [python_item("Q1/plot1.py", "trend_confidence_template", None)]
        report = self.run_gate("默认", items, {"Q1/plot1.py": "fig, ax = plt.subplots()\n"})
        self.assertFalse(report["ok"])
        self.assertIn("缺少整数 panel_count", report["errors"][0])

    def test_unknown_template_fails(self):
        items = [python_item("Q1/plot1.py", "自造模板", 1)]
        report = self.run_gate("默认", items, {"Q1/plot1.py": "fig, ax = plt.subplots()\n"})
        self.assertFalse(report["ok"])
        self.assertIn("不在内置模板注册表中", report["errors"][0])

    def test_policy_mismatch_between_state_and_manifest_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            (project / "项目状态.json").write_text(json.dumps({"subplot_policy": "禁用子图"}, ensure_ascii=False), encoding="utf-8")
            (project / "figures" / "manifest.json").write_text(
                json.dumps({"subplot_policy": "少用子图", "items": []}, ensure_ascii=False), encoding="utf-8"
            )
            (project / "Q1" / "plot1.py").write_text("fig, ax = plt.subplots()\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            report = json.loads(proc.stdout)
            self.assertFalse(report["ok"])
            self.assertIn("子图策略不一致", report["errors"][0])

    def test_legacy_card_without_policy_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            (project / "figures" / "manifest.json").write_text(
                json.dumps({"items": [python_item("Q1/plot1.py", "trend_confidence_template", 1)]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (project / "Q1" / "plot1.py").write_text("fig, ax = plt.subplots()\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            report = json.loads(proc.stdout)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["details"]["policy"], "默认（模型自行判断）")


if __name__ == "__main__":
    unittest.main()
