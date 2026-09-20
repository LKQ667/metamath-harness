#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression tests for the English emphasis gate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check_paper_emphasis.py")
BODY_WORDS = " ".join(["reproducible"] * 140)
GOOD_TEX = r"""
\begin{document}
{\sectiontitlefont Summary}
\paperstrong{For Problem 1} we fit a queueing model and report the optimum.
\paperstrong{For Problem 2} we calibrate the demand factor against the observed series.
{\keywordfont \paperstrong{Keywords:}} \paperstrong{queueing}; \paperstrong{calibration}; \paperstrong{robustness}\label{abstract:end}
\newpage
\section{Introduction}
""" + BODY_WORDS + r""" The decisive criterion is \paperstrong{waiting time below four minutes} and the final plan is \paperstrong{Plan B}, while all remaining text keeps the normal weight so the density check stays satisfied.
\begin{thebibliography}{9}
\bibitem{x} test reference
\end{thebibliography}
\label{body:end}
\end{document}
"""


class EnglishEmphasisTests(unittest.TestCase):
    def run_case(self, tex: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory(prefix="math-paper-emphasis-en-") as tmp:
            paper_dir = Path(tmp) / "论文"
            paper_dir.mkdir()
            (paper_dir / "main.tex").write_text(tex, encoding="utf-8")
            (Path(tmp) / "项目状态.json").write_text(json.dumps({"question_count": 2}), encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--project", tmp],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                env=env,
            )

    def test_valid_selective_emphasis_passes(self) -> None:
        result = self.run_case(GOOD_TEX)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_each_keyword_must_be_bold(self) -> None:
        bad = GOOD_TEX.replace(r"\paperstrong{calibration}; ", "calibration; ")
        self.assertNotEqual(self.run_case(bad).returncode, 0)

    def test_full_sentence_bold_is_rejected(self) -> None:
        bad = GOOD_TEX.replace(
            r"\paperstrong{Plan B}",
            r"\paperstrong{We recommend implementing Plan B in every district of the city during the first quarter of next year.}",
        )
        result = self.run_case(bad)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("完整句", result.stdout)

    def test_cjk_inside_bold_is_rejected(self) -> None:
        bad = GOOD_TEX.replace(r"\paperstrong{Plan B}", r"\paperstrong{方案 B}")
        result = self.run_case(bad)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("中文", result.stdout)


if __name__ == "__main__":
    unittest.main()
