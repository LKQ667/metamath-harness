#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_figure_table_numbering.py")
CLASS_STUB = "\\numberwithin{figure}{section}\n\\numberwithin{table}{section}\n"


def run_gate(project: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project", str(project)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    return json.loads(proc.stdout)


def tex_floats(labels_by_kind: dict[str, list[str]]) -> str:
    parts = ["\\begin{document}\n"]
    for kind, labels in labels_by_kind.items():
        for label in labels:
            if kind == "figure":
                parts.append(f"\\begin{{figure}}\\includegraphics{{a}}\\caption{{x}}\\label{{{label}}}\\end{{figure}}\n")
            else:
                parts.append(f"\\begin{{table}}\\caption{{x}}\\label{{{label}}}\\end{{table}}\n")
    parts.append("\\end{document}\n")
    return "".join(parts)


def aux_labels(pairs: list[tuple[str, str]]) -> str:
    return "".join(f"\\newlabel{{{label}}}{{{{{number}}}{{1}}}}\n" for label, number in pairs)


class FigureTableNumberingTests(unittest.TestCase):
    def build(self, main_tex: str, aux: str | None, cls: str = CLASS_STUB) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        project = Path(tmp.name)
        paper = project / "论文"
        paper.mkdir(parents=True)
        (paper / "main.tex").write_text(main_tex, encoding="utf-8")
        (paper / "gmcmthesis.cls").write_text(cls, encoding="utf-8")
        if aux is not None:
            (paper / "main.aux").write_text(aux, encoding="utf-8")
        return project

    def test_rejects_class_composite_numbering(self):
        project = self.build(
            "\\documentclass{gmcmthesis}\n\\begin{document}\n\\end{document}\n",
            "\\newlabel{fig:a}{{1.1}{1}}\n\\newlabel{fig:b}{{2.1}{3}}\n\\newlabel{tab:a}{{1.2}{2}}\n",
        )
        report = run_gate(project)
        self.assertFalse(report["ok"])
        self.assertTrue(any("counterwithout" in error for error in report["errors"]))

    def test_accepts_continuous_numbering(self):
        tex = (
            "\\documentclass{gmcmthesis}\n\\usepackage{chngcntr}\n"
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            + tex_floats({"figure": ["fig:a", "fig:b"], "table": ["tab:a", "tab:b"]})
        )
        aux = aux_labels([("fig:a", "1"), ("fig:b", "2"), ("tab:a", "1"), ("tab:b", "2")])
        report = run_gate(self.build(tex, aux))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(sorted(report["details"]["counterwithout"]), ["figure", "table"])

    def test_accepts_arbitrary_label_names_in_floats(self):
        # 任意合法 label 不因前缀约定被漏掉或误算
        tex = (
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            + tex_floats({"figure": ["res:main-result", "res:second"]})
        )
        aux = aux_labels([("res:main-result", "1"), ("res:second", "2")])
        report = run_gate(self.build(tex, aux))
        self.assertTrue(report["ok"], report["errors"])

    def test_multiple_labels_same_float_count_once(self):
        # 一图多 label 只算一个浮动体，编号必须一致
        tex = (
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            "\\begin{document}\n"
            "\\begin{figure}\\caption{x}\\label{fig:a}\\label{alias:a}\\end{figure}\n"
            "\\end{document}\n"
        )
        aux = aux_labels([("fig:a", "1"), ("alias:a", "1")])
        report = run_gate(self.build(tex, aux))
        self.assertTrue(report["ok"], report["errors"])

    def test_multiple_labels_same_float_conflicting_numbers_fail(self):
        tex = (
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            "\\begin{document}\n"
            "\\begin{figure}\\caption{x}\\label{fig:a}\\label{alias:a}\\end{figure}\n"
            "\\end{document}\n"
        )
        aux = aux_labels([("fig:a", "1"), ("alias:a", "2")])
        report = run_gate(self.build(tex, aux))
        self.assertFalse(report["ok"])
        self.assertTrue(any("不同编号" in error for error in report["errors"]))

    def test_caption_without_label_lists_review_required(self):
        # 有 caption 无 label：待核对而不是失败或静默
        tex = (
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            "\\begin{document}\n"
            "\\begin{figure}\\caption{x}\\label{fig:a}\\end{figure}\n"
            "\\begin{figure}\\caption{y}\\end{figure}\n"
            "\\end{document}\n"
        )
        aux = aux_labels([("fig:a", "1")])
        report = run_gate(self.build(tex, aux))
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(any("无 label" in item for item in report["details"]["review_required"]))

    def test_rejects_non_continuous_sequence(self):
        tex = (
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            + tex_floats({"figure": ["fig:a", "fig:b"]})
        )
        aux = aux_labels([("fig:a", "1"), ("fig:b", "3")])
        report = run_gate(self.build(tex, aux))
        self.assertFalse(report["ok"])
        self.assertTrue(any("不连续" in error for error in report["errors"]))

    def test_aux_prefix_label_outside_float_is_review_not_error(self):
        # 无浮动体证据的 fig: 前缀 label：报待核对，不默默跳过也不凭空失败
        tex = (
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            "\\begin{document}\n\\end{document}\n"
        )
        aux = aux_labels([("fig:a", "1"), ("fig:b", "3")])
        report = run_gate(self.build(tex, aux))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(len(report["details"]["review_required"]), 2)

    def test_requires_aux_for_compiled_check(self):
        project = self.build("\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n", None)
        report = run_gate(project)
        self.assertFalse(report["ok"])
        self.assertTrue(any("main.aux" in error for error in report["errors"]))

    def test_equation_and_commented_lines_are_ignored(self):
        project = self.build(
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n"
            "% \\numberwithin{figure}{section}\n"
            "\\numberwithin{equation}{section}\n",
            "\\newlabel{eq:a}{{1.1}{1}}\n\\newlabel{fig:a}{{1}{2}}\n",
        )
        report = run_gate(project)
        self.assertTrue(report["ok"], report["errors"])

    def test_flags_modified_class(self):
        project = self.build(
            "\\counterwithout{figure}{section}\n\\counterwithout{table}{section}\n",
            "",
            cls="\\ProvidesClass{gmcmthesis}\n",
        )
        report = run_gate(project)
        self.assertFalse(report["ok"])
        self.assertTrue(any("官方 class" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
