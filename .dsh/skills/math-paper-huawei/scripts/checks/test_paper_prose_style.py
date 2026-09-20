#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_paper_prose_style.py")


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


class ProseStyleTests(unittest.TestCase):
    def test_hard_word_verdict_fails(self):
        report = run_check(build_paper("本文最终判决结果如表所示。"))
        self.assertFalse(report["ok"])
        self.assertTrue(any("判决" in error for error in report["errors"]))

    def test_hard_word_judgement_fails(self):
        report = run_check(build_paper("据此判定各方案优劣。"))
        self.assertFalse(report["ok"])
        self.assertTrue(any("判定" in error for error in report["errors"]))

    def test_hard_word_word_boundary(self):
        report = run_check(build_paper("综上，模型可以判断方案优劣。"))
        self.assertTrue(report["ok"], report["errors"])

    def test_hypothesis_testing_kept(self):
        report = run_check(build_paper("采用假设检验方法处理该显著性结论。"))
        self.assertTrue(report["ok"], report["errors"])

    def test_soft_words_low_frequency_passes(self):
        report = run_check(build_paper("结果与实测数据比较。再复算一次一致性。检验结论稳定。"))
        self.assertTrue(report["ok"], report["errors"])

    def test_soft_words_over_limit_yields_suggestion_not_failure(self):
        # W01/R05：三词合计超限只产生编辑建议，不导致失败
        report = run_check(build_paper("验证一。验证二。检验一。核对一。"))
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(any("低频词统计" in item for item in report["details"]["suggestions"]))
        self.assertGreater(sum(report["details"]["soft_word_counts"].values()), 3)

    def test_four_professional_hypothesis_testing_passes_with_counts(self):
        # W01：四次专业术语“假设检验”不失败且输出频次
        report = run_check(
            build_paper(
                "采用假设检验处理第一组。以假设检验复核第二组。"
                "第三组仍用假设检验确认。假设检验的结论与实测一致。"
            )
        )
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["details"]["soft_word_counts"]["检验"], 4)
        self.assertTrue(any("假设检验" in item for item in report["details"]["suggestions"]))

    def test_forbidden_words_in_bibliography_do_not_fail(self):
        tex = build_paper("模型结果与实测一致。")
        tex = tex.replace("\\bibitem{a} 参考文献。", "\\bibitem{a} 判定理论导论。")
        report = run_check(tex)
        self.assertTrue(report["ok"], report["errors"])

    def test_forbidden_word_in_math_and_code_does_not_fail(self):
        report = run_check(build_paper("符号记作 $\\text{判定}$。\n\\begin{equation}\n判决 = 1\n\\end{equation}"))
        self.assertTrue(report["ok"], report["errors"])


if __name__ == "__main__":
    unittest.main()
