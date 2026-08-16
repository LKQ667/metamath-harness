#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""yatai-cn 强调门禁的独立回归测试。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check_paper_emphasis.py")
GOOD_TEX = r"""
\begin{document}
{\sectiontitlefont 摘要}
\paperstrong{针对问题一}，基于权威数据建立\paperstrong{组合优化模型}，由约束关系确定可行域，并使用独立样本检验求解结果。计算表明模型在给定边界内保持稳定，最终得到\paperstrong{目标值为 12.5}。
{\keywordfont \paperstrong{关键词：}} \paperstrong{组合优化}；\paperstrong{灵敏度分析}\label{abstract:end}
\newpage
\section{问题重述}
正文使用权威数据、变量、公式和结果解释推进论证。该段保留足够的普通文字，用于确认少量关键短语强调不会被误判。模型的核心判据为\paperstrong{误差不超过 2\%}，其余内容保持普通字重。
\begin{thebibliography}{9}
\bibitem{x} 测试文献
\end{thebibliography}
\label{body:end}
\end{document}
"""


class PaperEmphasisTests(unittest.TestCase):
    def run_case(self, tex: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="yatai-paper-emphasis-") as tmp:
            paper = Path(tmp) / "论文"
            paper.mkdir()
            (paper / "main.tex").write_text(tex, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--project", tmp],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )

    def test_valid_selective_emphasis_passes(self) -> None:
        self.assertEqual(self.run_case(GOOD_TEX).returncode, 0)

    def test_problem_label_must_be_isolated(self) -> None:
        bad = GOOD_TEX.replace(r"\paperstrong{针对问题一}", r"\paperstrong{针对问题一，基于权威数据建立}")
        self.assertNotEqual(self.run_case(bad).returncode, 0)

    def test_each_keyword_must_be_bold(self) -> None:
        bad = GOOD_TEX.replace(r"\paperstrong{组合优化}；", "组合优化；")
        self.assertNotEqual(self.run_case(bad).returncode, 0)

    def test_full_sentence_bold_is_rejected(self) -> None:
        bad = GOOD_TEX.replace(r"\paperstrong{目标值为 12.5}", r"\paperstrong{目标值为 12.5。}")
        self.assertNotEqual(self.run_case(bad).returncode, 0)

    def test_full_sentence_with_external_period_is_rejected(self) -> None:
        bad = GOOD_TEX.replace(
            "正文使用权威数据、变量、公式和结果解释推进论证。",
            r"\paperstrong{正文使用权威数据、变量、公式和结果解释推进论证}。",
        )
        result = self.run_case(bad)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("完整句", result.stdout)


if __name__ == "__main__":
    unittest.main()
