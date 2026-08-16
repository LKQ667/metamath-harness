#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""华数杯模板身份与赛事规则的最小回归合同。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from common import read_text
from run_stage_gate import launcher_source


CHECKS = Path(__file__).resolve().parent
SKILL_ROOT = CHECKS.parents[1]
TEMPLATE_DIR = SKILL_ROOT / "assets" / "templates"


class HuashuTemplateContractTests(unittest.TestCase):
    def run_check(self, script: str, main_tex: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="huashu-template-check-") as tmp:
            project = Path(tmp)
            paper = project / "论文"
            paper.mkdir()
            (paper / "main.tex").write_text(main_tex, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(CHECKS / script), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )

    def test_bundled_template_passes_huashu_identity_gate(self) -> None:
        main = (TEMPLATE_DIR / "main.tex").read_text(encoding="utf-8")
        result = self.run_check("check_template_adherence.py", main)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_generic_article_cannot_replace_huashu_template(self) -> None:
        main = (TEMPLATE_DIR / "main.tex").read_text(encoding="utf-8")
        main = main.replace("\\documentclass{JXUSTmodeling}", "\\documentclass{ctexart}")
        result = self.run_check("check_template_adherence.py", main)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("JXUSTmodeling", result.stdout)

    def test_huashu_does_not_inherit_cumcm_abstract_formula_ban(self) -> None:
        main = (TEMPLATE_DIR / "main.tex").read_text(encoding="utf-8")
        main = main.replace("[中文摘要内容", r"模型目标为 $\min f(x)$。[中文摘要内容")
        result = self.run_check("check_abstract_no_formula.py", main)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('"profile": "huashu"', result.stdout)

    def test_template_contains_invisible_page_contract_labels(self) -> None:
        main = (TEMPLATE_DIR / "main.tex").read_text(encoding="utf-8")
        cls = (TEMPLATE_DIR / "JXUSTmodeling.cls").read_text(encoding="utf-8")
        for marker in ("body:start", "body:end", "appendix:start"):
            self.assertIn(rf"\label{{{marker}}}", main)
        self.assertIn(r"\label{abstract:end}", cls)

    def test_content_checks_expand_guarded_section_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="huashu-input-expand-") as tmp:
            paper = Path(tmp) / "论文"
            section = paper / "sections" / "1_restatement.tex"
            section.parent.mkdir(parents=True)
            section.write_text(r"\section{问题重述}真实内容", encoding="utf-8")
            main = paper / "main.tex"
            main.write_text(r"\input{sections/1_restatement}", encoding="utf-8")
            expanded = read_text(main)
            self.assertIn(r"\section{问题重述}", expanded)
            self.assertNotIn(r"\input{sections/1_restatement}", expanded)

    def test_content_checks_do_not_expand_outside_paper_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="huashu-input-guard-") as tmp:
            root = Path(tmp)
            paper = root / "论文"
            paper.mkdir()
            (root / "outside.tex").write_text("不应读取", encoding="utf-8")
            main = paper / "main.tex"
            main.write_text(r"\input{../outside}", encoding="utf-8")
            self.assertEqual(read_text(main), r"\input{../outside}")

    def test_project_launcher_resolves_huashu_skill(self) -> None:
        source = launcher_source(["--stage", "step0"])
        self.assertIn("skills' / 'math-paper-huashu'", source)
        self.assertNotIn("skills' / 'math-paper-cn'", source)

    def test_agent_entry_uses_huashu_skill_name(self) -> None:
        agent = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$math-paper-huashu", agent)
        self.assertNotIn("$math-paper-cn", agent)


if __name__ == "__main__":
    unittest.main()
