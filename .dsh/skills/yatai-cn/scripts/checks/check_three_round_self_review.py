#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the required three-round self review report."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report


def contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(item in text for item in candidates)


def main() -> int:
    parser = project_arg("检查最终交付前必须完成三轮全链路自查")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    review_path = project / "检查结果" / "三轮自查.md"
    errors: list[str] = []

    if not review_path.exists():
        errors.append(f"缺少三轮自查文件: {review_path}")
        return write_report(False, "check_three_round_self_review", errors, args.output)

    text = read_text(review_path)
    required = [
        ("第一轮", ("第一轮", "第1轮"), "内容与数据链"),
        ("第二轮", ("第二轮", "第2轮"), "论文与版式链"),
        ("第三轮", ("第三轮", "第3轮"), "代码与复现链"),
    ]
    for label, aliases, chain in required:
        if not contains_any(text, aliases):
            errors.append(f"三轮自查缺少{label}记录。")
        if chain not in text:
            errors.append(f"三轮自查缺少“{chain}”检查结论。")
    for item in (
        "正文符号",
        "支撑材料目录",
        "摘要页",
        "普通柱状图必要性",
        "顶刊一区中文三维图可行性评估",
        "正文页数是否达标",
    ):
        if item not in text:
            errors.append(f"三轮自查缺少“{item}”新增门禁检查结论。")
    abstract_review = (
        ("摘要一页内", ("一页", "第一页")),
        ("摘要尽量写满", ("写满", "800-1000")),
        ("摘要结束标记", ("abstract:end",)),
        ("摘要编译页码复核", ("编译页码", "页码复核", "main.aux")),
    )
    for label, tokens in abstract_review:
        if not contains_any(text, tokens):
            errors.append(f"三轮自查缺少“{label}”检查证据。")
    if not contains_any(text, ("最终通过", "全部通过", "三轮均通过", "通过结论")):
        errors.append("三轮自查缺少最终通过结论。")

    return write_report(not errors, "check_three_round_self_review", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
