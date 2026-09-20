#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_python_bar_chart_policy.py")


class PythonBarChartPolicyTests(unittest.TestCase):
    def run_gate(self, policy: str, source: str, exception: dict | None = None, manifest_policy: str | None = None) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            (project / "项目状态.json").write_text(
                json.dumps({"bar_policy": policy}, ensure_ascii=False), encoding="utf-8"
            )
            item = {"generator": "python", "source": "Q1/plot.py", "chart_family": "timeline_interval"}
            if exception is not None:
                item["bar_exception"] = exception
            (project / "figures" / "manifest.json").write_text(
                json.dumps({"bar_policy": manifest_policy or policy, "items": [item]}, ensure_ascii=False), encoding="utf-8"
            )
            (project / "Q1" / "plot.py").write_text(source, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            return json.loads(proc.stdout)

    def test_disabled_rejects_barh_even_for_interval_chart(self):
        report = self.run_gate("禁用", "ax.barh(0, 1, left=2)\n")
        self.assertFalse(report["ok"])
        self.assertEqual(report["details"]["bar_calls"][0]["call"], "barh")

    def test_disabled_accepts_line_segment_interval(self):
        report = self.run_gate("禁用", "ax.hlines(0, 2, 3)\nax.plot([2, 3], [0, 0])\n")
        self.assertTrue(report["ok"])

    def test_sparse_requires_complete_same_source_exception(self):
        denied = self.run_gate("少用", "ax.bar([1], [2])\n")
        self.assertFalse(denied["ok"])
        exception = {
            "necessary": True,
            "category_count_small": True,
            "zero_baseline_required": True,
            "absolute_height_comparison": True,
            "reason": "两个方案必须从零比较绝对值",
        }
        allowed = self.run_gate("少用", "ax.bar([1], [2])\n", exception)
        self.assertTrue(allowed["ok"])

    def test_normal_allows_bar_call(self):
        report = self.run_gate("正常", "df.plot(kind='barh')\n")
        self.assertTrue(report["ok"])
        self.assertEqual(report["details"]["bar_calls"][0]["call"], "plot(kind='barh')")

    def test_disabled_rejects_plotly_bar_class(self):
        report = self.run_gate("禁用", "go.Bar(x=[1], y=[2])\n")
        self.assertFalse(report["ok"])

    def test_disabled_rejects_import_assignment_and_getattr_aliases(self):
        source = "from matplotlib.pyplot import bar as draw\ndraw([1], [2])\nplot = ax.barh\nplot(0, 1)\ngetattr(ax, 'barh')(0, 1)\n"
        report = self.run_gate("禁用", source)
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["details"]["bar_calls"]), 3)

    def test_disabled_rejects_plotly_dictionary_spec(self):
        report = self.run_gate("禁用", "go.Figure(data=[{'type': 'bar'}])\n")
        self.assertFalse(report["ok"])
        self.assertEqual(report["details"]["bar_calls"][0]["call"], "{'type': 'bar'}")

    def test_comments_and_strings_do_not_trigger(self):
        report = self.run_gate("禁用", "# ax.barh(0, 1)\ntext = \"barplot kind='bar'\"\n")
        self.assertTrue(report["ok"])

    def test_state_and_manifest_policy_must_match(self):
        report = self.run_gate("禁用", "ax.hlines(0, 1, 2)\n", manifest_policy="正常")
        self.assertFalse(report["ok"])
        self.assertIn("柱状图策略不一致", report["errors"][0])


if __name__ == "__main__":
    unittest.main()
