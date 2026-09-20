#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第七项“Python 图型重复策略”回归用例（C01–C06、D01–D08）。

夹具为合成 manifest/PNG，只用于测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_python_figure_contract.py")
STAGES = ("step0", "step1", "step2", "step3", "step4", "step5")


def data_item(source: str, template_id: str, chart_family: str, panel_count: int = 1, extra: dict | None = None) -> dict:
    stem = Path(source).stem
    item = {
        "generator": "python",
        "source": source,
        "template_id": template_id,
        "chart_family": chart_family,
        "panel_count": panel_count,
        "paper_ready": True,
        "exports": [f"figures/{stem}.pdf", f"figures/{stem}.png", f"figures/{stem}.svg"],
    }
    item.update(extra or {})
    return item


class PythonFigureContractTests(unittest.TestCase):
    def run_gate(self, state: dict | None, items: list[dict], manifest_extra: dict | None = None, stage: str | None = None,
                 tex: str | None = None, files: bool = True) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            if state is not None:
                (project / "项目状态.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            manifest = {"items": items}
            manifest.update(manifest_extra or {})
            (project / "figures" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            for item in items:
                for export in item.get("exports", []):
                    target = project / export
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if files:
                        target.write_bytes(b"stub")
                source = project / item["source"]
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("import matplotlib.pyplot as plt\nfig, ax = plt.subplots()\n", encoding="utf-8")
            if tex is not None:
                (project / "论文").mkdir()
                (project / "论文" / "main.tex").write_text("\\graphicspath{{../}}\n" + tex, encoding="utf-8")
            command = [sys.executable, str(CHECK), "--project", str(project)]
            if stage:
                command.extend(["--stage", stage])
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            return json.loads(proc.stdout)

    # ---- C01 ----
    def test_new_card_default_written_to_state(self):
        # C01：新卡片默认值显式落状态 → 显式默认（少重复），不走兼容分支
        items = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/heat2.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/line1.py", "trend_confidence_template", "line_band"),
                 data_item("Q1/line2.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["mode"], "默认（少重复）")
        self.assertEqual(report["details"]["policy_source"], "explicit_state")
        self.assertEqual(report["details"]["G"], 2)

    def test_legacy_project_both_missing_uses_free(self):
        # C01/C05：双缺字段 → 模型自行分析 + legacy_missing，缺元数据不阻断
        items = [data_item("Q1/custom1.py", "自造模板A", "fusion"),
                 data_item("Q1/custom2.py", "自造模板B", "fusion")]
        report = self.run_gate(None, items)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["mode"], "模型自行分析")
        self.assertEqual(report["details"]["policy_source"], "legacy_missing")
        self.assertIsNone(report["details"]["G"])
        self.assertEqual(len(report["details"]["unknown_types_items"]), 2)

    # ---- C02 ----
    def test_single_place_explicit_policy_is_used(self):
        items = [data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        report = self.run_gate(None, items, {"python_chart_repeat_policy": "禁止重复"})
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["policy_source"], "explicit_manifest")
        self.assertEqual(report["details"]["mode"], "禁止重复")

    def test_conflicting_policy_fails(self):
        items = [data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items, {"python_chart_repeat_policy": "默认（少重复）"})
        self.assertFalse(report["ok"])
        self.assertTrue(any("策略不一致" in error for error in report["errors"]))

    def test_null_or_empty_or_unknown_policy_fails(self):
        items = [data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        for bad in (None, "", "随便"):
            with self.subTest(value=bad):
                report = self.run_gate({"python_chart_repeat_policy": bad}, items)
                self.assertFalse(report["ok"])
                self.assertTrue(any("非法" in error or "配置错误" in error for error in report["errors"]))

    # ---- C03 ----
    def test_step3_without_tex_reports_pending_scope(self):
        items = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap")]
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items)
        self.assertTrue(report["ok"], report["errors"])
        self.assertIn("拟入文", report["details"]["scope"])

    def test_step4_reference_manifest_mismatch_fails(self):
        # C03：step4 有清单/引用不匹配 → 不静默通过
        items = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        tex = "\\documentclass{gmcmthesis}\n\\begin{document}\n\\includegraphics{figures/heat1}\n\\end{document}\n"
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items, stage="step4", tex=tex)
        self.assertFalse(report["ok"])
        self.assertTrue(any("未出现在最终论文引用" in error for error in report["errors"]))

    def test_step4_unregistered_reference_fails(self):
        items = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap")]
        tex = "\\documentclass{gmcmthesis}\n\\begin{document}\n\\includegraphics{figures/ghost}\n\\end{document}\n"
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items, stage="step4", tex=tex)
        self.assertFalse(report["ok"])
        self.assertTrue(any("无法解析为项目内实际文件" in error for error in report["errors"]))

    # ---- C04 ----
    def test_same_source_two_figures_counted_separately(self):
        # C04：同 source 生成两图 → 两个图项分别计数（热图 n=2、折线 n=3 → G=2 默认通过）
        items = [data_item("Q1/make.py", "sensitivity_sobol_heatmap_template", "heatmap",
                           extra={"exports": ["figures/a1.pdf", "figures/a1.png", "figures/a1.svg"]}),
                 data_item("Q1/make.py", "sensitivity_sobol_heatmap_template", "heatmap",
                           extra={"exports": ["figures/a2.pdf", "figures/a2.png", "figures/a2.svg"]}),
                 data_item("Q1/line1.py", "trend_confidence_template", "line_band"),
                 data_item("Q1/line2.py", "trend_confidence_template", "line_band"),
                 data_item("Q1/line3.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["n_by_type"], {"heatmap_2d": 2, "line_2d": 3})
        self.assertEqual(report["details"]["G"], 2)
        # 若按 source 去重，热图会被错误地算成 n=1、G=1；禁止重复模式下应仍失败
        forbid = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertFalse(forbid["ok"])
        self.assertIn("heatmap_2d", forbid["errors"][0])

    def test_shared_export_path_conflicts(self):
        # C04：两图项共用同一导出路径 → 清单冲突
        first = data_item("Q1/one.py", "trend_confidence_template", "line_band")
        second = data_item("Q1/two.py", "trend_confidence_template", "line_band",
                           extra={"exports": first["exports"]})
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, [first, second])
        self.assertFalse(report["ok"])
        self.assertTrue(any("清单冲突" in error for error in report["errors"]))

    # ---- D01/D02/D03/D05 ----
    def test_default_two_repeat_families_pass_and_three_fail(self):
        base = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                data_item("Q1/heat2.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                data_item("Q1/line1.py", "trend_confidence_template", "line_band"),
                data_item("Q1/line2.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, base)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["G"], 2)  # D01
        scatter = [data_item(f"Q1/sc{i}.py", "自造散点", "scatter", extra={"panel_chart_types": [["scatter_2d"]]}) for i in (1, 2)]
        report3 = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, base + scatter)
        self.assertFalse(report3["ok"])  # D02：G=3 默认失败
        self.assertIn("G=3", report3["errors"][0])
        free = self.run_gate({"python_chart_repeat_policy": "模型自行分析",
                              "chart_repeat_reasons": {"scatter_2d": "对比两种聚类散结构", "heatmap_2d": "对比两阶段热图", "line_2d": "对比两条收敛轨迹"}},
                             base + scatter)
        self.assertTrue(free["ok"], free["errors"])  # D02：自行分析可记录理由通过
        free_no_reason = self.run_gate({"python_chart_repeat_policy": "模型自行分析"}, base + scatter)
        self.assertFalse(free_no_reason["ok"])
        self.assertTrue(any("chart_repeat_reasons" in error for error in free_no_reason["errors"]))

    def test_forbid_any_repeat_fails(self):
        # D03：禁止重复，2 张同类型失败
        items = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/heat2.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertFalse(report["ok"])
        self.assertIn("禁止重复", report["errors"][0])

    def test_three_same_type_single_other_is_G1(self):
        # D05：三张同类型、其他类型唯一 → G=1，不擅加每类最多两张
        items = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/heat2.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/heat3.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["G"], 1)

    def test_renaming_template_or_colors_does_not_evade(self):
        # D06：改 template_id/颜色不产生新类型；显式元数据仍按视觉类型归组
        items = [data_item("Q1/red1.py", "自造红版热图", "heatmap", extra={"panel_chart_types": [["heatmap_2d"]]}),
                 data_item("Q1/blue1.py", "自造蓝版热图", "heatmap", extra={"panel_chart_types": [["heatmap_2d"]]}),
                 data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertFalse(report["ok"])
        self.assertIn("heatmap_2d", report["errors"][0])

    def test_composite_figures_line_family_counts_across_families(self):
        # D07：两张复合图顶层 family 不同，但都含折线 → 折线 n=2，禁止重复失败
        items = [data_item("Q1/pareto1.py", "自造权衡", "pareto",
                           extra={"panel_chart_types": [["scatter_2d", "line_2d"]]}),
                 data_item("Q1/net1.py", "自造网络", "network_stack", panel_count=2,
                           extra={"panel_chart_types": [["network_2d"], ["line_2d"]]})]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertFalse(report["ok"])
        self.assertIn("line_2d", report["errors"][0])

    def test_flowchart_and_non_python_not_counted(self):
        # D08：流程图与 Draw.io 图不计入 Python 数据图重复
        flow = data_item("Q1/flow1.py", "python_flowchart_topdown", "flowchart",
                         extra={"panel_chart_types": [["flowchart"]]})
        drawio = {"generator": "drawio", "source": "手绘图/roadmap.drawio", "chart_family": "flowchart",
                  "paper_ready": True, "exports": ["figures/roadmap.pdf"]}
        heats = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap"),
                 data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "figures").mkdir()
            (project / "Q1").mkdir()
            (project / "手绘图").mkdir()
            (project / "项目状态.json").write_text(json.dumps({"python_chart_repeat_policy": "禁止重复"}, ensure_ascii=False), encoding="utf-8")
            (project / "figures" / "manifest.json").write_text(
                json.dumps({"items": [flow, drawio, *heats]}, ensure_ascii=False), encoding="utf-8")
            for item in [flow, drawio, *heats]:
                for export in item.get("exports", []):
                    target = project / export
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b"stub")
                if item.get("generator") == "python":
                    source = project / item["source"]
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text("fig, ax = plt.subplots()\n", encoding="utf-8")
            (project / "手绘图" / "roadmap.drawio").write_text("<xml/>", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            report = json.loads(proc.stdout)
        self.assertTrue(report["ok"], report["errors"])
        self.assertNotIn("flowchart", report["details"]["n_by_type"])
        self.assertEqual(report["details"]["counted_figures"], 2)

    def test_duplicate_reference_of_one_figure_counts_once(self):
        # D04：同一图 PDF/PNG/SVG 导出、重复引用 → 一个图项
        items = [data_item("Q1/heat1.py", "sensitivity_sobol_heatmap_template", "heatmap")]
        tex = ("\\documentclass{gmcmthesis}\n\\begin{document}\n"
               "\\includegraphics{figures/heat1}\n\\includegraphics{figures/heat1.png}\n\\end{document}\n")
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items, stage="step4", tex=tex)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["counted_figures"], 1)

    def test_six_c06_marker_line_only_line_and_overlay_two_types(self):
        # C06：带点折线+置信带只算 line_2d；独立散点叠加才登记第二类型
        items = [data_item("Q1/line1.py", "trend_confidence_template", "line_band"),
                 data_item("Q1/line2.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertFalse(report["ok"])
        self.assertEqual(report["details"]["n_by_type"], {"line_2d": 2})
        overlay = [data_item("Q1/mix1.py", "自造叠加", "overlay", extra={"panel_chart_types": [["line_2d", "scatter_2d"]]}),
                   data_item("Q1/mix2.py", "自造叠加", "overlay", extra={"panel_chart_types": [["line_2d", "scatter_2d"]]})]
        report2 = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, overlay)
        self.assertFalse(report2["ok"])
        self.assertEqual(report2["details"]["n_by_type"], {"line_2d": 2, "scatter_2d": 2})

    def test_replotted_item_without_metadata_fails_in_strict_mode(self):
        # 改绘（chart_family 与注册表不一致）且缺显式元数据：默认模式计数不可完成
        items = [data_item("Q1/custom.py", "trend_confidence_template", "自造新家族"),
                 data_item("Q1/custom2.py", "trend_confidence_template", "自造新家族")]
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items)
        self.assertFalse(report["ok"])
        self.assertTrue(any("计数不可完成" in error for error in report["errors"]))
        legacy = self.run_gate(None, items)
        self.assertTrue(legacy["ok"], legacy["errors"])

    def test_invalid_panel_chart_types_structure_fails(self):
        # 结构非法：扁平数组/长度不符/面板内重复 → 恒报错
        items = [data_item("Q1/bad1.py", "自造", "x", extra={"panel_chart_types": ["line_2d"]})]
        report = self.run_gate(None, items)
        self.assertFalse(report["ok"])
        flat_or_mixed = any("二维字符串数组" in error for error in report["errors"])
        self.assertTrue(flat_or_mixed)
        items2 = [data_item("Q1/bad2.py", "trend_confidence_template", "line_band", extra={"panel_chart_types": [["line_2d"], ["line_2d"]]})]
        report2 = self.run_gate(None, items2)
        self.assertFalse(report2["ok"])
        self.assertTrue(any("外层长度必须等于" in error for error in report2["errors"]))

    def test_default_stage_annotation(self):
        items = [data_item("Q1/line1.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "默认（少重复）"}, items)
        self.assertEqual(report["details"]["stage"], "step3")
        self.assertEqual(report["details"]["stage_source"], "default_step3")

    # ---- M06（GOAL-84）：空面板与非法成员不得绕过禁止重复 ----
    def test_m06_empty_panels_do_not_bypass_forbid(self):
        items = [data_item("Q1/a.py", "自造", "x", extra={"panel_chart_types": [[]]}),
                 data_item("Q1/b.py", "自造", "x", extra={"panel_chart_types": [[]]})]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertFalse(report["ok"])
        self.assertTrue(any("面板为空" in error for error in report["errors"]))
        self.assertFalse(report["details"].get("ok", False), "空面板不得把 ok 顶回 true")

    def test_m06_illegal_members_are_structured_errors_not_crashes(self):
        for bad in ([[{}]], [[[]]], [[1]], [[True]]):
            with self.subTest(value=bad):
                items = [data_item("Q1/bad.py", "自造", "x", panel_count=1, extra={"panel_chart_types": bad})]
                report = self.run_gate(None, items)
                # 运行到这里说明 stdout 是可解析 JSON（未抛未捕获异常）
                self.assertFalse(report["ok"])
                self.assertTrue(any("非字符串成员" in error for error in report["errors"]))

    def test_m06_outer_length_mismatch_and_legal_two_type_panel(self):
        items = [data_item("Q1/bad.py", "自造", "x", panel_count=2, extra={"panel_chart_types": [["line_2d"]]})]
        report = self.run_gate(None, items)
        self.assertFalse(report["ok"])
        self.assertTrue(any("外层长度必须等于" in error for error in report["errors"]))
        # 合法双图型面板保持原语义（C06 同口径）
        ok_item = data_item("Q1/mix.py", "自造叠加", "overlay", extra={"panel_chart_types": [["line_2d", "scatter_2d"]]})
        report2 = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, [ok_item])
        self.assertTrue(report2["ok"], report2["errors"])

    # ---- M07：roadmap 文件名不再排除数据图 ----
    def test_m07_roadmap_named_line_charts_are_counted(self):
        items = [data_item("Q1/roadmap_a.py", "trend_confidence_template", "line_band"),
                 data_item("Q1/roadmap_b.py", "trend_confidence_template", "line_band")]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertFalse(report["ok"])
        self.assertEqual(report["details"]["counted_figures"], 2)
        self.assertEqual(report["details"]["n_by_type"], {"line_2d": 2})
        self.assertIn("line_2d", report["errors"][0])

    def test_m07_title_token_does_not_exclude_real_data_chart(self):
        items = [data_item("Q1/frame1.py", "trend_confidence_template", "line_band",
                           extra={"title": "问题一求解框架图"})]
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, items)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["counted_figures"], 1)

    # ---- M08：legacy_missing 不被新增理由字段阻断 ----
    def test_m08_legacy_project_with_derivable_repeats_passes(self):
        items = [data_item("Q1/line1.py", "trend_confidence_template", "line_band"),
                 data_item("Q1/line2.py", "trend_confidence_template", "line_band")]
        report = self.run_gate(None, items)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["policy_source"], "legacy_missing")
        self.assertEqual(report["details"]["n_by_type"], {"line_2d": 2})

    def test_m08_explicit_free_mode_still_requires_reasons(self):
        items = [data_item("Q1/line1.py", "trend_confidence_template", "line_band"),
                 data_item("Q1/line2.py", "trend_confidence_template", "line_band")]
        explicit = self.run_gate({"python_chart_repeat_policy": "模型自行分析"}, items)
        self.assertFalse(explicit["ok"])
        self.assertTrue(any("chart_repeat_reasons" in error for error in explicit["errors"]))
        invalid = self.run_gate({"python_chart_repeat_policy": "随便写"}, items)
        self.assertFalse(invalid["ok"])
        self.assertTrue(any("非法" in error for error in invalid["errors"]))

    def test_flowchart_claim_cannot_hide_registered_data_template(self):
        item = data_item("Q1/line.py", "trend_confidence_template", "flowchart")
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, [item])
        self.assertFalse(report["ok"])
        self.assertTrue(any("流程图声明" in error for error in report["errors"]))

    # ---- M09：相同 source 原样重复声明同一 exports → 清单错误 ----
    def test_m09_identical_manifest_entries_reported(self):
        first = data_item("Q1/a.py", "trend_confidence_template", "line_band")
        second = json.loads(json.dumps(first))  # 原样重复条目
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, [first, second])
        self.assertFalse(report["ok"])
        self.assertTrue(any("清单冲突" in error and "重复声明" in error for error in report["errors"]))

    def test_m09_same_source_different_exports_still_legal(self):
        first = data_item("Q1/make.py", "trend_confidence_template", "line_band",
                          extra={"exports": ["figures/a1.pdf", "figures/a1.png", "figures/a1.svg"]})
        second = data_item("Q1/make.py", "trend_confidence_template", "line_band",
                           extra={"exports": ["figures/a2.pdf", "figures/a2.png", "figures/a2.svg"]})
        report = self.run_gate({"python_chart_repeat_policy": "禁止重复"}, [first, second])
        self.assertFalse(report["ok"])  # 禁止重复下两张折线图应失败，而非清单错误
        self.assertTrue(all("清单冲突" not in error for error in report["errors"]))

    # ---- M10：图片解析与实际 TeX 编译目录一致 ----
    def test_m10_resolve_prefers_paper_dir_over_root(self):
        sys.path.insert(0, str(CHECK.parent))
        from common import resolve_figure_references
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "论文").mkdir()
            (project / "same.png").write_bytes(b"root-copy")
            (project / "论文" / "same.png").write_bytes(b"paper-copy")
            (project / "论文" / "main.tex").write_text(
                "\\documentclass{gmcmthesis}\n\\includegraphics{same.png}\n", encoding="utf-8")
            info = resolve_figure_references(project)
        self.assertFalse(info["tex_missing"])
        self.assertEqual(len(info["resolved"]), 1)
        self.assertEqual(info["resolved"][0].parent.name, "论文", "与实际 TeX cwd 一致，应选论文目录那张")

    def test_m10_current_directory_before_graphicspath_and_no_root_guess(self):
        sys.path.insert(0, str(CHECK.parent))
        from common import resolve_figure_references
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            paper = project / "论文"
            (paper / "g").mkdir(parents=True)
            for target in (paper / "same.pdf", paper / "g" / "same.pdf", project / "root.pdf"):
                target.write_bytes(b"stub")
            (paper / "main.tex").write_text(
                r"\graphicspath{{g/}}\includegraphics{same.pdf}\includegraphics{root.pdf}", encoding="utf-8")
            info = resolve_figure_references(project)
            self.assertEqual(info["resolved"], [(paper / "same.pdf").resolve()])
            self.assertEqual(info["unresolved"], ["root.pdf"])

    def test_m10_extension_priority_before_directory_priority(self):
        sys.path.insert(0, str(CHECK.parent))
        from common import resolve_figure_references
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            paper = project / "论文"
            (paper / "g").mkdir(parents=True)
            (paper / "same.png").write_bytes(b"stub")
            (paper / "g" / "same.pdf").write_bytes(b"stub")
            (paper / "main.tex").write_text(
                r"\graphicspath{{g/}}\includegraphics{same}", encoding="utf-8")
            self.assertEqual(resolve_figure_references(project)["resolved"], [(paper / "g" / "same.pdf").resolve()])

    def test_m10_graphicspath_and_unresolvable_and_out_of_project(self):
        sys.path.insert(0, str(CHECK.parent))
        from common import resolve_figure_references
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            outside = Path(tmp) / "outside-project"
            outside.mkdir()
            (outside / "out.png").write_bytes(b"outside")
            (project / "论文").mkdir(parents=True)
            (project / "论文" / "fig").mkdir()
            (project / "论文" / "fig" / "g.png").write_bytes(b"gp")
            tex = ("\\documentclass{gmcmthesis}\n"
                   "\\graphicspath{{fig/}}\n"
                   "\\includegraphics{g}\n"          # graphicspath + 省略扩展名
                   "\\includegraphics{missing.png}\n"  # 找不到文件
                   "\\includegraphics{../outside-project/out.png}\n"  # 项目外
                   "\\includegraphics{\\macrofig}\n"   # 宏构造：须标未解析
                   "\\end{document}\n")
            (project / "论文" / "main.tex").write_text(tex, encoding="utf-8")
            info = resolve_figure_references(project)
        self.assertEqual(info["resolved"][0].name, "g.png")
        self.assertTrue(all(path.is_relative_to(project) for path in info["resolved"]),
                        "解析结果不得包含项目外文件")
        self.assertIn("missing.png", info["unresolved"])
        self.assertTrue(any("outside-project" in token for token in info["unresolved"]))
        self.assertTrue(any("宏" in token for token in info["unresolved"]))


if __name__ == "__main__":
    unittest.main()
