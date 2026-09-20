#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_excellent_paper_visual_reference.py")

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
SHA_A = "a" * 64
SHA_B = "b" * 64


def sample_shot(index: int) -> dict:
    page = 1 if index == 0 else 2
    label = "摘要" if index == 0 else "求解"
    png = "p001_摘要.png" if index == 0 else "p002_求解.png"
    folder = f"截图/优秀论文{index + 1}"
    return {"page": page, "label": label, "png": png, "folder": folder}


def observation_lines(png_relative: str, filled: bool) -> list[str]:
    if not filled:
        return [
            f"- 视觉读取：未读取，待完成视觉观察 `{png_relative}`",
            "- 版式留白与信息密度：待填写",
            "- 布局与图表组织：待填写",
            "- 文风与句式节奏：待填写",
            "- 明确禁止复制的内容：待填写",
        ]
    return [
        f"- 视觉读取：已读取 `{png_relative}`，观察结论如下",
        "- 版式留白与信息密度：摘要单页铺满，标题两级，段落长度中等，图表靠近首段解释。",
        "- 布局与图表组织：单图为主，图宽约占版心三分之二，表题在表上方。",
        "- 文风与句式节奏：短句克制，每段三到五句，先结论后依据。",
        "- 明确禁止复制的内容：原句、公式、数据、结论与装饰符号",
    ]


def sample_record(index: int, filled: bool, same_problem_note: bool) -> str:
    shot = sample_shot(index)
    sha = SHA_A if index == 0 else SHA_B
    png_relative = f"{shot['folder']}/{shot['png']}"
    lines = [
        "# 优秀论文参考记录（华为杯视觉校准）",
        "",
        "- 共享发现状态：matched",
        "- 回退原因：无",
        f"- 同题匹配：{'是' if same_problem_note else '否——未能完成同题参考，仅同赛事参考'}",
        "",
        f"## 样本 {shot['folder']}",
        "",
        "- 赛事：华为杯　年份：2023　题号：A",
        f"- 样本 PDF：论文库/样本-{sha[:8]}.pdf（共 20 页，仅渲染代表页）",
        f"- 样本身份：relativePath=论文库/样本-{sha[:8]} sha256={sha}",
        "",
        "### 逐页视觉读取记录",
        "",
        f"#### p{shot['page']:03d}（{shot['label']}）`{png_relative}`",
        "",
        *observation_lines(png_relative, filled),
        "",
    ]
    return "\n".join(lines)


def build_report(papers: list[dict], status: str = "matched", problem_match: bool = True, declared: int | None = None) -> dict:
    report = {
        "ok": True,
        "status": status,
        "problem_match": problem_match,
        "papers": declared if declared is not None else len(papers),
        "selected_papers": papers,
        "render_failures": [],
    }
    if status != "matched":
        report["fallback_reason"] = "暂无匹配样本"
        report["selected_papers"] = []
        report["papers"] = 0
    return report


def selected_paper(index: int) -> dict:
    shot = sample_shot(index)
    sha = SHA_A if index == 0 else SHA_B
    return {
        "relativePath": f"论文库/样本-{sha[:8]}",
        "sha256": sha,
        "folder": shot["folder"],
        "shots": [{"page": shot["page"], "label": shot["label"], "relative": f"{shot['folder']}/{shot['png']}"}],
    }


class ExcellentPaperVisualReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temps: list[tempfile.TemporaryDirectory] = []

    def tearDown(self) -> None:
        for item in self._temps:
            item.cleanup()

    def build_project(
        self,
        state: dict | None,
        report: dict | None,
        filled_flags: list[bool] | None = None,
        leak: bool = False,
        same_problem_note: bool = True,
        with_evidence: bool | None = None,
    ) -> Path:
        """with_evidence=None 表示按 report 是否 matched 自动决定是否放置截图/记录。"""
        tmp = tempfile.TemporaryDirectory()
        self._temps.append(tmp)
        project = Path(tmp.name) / "project"
        (project / "论文").mkdir(parents=True)
        if state is not None:
            (project / "项目状态.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tex = "\\documentclass{gmcmthesis}\n\\begin{document}\n"
        if leak:
            tex += "\\includegraphics[width=0.8\\textwidth]{截图/优秀论文1/p001_摘要.png}\n"
        tex += "\\end{document}\n"
        (project / "论文" / "main.tex").write_text(tex, encoding="utf-8")
        if report is not None:
            (project / "检查结果").mkdir(parents=True, exist_ok=True)
            (project / "检查结果" / "excellent_paper_visual_review.json").write_text(
                json.dumps(report, ensure_ascii=False), encoding="utf-8"
            )
        place = with_evidence if with_evidence is not None else (report is None or report.get("status") == "matched")
        if place:
            flags = filled_flags or [True]
            record = ""
            for index, filled in enumerate(flags):
                shot = sample_shot(index)
                (project / shot["folder"]).mkdir(parents=True, exist_ok=True)
                (project / shot["folder"] / shot["png"]).write_bytes(PNG_1PX)
                record += sample_record(index, filled, same_problem_note)
            (project / "截图").mkdir(parents=True, exist_ok=True)
            (project / "截图" / "优秀论文参考记录.md").write_text(record, encoding="utf-8")
        return project

    def run_check(self, project: Path) -> dict:
        proc = subprocess.run(
            [sys.executable, str(CHECK), "--project", str(project)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return json.loads(proc.stdout)

    # ---- E01 ----
    def test_disabled_requires_nothing(self):
        report = self.run_check(self.build_project({"reference_excellent_papers": False}, None))
        self.assertTrue(report["ok"], report["errors"])
        self.assertFalse(report["details"]["enabled"])

    def test_legacy_project_without_switch_passes(self):
        report = self.run_check(self.build_project(None, None))
        self.assertTrue(report["ok"], report["errors"])
        self.assertFalse(report["details"]["enabled"])

    def test_invalid_switch_type_reports_config_error(self):
        report = self.run_check(self.build_project({"reference_excellent_papers": "abc"}, None))
        self.assertFalse(report["ok"])
        self.assertTrue(any("不是合法布尔值" in error for error in report["errors"]))

    def test_switch_not_inferred_from_tex(self):
        # R09：tex 出现字段字符串不能当作开启
        project = self.build_project(None, None)
        tex = project / "论文" / "main.tex"
        tex.write_text(
            tex.read_text(encoding="utf-8").replace("\\begin{document}", "reference_excellent_papers\n\\begin{document}"),
            encoding="utf-8",
        )
        report = self.run_check(project)
        self.assertTrue(report["ok"], report["errors"])
        self.assertFalse(report["details"]["enabled"])

    # ---- E02 ----
    def test_matched_with_full_evidence_passes(self):
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            build_report([selected_paper(0)]),
        ))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["papers"], 1)

    # ---- E03 ----
    def test_corrupt_png_fails(self):
        project = self.build_project({"reference_excellent_papers": True}, build_report([selected_paper(0)]))
        (project / "截图" / "优秀论文1" / "p001_摘要.png").write_bytes(b"not a png")
        report = self.run_check(project)
        self.assertFalse(report["ok"])
        self.assertTrue(any("解码" in error for error in report["errors"]))

    def test_missing_page_shot_fails(self):
        # 某页缺 PNG/缺观察：报告登记两页但项目只有一页证据
        payload = build_report([selected_paper(0)])
        payload["selected_papers"][0]["shots"].append(
            {"page": 2, "label": "求解", "relative": "截图/优秀论文1/p002_求解.png"}
        )
        report = self.run_check(self.build_project({"reference_excellent_papers": True}, payload))
        self.assertFalse(report["ok"])
        self.assertTrue(any("缺少代表页截图" in error for error in report["errors"]))

    def test_two_declared_but_one_evidence_fails(self):
        # E03：发现报告选择两篇但缺少第二篇证据
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            build_report([selected_paper(0)], declared=2),
        ))
        self.assertFalse(report["ok"])
        self.assertTrue(any("selected_papers 只有 1 篇" in error for error in report["errors"]))

    def test_one_selected_paper_only_requires_one(self):
        # 实际只命中一篇不得误报少样本
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            build_report([selected_paper(0)]),
        ))
        self.assertTrue(report["ok"], report["errors"])

    def test_placeholder_and_unread_observation_fail(self):
        # R08：占位与“未读取”都不算观察
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            build_report([selected_paper(0)]),
            filled_flags=[False],
        ))
        self.assertFalse(report["ok"])
        self.assertTrue(any("未读取" in error for error in report["errors"]))

    # ---- E04 ----
    def test_enabled_but_disabled_status_conflicts(self):
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            {"ok": True, "status": "disabled", "papers": 0, "selected_papers": []},
        ))
        self.assertFalse(report["ok"])
        self.assertTrue(any("冲突" in error for error in report["errors"]))

    # ---- E05 ----
    def test_no_matching_sample_with_reason_passes(self):
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            build_report([], status="no_matching_sample"),
            with_evidence=False,
        ))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["status"], "no_matching_sample")

    def test_fallback_without_reason_fails(self):
        project = self.build_project(
            {"reference_excellent_papers": True},
            build_report([], status="no_matching_sample"),
            with_evidence=False,
        )
        path = project / "检查结果" / "excellent_paper_visual_review.json"
        broken = json.loads(path.read_text(encoding="utf-8"))
        broken["fallback_reason"] = ""
        path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
        report = self.run_check(project)
        self.assertFalse(report["ok"])
        self.assertTrue(any("回退原因" in error for error in report["errors"]))

    # ---- E06 ----
    def test_sample_one_missing_observation_still_fails(self):
        # 样本一缺观察、样本二齐全：样本一仍失败，样本二不背锅
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            build_report([selected_paper(0), selected_paper(1)]),
            filled_flags=[False, True],
        ))
        self.assertFalse(report["ok"])
        self.assertTrue(any("优秀论文1" in error for error in report["errors"]))
        self.assertFalse(any("优秀论文2" in error for error in report["errors"]))

    # ---- E07 ----
    def test_screenshot_leak_fails_when_enabled(self):
        report = self.run_check(self.build_project(
            {"reference_excellent_papers": True},
            build_report([selected_paper(0)]),
            leak=True,
        ))
        self.assertFalse(report["ok"])
        self.assertTrue(any("不得被" in error for error in report["errors"]))

    def test_screenshot_leak_fails_when_disabled(self):
        # E07：任意开关状态下截图入文都失败
        report = self.run_check(self.build_project({"reference_excellent_papers": False}, None, leak=True))
        self.assertFalse(report["ok"])
        self.assertTrue(any("不得被" in error for error in report["errors"]))

    # ---- E10 ----
    def test_matched_without_problem_match_requires_note(self):
        payload = build_report([selected_paper(0)], problem_match=False)
        ok_report = self.run_check(self.build_project(
            {"reference_excellent_papers": True}, payload, same_problem_note=False,
        ))
        self.assertTrue(ok_report["ok"], ok_report["errors"])
        bad_report = self.run_check(self.build_project(
            {"reference_excellent_papers": True}, payload, same_problem_note=True,
        ))
        self.assertFalse(bad_report["ok"])
        self.assertTrue(any("未能完成同题参考" in error for error in bad_report["errors"]))

    def test_missing_authoritative_report_fails(self):
        report = self.run_check(self.build_project({"reference_excellent_papers": True}, None))
        self.assertFalse(report["ok"])
        self.assertTrue(any("权威报告" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
