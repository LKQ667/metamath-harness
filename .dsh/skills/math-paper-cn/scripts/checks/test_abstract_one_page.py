#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from check_abstract_one_page import LABEL, validate_abstract


def paper(chars: int, *, keyword: bool = True) -> str:
    suffix = "关键词：模型；优化" if keyword else ""
    return "{\\sectiontitlefont 摘要}\n" + ("甲" * chars) + "\n" + suffix + LABEL


class AbstractOnePageTests(unittest.TestCase):
    def test_accepts_full_first_page_abstract(self) -> None:
        errors, details = validate_abstract(
            paper(900),
            r"\newlabel{abstract:end}{{}{1}}",
        )
        self.assertEqual(errors, [])
        self.assertEqual(details["end_page"], "1")

    def test_rejects_second_page_even_when_length_is_good(self) -> None:
        errors, _ = validate_abstract(
            paper(900),
            r"\newlabel{abstract:end}{{}{2}}",
        )
        self.assertTrue(any("第 2 页" in error for error in errors))

    def test_rejects_underfilled_abstract(self) -> None:
        errors, _ = validate_abstract(
            paper(300),
            r"\newlabel{abstract:end}{{}{1}}",
        )
        self.assertTrue(any("最低要求" in error for error in errors))

    def test_requires_end_marker_after_keywords(self) -> None:
        errors, _ = validate_abstract(
            "{\\sectiontitlefont 摘要}" + ("甲" * 900) + LABEL + "关键词：模型",
            r"\newlabel{abstract:end}{{}{1}}",
        )
        self.assertTrue(any("关键词之后" in error for error in errors))

    def test_rejects_ambiguous_abstract_heading(self) -> None:
        errors, _ = validate_abstract(
            "摘要\n" + ("甲" * 900) + "\n关键词：模型" + LABEL,
            r"\newlabel{abstract:end}{{}{1}}",
        )
        self.assertTrue(any("未找到摘要区域" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
