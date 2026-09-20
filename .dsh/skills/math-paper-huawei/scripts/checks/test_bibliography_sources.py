#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CHECK = Path(__file__).with_name("check_bibliography_sources.py")


def run_check(entries: list[str], source_map: bool = True, body_refs: str = "") -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "论文").mkdir()
        (project / "文献").mkdir()
        if source_map:
            (project / "文献" / "source_map.md").write_text(
                "# 文献来源映射\n\n来源链接、可信等级、支撑章节见下表。\n", encoding="utf-8"
            )
        bib = "\n".join(f"\\bibitem{{ref{index}}} {entry}" for index, entry in enumerate(entries, 1))
        (project / "论文" / "main.tex").write_text(
            "\\documentclass[bwprint]{gmcmthesis}\n\\begin{document}\n"
            "\\begin{thebibliography}{9}\n" + bib + "\n\\end{thebibliography}\n"
            f"{body_refs}\n\\end{{document}}\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(CHECK), "--project", str(project)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return json.loads(proc.stdout)


class BibliographySourceTests(unittest.TestCase):
    def test_rejects_competition_format_specification(self):
        report = run_check(
            ["全国大学生数学建模竞赛论文格式规范，全国大学生数学建模竞赛组委会，2024。"]
        )
        self.assertFalse(report["ok"])
        self.assertTrue(any("赛事合规资料" in item["kind"] for item in report["details"]["rejected"]))

    def test_rejects_generic_textbook(self):
        report = run_check(["姜启源，谢金星，叶俊. 数学模型（第5版）. 北京：高等教育出版社，2018. ISBN 9787040493863."])
        self.assertFalse(report["ok"])
        self.assertTrue(any("通用数学建模教材" in item["kind"] for item in report["details"]["rejected"]))

    def test_allows_tech_standard(self):
        report = run_check(["ASTM D4236-94(2021) Standard Practice for Labeling Art Materials. ASTM International, 2021."])
        self.assertTrue(report["ok"], report["errors"])

    def test_allows_gb_t_standard(self):
        report = run_check(["GB/T 7714-2015 信息与文献 参考文献著录规则. 中国标准出版社, 2015."])
        self.assertTrue(report["ok"], report["errors"])

    def test_allows_journal_paper_with_doi(self):
        report = run_check(["Zhang L, Wang H. Channel access modelling for dense WLAN. IEEE Transactions on Wireless Communications, 2023, 22(4): 2501-2515. DOI: 10.1109/TWC.2023.1234567."])
        self.assertTrue(report["ok"], report["errors"])

    def test_allows_journal_paper_mentioning_mathematical_model(self):
        report = run_check(["Li M. A mathematical model of queueing delay in 802.11 networks. Journal of Network Theory, 2021, 9(2): 1-20. DOI: 10.1000/jnt.2021.0201."])
        self.assertTrue(report["ok"], report["errors"])

    def test_source_map_fields_required(self):
        report = run_check(["GB/T 7714-2015 信息与文献 参考文献著录规则. 中国标准出版社, 2015."], source_map=False)
        self.assertFalse(report["ok"])
        self.assertTrue(any("source_map" in error for error in report["errors"]))

    def test_multiple_entries_isolate_offender(self):
        report = run_check(
            [
                "GB/T 7714-2015 信息与文献 参考文献著录规则. 中国标准出版社, 2015.",
                "姜启源. 数学模型（第5版）. 高等教育出版社，2018. ISBN 9787040493863.",
            ]
        )
        self.assertFalse(report["ok"])
        rejected = report["details"]["rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["index"], 2)

    def test_rejects_spaced_screenshot_edition(self):
        # B01/R06：用户截图中“数学模型. 第 5 版. … ISBN …”带空格版次同样拒绝
        report = run_check(["司守奎. 数学模型. 第 5 版. 北京: 国防工业出版社, 2021. ISBN 9787118122114."])
        self.assertFalse(report["ok"])
        self.assertTrue(any(item["kind"] == "通用数学建模教材" for item in report["details"]["rejected"]))

    def test_rejects_chinese_numeral_edition(self):
        report = run_check(["数学建模方法与分析. 第五版. 高等教育出版社, 2020. ISBN 9787040532118."])
        self.assertFalse(report["ok"])
        self.assertTrue(any(item["kind"] == "通用数学建模教材" for item in report["details"]["rejected"]))

    def test_entry_without_source_signal_fails_even_with_appendix_standard(self):
        # B04/R07：无来源 bibitem 失败；末条后的附录标准号不为其背书
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "论文").mkdir()
            (project / "文献").mkdir()
            (project / "文献" / "source_map.md").write_text(
                "# 文献来源映射\n\n来源链接、可信等级、支撑章节见下表。\n", encoding="utf-8"
            )
            (project / "论文" / "main.tex").write_text(
                "\\documentclass[bwprint]{gmcmthesis}\n\\begin{document}\n"
                "\\begin{thebibliography}{9}\n\\bibitem{refA} 某作者. 某研究. 2024.\n\\end{thebibliography}\n"
                "附录：本方法遵循 GB/T 7714-2015 标准。\n\\end{document}\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            report = json.loads(proc.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(any("refA" in error for error in report["errors"]))
            self.assertEqual(report["details"]["bibitem_count"], 1)

    def test_unclosed_bibliography_environment_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "论文").mkdir()
            (project / "文献").mkdir()
            (project / "文献" / "source_map.md").write_text(
                "# 文献来源映射\n\n来源链接、可信等级、支撑章节见下表。\n", encoding="utf-8"
            )
            (project / "论文" / "main.tex").write_text(
                "\\documentclass[bwprint]{gmcmthesis}\n\\begin{document}\n"
                "\\begin{thebibliography}{9}\n\\bibitem{refA} Zhang L. Model study. IEEE Trans, 2023. DOI: 10.1/x.\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(CHECK), "--project", str(project)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            report = json.loads(proc.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(any("\\end{thebibliography}" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
