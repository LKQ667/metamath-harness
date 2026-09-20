#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_paper_body_forbidden_symbols.py")


def build_paper(middle: str) -> str:
    return (
        "\\documentclass[bwprint]{gmcmthesis}\n\\title{样例标题}\n"
        "\\baominghao{20260900001}\n\\schoolname{测试学校}\n"
        "\\membera{甲}\n\\memberb{乙}\n\\memberc{丙}\n"
        "\\begin{document}\n"
        "\\label{body:start}\n\\maketitle\n"
        "\\begin{abstract}\\label{abstract:start}摘要内容。\\keywords{关键词}\\label{abstract:end}\\end{abstract}\n"
        f"{middle}\n"
        "\\begin{thebibliography}{9}\n\\bibitem{a} 参考文献。\n\\end{thebibliography}\n"
        "\\label{body:end}\n\\newpage\n\\label{appendix:start}\n"
        "\\begin{appendices}\n\\section{支撑材料文件目录}\n仅代码名称。\n"
        "\\section{附录代码文件}\n\\begin{Python}\nprint(1)\n\\end{Python}\n\\end{appendices}\n\\end{document}\n"
    )


def run_check(tex: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "论文").mkdir()
        (project / "论文" / "main.tex").write_text(tex, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(CHECK), "--project", str(project)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return json.loads(proc.stdout)


class ForbiddenSymbolTests(unittest.TestCase):
    def test_raw_middot_fails(self):
        report = run_check(build_paper("本节要点\u00b7 第一项。"))
        self.assertFalse(report["ok"])
        self.assertTrue(any("\u00b7" in error or "中点" in error for error in report["errors"]))

    def test_bullet_fails(self):
        report = run_check(build_paper("要点\u2022 第一项。"))
        self.assertFalse(report["ok"])
        self.assertTrue(any("项目符号" in error for error in report["errors"]))

    def test_checkbox_fails(self):
        report = run_check(build_paper("选项\u2610 第一项。"))
        self.assertFalse(report["ok"])
        self.assertTrue(any("复选框" in error for error in report["errors"]))

    def test_latex_cdot_passes(self):
        report = run_check(build_paper("向量内积写成 $a\\cdot b$ 的形式。"))
        self.assertTrue(report["ok"], report["errors"])

    def test_inline_raw_middot_inside_math_fails_outside_only(self):
        report = run_check(build_paper("正文说明。\n$a\\cdot b$ 与 $c\\cdot d$ 相乘。"))
        self.assertTrue(report["ok"], report["errors"])

    def test_commented_symbol_is_ignored(self):
        report = run_check(build_paper("% 备注：\u00b7 不进入正文\n正文说明。"))
        self.assertTrue(report["ok"], report["errors"])


if __name__ == "__main__":
    unittest.main()
