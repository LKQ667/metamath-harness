#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""渲染器行为测试：不预写已读、重跑保留观察、样本身份识别、disabled/fallback 路径。

样例 PDF 与论文库均为合成数据，只用于测试，不进入实际论文。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RENDER = Path(__file__).with_name("excellent_paper_visual_review.py")
FILLED_MARK = "已填写观察标记E08：摘要单页铺满标题两级，图占版心一半，留白均匀。"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_paper_pdf(path: Path, pages: int = 4, extra_text: str = "") -> None:
    import fitz

    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"摘要与关键词 模型建立 求解 第{index + 1}页 {extra_text}", fontname="china-s")
    doc.save(str(path))
    doc.close()


def build_library(home: Path, papers: list[dict]) -> None:
    """papers: [{"name": "docs/paper1.pdf", "problem": "A", "priority": 2}]

    catalog 的 path 相对论文库根（往年优秀论文/）解析，与共享发现脚本一致。
    """
    library = home / "往年优秀论文"
    library.mkdir(parents=True, exist_ok=True)
    entries = []
    for spec in papers:
        target = library / spec["name"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            # 复用已有 PDF 字节：fitz 重建含时间戳，会导致 sha 无谓变化
            build_paper_pdf(target)
        entries.append({
            "path": spec["name"],
            "competition": "华为杯",
            "year": 2023,
            "problem": spec.get("problem", "A"),
            "priority": spec.get("priority", 1),
            "sha256": sha256_of(target),
        })
    catalog = {
        "schema": "dsh.excellent-papers.catalog/v1",
        "competitions": {"华为杯": ["huawei"]},
        "papers": entries,
    }
    (library / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def write_catalog(home: Path, papers: list[dict]) -> None:
    build_library(home, papers)


def run_renderer(project: Path, home: Path, extra_args: list[str] | None = None) -> dict:
    proc = subprocess.run(
        [sys.executable, str(RENDER), "--project", str(project), "--dsh-home", str(home), *(extra_args or [])],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    return json.loads(proc.stdout)


def read_record(project: Path) -> str:
    return (project / "截图" / "优秀论文参考记录.md").read_text(encoding="utf-8")


def fill_observations(project: Path) -> None:
    record = read_record(project)
    record = record.replace("- 视觉读取：未读取，待完成视觉观察 ", "- 视觉读取：已读取 ")
    record = record.replace("- 版式留白与信息密度：待填写", f"- 版式留白与信息密度：{FILLED_MARK}")
    record = record.replace("- 布局与图表组织：待填写", "- 布局与图表组织：布局组织标记E08：单图为主表题在上。")
    record = record.replace("- 文风与句式节奏：待填写", "- 文风与句式节奏：文风节奏标记E08：短句克制。")
    record = record.replace("- 明确禁止复制的内容：待填写", "- 明确禁止复制的内容：原句、公式、数据与装饰符号")
    (project / "截图" / "优秀论文参考记录.md").write_text(record, encoding="utf-8")


class ExcellentPaperVisualReviewRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temps: list[tempfile.TemporaryDirectory] = []

    def tearDown(self) -> None:
        for item in self._temps:
            item.cleanup()

    def temp_pair(self) -> tuple[Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        self._temps.append(tmp)
        root = Path(tmp.name)
        return root / "home", root / "project"

    def test_disabled_writes_nothing(self):
        home, project = self.temp_pair()
        project.mkdir(parents=True)
        report = run_renderer(project, home, ["--disabled"])
        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "disabled")
        self.assertFalse((project / "检查结果" / "excellent_paper_visual_review.json").exists())
        self.assertFalse((project / "截图").exists())

    def test_fallback_writes_report_with_reason(self):
        home, project = self.temp_pair()
        project.mkdir(parents=True)
        build_library(home, [{"name": "docs/paper1.pdf", "problem": "B", "priority": 1}])
        report = run_renderer(project, home, ["--problem", "A"])
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["status"], "no_matching_sample")
        self.assertTrue(report["fallback_reason"])
        written = json.loads((project / "检查结果" / "excellent_paper_visual_review.json").read_text(encoding="utf-8"))
        self.assertEqual(written["status"], "no_matching_sample")
        self.assertIn("暂无匹配样本", written["fallback_reason"])
        record = read_record(project)
        self.assertIn("no_matching_sample", record)

    def test_rerun_preserves_filled_observations(self):
        # E08/R10：初始未读取；重跑复用截图并保留已填写观察
        home, project = self.temp_pair()
        project.mkdir(parents=True)
        build_library(home, [{"name": "docs/paper1.pdf", "problem": "A", "priority": 1}])
        first = run_renderer(project, home, ["--problem", "A"])
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["status"], "matched")
        self.assertTrue(first["problem_match"])
        record = read_record(project)
        self.assertIn("未读取，待完成视觉观察", record)
        self.assertNotIn("已读取", record.split("### 逐页视觉读取记录")[1])
        self.assertTrue((project / "截图" / "优秀论文1").exists())
        pngs_before = sorted(path.name for path in (project / "截图" / "优秀论文1").glob("*.png"))
        fill_observations(project)
        second = run_renderer(project, home, ["--problem", "A"])
        self.assertTrue(second["ok"], second)
        record_after = read_record(project)
        self.assertIn(FILLED_MARK, record_after, "重跑不得覆盖已完成观察")
        pngs_after = sorted(path.name for path in (project / "截图" / "优秀论文1").glob("*.png"))
        self.assertEqual(pngs_before, pngs_after)
        self.assertTrue(all(shot["relative"] for shot in second["selected_papers"][0]["shots"]))

    def test_sample_order_change_keeps_observations_with_identity(self):
        # E09：样本次序变化后观察跟随内容身份，而不是排序位置
        home, project = self.temp_pair()
        project.mkdir(parents=True)
        build_library(home, [
            {"name": "docs/paper1.pdf", "problem": "A", "priority": 2},
            {"name": "docs/paper2.pdf", "problem": "A", "priority": 1},
        ])
        first = run_renderer(project, home, ["--problem", "A"])
        self.assertEqual(first["papers"], 2)
        self.assertEqual(first["selected_papers"][0]["relativePath"], "docs/paper1.pdf")
        fill_observations(project)
        write_catalog(home, [
            {"name": "docs/paper1.pdf", "problem": "A", "priority": 1},
            {"name": "docs/paper2.pdf", "problem": "A", "priority": 2},
        ])
        second = run_renderer(project, home, ["--problem", "A"])
        self.assertEqual(second["selected_papers"][0]["relativePath"], "docs/paper2.pdf")
        record = read_record(project)
        self.assertIn(FILLED_MARK, record)
        blocks = record.split("## 样本 ")
        block_for_paper1 = next(block for block in blocks if "relativePath=docs/paper1.pdf" in block)
        self.assertIn(FILLED_MARK, block_for_paper1, "观察应跟随内容身份移动到新序号样本")

    def test_legacy_record_without_identity_reuses_by_pdf_path(self):
        # 旧版渲染器记录无 sha256 身份行，仅凭“样本 PDF”路径回退匹配复用观察
        home, project = self.temp_pair()
        project.mkdir(parents=True)
        build_library(home, [{"name": "docs/paper1.pdf", "problem": "A", "priority": 1}])
        first = run_renderer(project, home, ["--problem", "A"])
        self.assertTrue(first["ok"], first)
        fill_observations(project)
        record = read_record(project)
        record = record.replace("- 样本身份：relativePath=docs/paper1.pdf sha256=" + first["selected_papers"][0]["sha256"], "- 样本身份：（旧版记录）")
        (project / "截图" / "优秀论文参考记录.md").write_text(record, encoding="utf-8")
        second = run_renderer(project, home, ["--problem", "A"])
        self.assertTrue(second["ok"], second)
        self.assertIn(FILLED_MARK, read_record(project), "旧版记录应凭 PDF 路径回退匹配并保留观察")

    def test_content_change_invalidates_reuse_and_archives_old(self):
        # E09：同路径 PDF 内容变化后 sha 不同，不复用旧观察；旧记录保留归档
        home, project = self.temp_pair()
        project.mkdir(parents=True)
        build_library(home, [{"name": "docs/paper1.pdf", "problem": "A", "priority": 1}])
        run_renderer(project, home, ["--problem", "A"])
        fill_observations(project)
        library = home / "往年优秀论文"
        pdf_path = library / "docs" / "paper1.pdf"
        build_paper_pdf(pdf_path, pages=4, extra_text="内容已变化")
        catalog = json.loads((library / "catalog.json").read_text(encoding="utf-8"))
        catalog["papers"][0]["sha256"] = sha256_of(pdf_path)
        (library / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        second = run_renderer(project, home, ["--problem", "A"])
        self.assertTrue(second["ok"], second)
        record = read_record(project)
        self.assertIn("未读取，待完成视觉观察", record, "内容变化后不得复用旧观察")
        self.assertIn("（旧样本，不参与本次统计）", record, "旧记录必须保留并标注不参与统计")
        self.assertIn(FILLED_MARK, record, "旧观察文本本身应被保留归档")


if __name__ == "__main__":
    unittest.main()
