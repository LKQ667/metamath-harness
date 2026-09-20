#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GOAL-84/M14：符号说明结构与 PDF 位置检查回归（N01/N02/N07/N08/N09 + PDF 顺序）。"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECKS = Path(__file__).resolve().parent
WHITELIST = CHECKS / "check_paper_section_whitelist.py"

TEMPLATE_HEAD = (
    "\\documentclass[bwprint]{gmcmthesis}\n"
    "\\title{测试论文}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\label{body:start}\n"
    "\\begin{abstract}\n摘要\n\\end{abstract}\n"
    "\\maketoc\n"
    "\\begin{thebibliography}{9}\n\\bibitem{a} refs\n\\end{thebibliography}\n"
)

BODY_FIXED = (
    "\\section{问题重述}\n正文\n"
    "\\section{模型假设与符号说明}\n"
)

BODY_TAIL = (
    "\\section{问题一模型建立与求解}\n正文\n"
    "\\section{模型总结与评价}\n正文\n"
    "\\label{body:end}\n"
    "\\newpage\n"
    "\\label{appendix:start}\n"
    "\\begin{appendices}\n"
    "支撑材料文件目录：Q1\n"
    "\\section{附录代码文件}\n代码\n"
    "\\end{appendices}\n"
    "\\end{document}\n"
)

SYMBOL_TABLE = (
    "\\subsection{符号说明}\n"
    "\\begin{tabular}{|c|c|}\n符号 & 意义 \\\\\n\\hline\n$a$ & 测试 \\\\\n\\end{tabular}\n"
)


def run_whitelist(tex: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "论文").mkdir()
        (project / "论文" / "main.tex").write_text(tex, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(WHITELIST), "--project", str(project)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return json.loads(proc.stdout)


def load_template_module():
    spec = importlib.util.spec_from_file_location("cta_m14", CHECKS / "check_template_adherence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SymbolStructureSourceTests(unittest.TestCase):
    def test_n01_three_row_template_order_passes(self):
        tex = TEMPLATE_HEAD + BODY_FIXED + "\\subsection{模型假设}\n假设\n" + SYMBOL_TABLE + BODY_TAIL
        report = run_whitelist(tex)
        self.assertTrue(report["ok"], report["errors"])

    def test_n02_figure_inserted_before_symbol_table_fails(self):
        inserted = (
            "\\subsection{符号说明}\n"
            "\\begin{figure}[htp!]\n\\includegraphics{x.png}\n\\caption{EDA}\n\\end{figure}\n"
            "\\begin{tabular}{|c|c|}\n符号 & 意义 \\\\\\end{tabular}\n"
        )
        tex = TEMPLATE_HEAD + BODY_FIXED + "\\subsection{模型假设}\n假设\n" + inserted + BODY_TAIL
        report = run_whitelist(tex)
        self.assertFalse(report["ok"])
        self.assertTrue(any("插入了 figure" in e for e in report["errors"]), report["errors"])

    def test_n07_missing_table_float_table_and_duplicate_subsection_fail(self):
        tex = TEMPLATE_HEAD + BODY_FIXED + "\\subsection{模型假设}\n假设\n\\subsection{符号说明}\n只有文字。\n" + BODY_TAIL
        report = run_whitelist(tex)
        self.assertFalse(report["ok"])
        self.assertTrue(any("缺少符号表" in e for e in report["errors"]), report["errors"])

        tex2 = (TEMPLATE_HEAD + BODY_FIXED + "\\subsection{模型假设}\n假设\n"
                + SYMBOL_TABLE.replace("\\begin{tabular}", "\\begin{table}[htp!]\\centering\\begin{tabular}", 1)
                .replace("\\end{tabular}", "\\end{tabular}\n\\end{table}", 1) + BODY_TAIL)
        report2 = run_whitelist(tex2)
        self.assertFalse(report2["ok"])
        self.assertTrue(any("可漂移浮动容器" in e for e in report2["errors"]), report2["errors"])

        tex3 = (TEMPLATE_HEAD + BODY_FIXED + "\\subsection{模型假设}\n假设\n% \\subsection{符号说明}\n"
                "\\subsection{符号说明}\n\\subsection{符号说明}\n"
                "\\begin{tabular}{|c|c|}\n符号 & 意义 \\\\\\end{tabular}\n" + BODY_TAIL)
        report3 = run_whitelist(tex3)
        self.assertFalse(report3["ok"])
        self.assertTrue(any("不得缺失、重复" in e for e in report3["errors"]), report3["errors"])

    def test_n08_comment_toc_mentions_are_not_structures(self):
        tex = (TEMPLATE_HEAD
               + "% 目录或注释中提到：四、符号说明（不应命中结构检查）\n"
               + BODY_FIXED + "\\subsection{模型假设}\n假设\n" + SYMBOL_TABLE + BODY_TAIL)
        report = run_whitelist(tex)
        self.assertTrue(report["ok"], report["errors"])

    def test_n09_captionless_symbol_table_passes_before_result_tables(self):
        result_table = ("\\section{问题一模型建立与求解}\n"
                        "\\begin{table}[htp!]\\caption{结果}\\begin{tabular}{|c|}a\\\\\\end{tabular}\\end{table}\n")
        tex = (TEMPLATE_HEAD + BODY_FIXED + "\\subsection{模型假设}\n假设\n" + SYMBOL_TABLE
               + result_table
               + BODY_TAIL.split("\\section{问题一模型建立与求解}\n正文\n", 1)[1])
        report = run_whitelist(tex)
        self.assertTrue(report["ok"], report["errors"])


    def test_wrong_second_section_duplicate_table_and_star_float_fail(self):
        valid = TEMPLATE_HEAD + BODY_FIXED + "\\subsection{模型假设}\n假设\n" + SYMBOL_TABLE + BODY_TAIL
        cases = [
            valid.replace("\\section{问题重述}\n", ""),
            valid.replace("\\end{tabular}", "\\end{tabular}\n" + r"\begin{tabular}{cc}a&b\\\end{tabular}"),
            valid.replace("\\begin{tabular}", "\\begin{table*}\n\\begin{tabular}").replace("\\end{tabular}", "\\end{tabular}\n\\end{table*}"),
            valid.replace("问题一模型建立与求解", "问题二模型建立与求解"),
        ]
        for tex in cases:
            with self.subTest(tex=tex):
                self.assertFalse(run_whitelist(tex)["ok"])


def make_pdf(path: Path, lines: list[tuple[int, float, str]]) -> None:
    import fitz
    doc = fitz.open()
    pages: dict[int, object] = {}
    for page_no, y, text in lines:
        page = pages.get(page_no)
        if page is None:
            page = doc.new_page()
            pages[page_no] = page
        page.insert_text((72, y), text, fontname="china-s", fontsize=11)
    doc.save(str(path))
    doc.close()


class SymbolPositionPdfTests(unittest.TestCase):
    def prepare(self, lines: list[tuple[int, float, str]] | None) -> tuple[Path, object]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp = Path(temporary.name)
        (tmp / "论文").mkdir()
        # 源码定义完整行集合，不能仅凭PDF问题一之前存在几行中文就通过。
        source = r"\documentclass{gmcmthesis}\subsection{符号说明}\begin{tabular}{cc}符号 & 意义\\ r & 卫星位置矢量，单位 km\\ N & 光子总数\\\end{tabular}"
        (tmp / "论文" / "main.tex").write_text(source, encoding="utf-8")
        if lines is not None:
            make_pdf(tmp / "论文" / "main.pdf", lines)
        return tmp, load_template_module()

    def test_correct_order_passes(self):
        lines = [
            (1, 80, "1 问题重述"),
            (1, 200, "1.1 模型假设"),
            (1, 300, "2 模型假设与符号说明"),
            (1, 380, "2.1 模型假设"),
            (1, 460, "2.2 符号说明"),
            (1, 520, "符号 意义"),
            (1, 560, "r 卫星位置矢量，单位 km"),
            (1, 700, "N 光子总数"),
            (2, 120, "3 问题一模型建立与求解"),
        ]
        project, module = self.prepare(lines)
        errors: list[str] = []
        module.check_symbol_position_pdf(project, errors)
        self.assertEqual(errors, [])

    def test_inverted_order_fails(self):
        lines = [
            (1, 80, "符号 意义"),
            (1, 120, "P 降水量，mm/日"),
            (1, 300, "2.2 符号说明"),
            (1, 420, "3 问题一模型建立与求解"),
        ]
        project, module = self.prepare(lines)
        errors: list[str] = []
        module.check_symbol_position_pdf(project, errors)
        # 表浮到标题上方时要么报顺序错误、要么因锚点缺失进入需人工核对；
        # 无论哪种路径都必须失败，不得自动通过。
        self.assertTrue(errors, "倒置场景不得静默通过")

    def test_last_symbol_row_after_problem_one_fails(self):
        lines = [(1, 80, "2.1 模型假设"), (1, 120, "2.2 符号说明"),
                 (1, 160, "符号 意义"), (1, 200, "r 卫星位置矢量，单位 km"),
                 (1, 240, "3 问题一模型建立与求解"), (1, 280, "N 光子总数")]
        project, module = self.prepare(lines)
        errors = []
        module.check_symbol_position_pdf(project, errors)
        self.assertTrue(any("阅读顺序错误" in error for error in errors), errors)

    def test_newer_input_invalidates_old_pdf(self):
        project, module = self.prepare([(1, 80, "无关页面")])
        paper = project / "论文"
        (paper / "main.tex").write_text(r"\input{symbols}", encoding="utf-8")
        (paper / "symbols.tex").write_text("更新内容", encoding="utf-8")
        pdf_time = (paper / "main.pdf").stat().st_mtime
        os.utime(paper / "main.tex", (pdf_time - 5, pdf_time - 5))
        os.utime(paper / "symbols.tex", (pdf_time + 5, pdf_time + 5))
        errors = []
        module.check_symbol_position_pdf(project, errors)
        self.assertTrue(any("symbols.tex" in error and "旧输出" in error for error in errors), errors)

    def test_missing_pdf_fails(self):
        project, module = self.prepare(None)
        errors: list[str] = []
        module.check_symbol_position_pdf(project, errors)
        self.assertTrue(any("main.pdf" in e for e in errors))

    def test_unextractable_pdf_requests_manual_review(self):
        project, module = self.prepare([(1, 100, "空页面 无锚点")])
        errors: list[str] = []
        module.check_symbol_position_pdf(project, errors)
        self.assertTrue(any(e.startswith("需人工视觉核对") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
