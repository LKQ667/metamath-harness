#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证 select_template 契约：只返回注册表内可执行模板；禁用+无等价时明确待拆分。"""

from __future__ import annotations

import runpy
import sys
import tempfile
import unittest
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "plotting" / "template_registry.py"


def load_module():
    spec_path = str(REGISTRY)
    namespace: dict = {}
    with open(spec_path, encoding="utf-8") as handle:
        exec(compile(handle.read(), spec_path, "exec"), namespace)
    return namespace


class SelectTemplateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_module()

    def test_disabled_multi_panel_without_equivalent_requests_manual_split(self):
        # S07/R04：不返回未注册的伪模板 ID
        result = self.registry["select_template"]("network_resilience_template", "禁用子图")
        self.assertFalse(result["ok"])
        self.assertTrue(result["needs_manual_split"])
        self.assertEqual(result["templates"], [])
        self.assertIn("需要按原图语义拆分", result["reason"])
        self.assertNotIn("#panel", result["reason"])
        self.assertNotIn("#panel", str(result["templates"]))

    def test_disabled_with_equivalent_returns_registered_template(self):
        result = self.registry["select_template"]("temporal_bursty_activity_template", "禁用子图")
        self.assertTrue(result["ok"], result["reason"])
        self.assertEqual(result["templates"], ["trend_confidence_template"])
        for template_id in result["templates"]:
            self.assertIn(template_id, self.registry["TEMPLATE_REGISTRY"])

    def test_single_panel_and_non_disabled_return_registered_self(self):
        for template_id, policy in (
            ("trend_confidence_template", "禁用子图"),
            ("network_resilience_template", "默认（模型自行判断）"),
            ("multi_panel_hero_support_template", "少用子图"),
        ):
            with self.subTest(template_id=template_id, policy=policy):
                result = self.registry["select_template"](template_id, policy)
                self.assertTrue(result["ok"], result["reason"])
                self.assertEqual(result["templates"], [template_id])
                self.assertIn(template_id, self.registry["TEMPLATE_REGISTRY"])

    def test_selection_result_runs_actual_generation_path(self):
        # 消费选择结果运行真实生成路径：等价单图模板必须可执行出图（合成样例）
        result = self.registry["select_template"]("temporal_bursty_activity_template", "禁用子图")
        template_id = result["templates"][0]
        root = Path(REGISTRY).resolve().parents[2]
        template_file = root / "assets" / "templates" / "py-figures" / f"{template_id}.py"
        self.assertTrue(template_file.exists(), f"选择结果指向的模板必须可执行: {template_file}")
        with tempfile.TemporaryDirectory() as tmp:
            sys.argv = [str(template_file), "--output-dir", tmp]
            try:
                runpy.run_path(str(template_file), run_name="__main__")
            except SystemExit:
                pass
            produced = list(Path(tmp).glob("*"))
            self.assertTrue(produced, "等价单图模板应产出真实图像文件")


if __name__ == "__main__":
    unittest.main()
