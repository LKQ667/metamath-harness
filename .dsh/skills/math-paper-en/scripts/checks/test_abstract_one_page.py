#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression tests for the COMAP Summary Sheet gate."""

from __future__ import annotations

import unittest

from check_abstract_one_page import LABEL, SUMMARY_TITLE_MARKER, validate_summary


def paper(words: int, keyword: bool = True) -> str:
    body = " ".join(["result"] * words)
    suffix = "Keywords: model; optimization" if keyword else ""
    return SUMMARY_TITLE_MARKER + "\n" + body + "\n" + suffix + LABEL


AUX_PAGE_ONE = r"\newlabel{abstract:end}{{}{1}}"
AUX_PAGE_TWO = r"\newlabel{abstract:end}{{}{2}}"


class SummarySheetTests(unittest.TestCase):
    def test_accepts_full_first_page_summary(self) -> None:
        errors, details = validate_summary(paper(400), AUX_PAGE_ONE)
        self.assertEqual(errors, [])
        self.assertEqual(details["end_page"], "1")

    def test_rejects_second_page_even_when_length_is_good(self) -> None:
        errors, _ = validate_summary(paper(400), AUX_PAGE_TWO)
        self.assertTrue(any("第 2 页" in error for error in errors))

    def test_rejects_underfilled_summary(self) -> None:
        errors, _ = validate_summary(paper(100), AUX_PAGE_ONE)
        self.assertTrue(any("最低要求" in error for error in errors))

    def test_requires_end_marker_after_keywords(self) -> None:
        tex = SUMMARY_TITLE_MARKER + " ".join(["result"] * 400) + LABEL + " Keywords: model"
        errors, _ = validate_summary(tex, AUX_PAGE_ONE)
        self.assertTrue(any("Keywords" in error for error in errors))

    def test_rejects_ambiguous_summary_heading(self) -> None:
        tex = "Summary\n" + " ".join(["result"] * 400) + "\nKeywords: model" + LABEL
        errors, _ = validate_summary(tex, AUX_PAGE_ONE)
        self.assertTrue(any("未找到" in error for error in errors))

    def test_rejects_cjk_in_summary(self) -> None:
        tex = SUMMARY_TITLE_MARKER + "本文 " + " ".join(["result"] * 400) + " Keywords: model" + LABEL
        errors, _ = validate_summary(tex, AUX_PAGE_ONE)
        self.assertTrue(any("中文字符" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
