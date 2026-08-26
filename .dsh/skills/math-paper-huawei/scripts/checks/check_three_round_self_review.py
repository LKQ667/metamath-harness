#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the required three-round self review report."""

from __future__ import annotations

import re
from pathlib import Path

from common import aux_label_page, project_arg, read_text, write_report


def contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(item in text for item in candidates)


def review_page(text: str, label: str) -> int | None:
    match = re.search(rf"{re.escape(label)}\s*[:：]\s*(\d+)", text)
    return int(match.group(1)) if match else None


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
        "正文章节白名单",
        "废话主章节清理",
        "模型建立与求解深化证据",
        "普通柱状图必要性",
        "顶刊一区中文三维图可行性评估",
        "正文页数是否达标",
    ):
        if item not in text:
            errors.append(f"三轮自查缺少“{item}”新增门禁检查结论。")
    abstract_review = (
        ("摘要不超过两页", ("两页", "不超过两页")),
        ("摘要字数达标", ("800", "850-1050")),
        ("摘要结束标记", ("abstract:end",)),
        ("摘要编译页码复核", ("编译页码", "页码复核", "main.aux")),
    )
    for label, tokens in abstract_review:
        if not contains_any(text, tokens):
            errors.append(f"三轮自查缺少“{label}”检查证据。")
    model_review = (
        ("模型推导循序渐进", ("循序渐进", "公式推导", "推导链")),
        ("模型结论有条理", ("有条理", "结果解释", "结论推进")),
        ("页数不足只深化五章", ("只深化", "模型建立与求解", "不新增主章节")),
    )
    for label, tokens in model_review:
        if not contains_any(text, tokens):
            errors.append(f"三轮自查缺少“{label}”检查证据。")
    page_labels = ("正文起始页", "正文结束页", "附录起始页", "正文实际页数")
    pages = {label: review_page(text, label) for label in page_labels}
    for label, value in pages.items():
        if value is None:
            errors.append(f"三轮自查缺少“{label}：数字”证据。")
    for phrase in ("参考文献计入正文", "支撑材料目录与代码附录排除", "附录另起页"):
        if phrase not in text:
            errors.append(f"三轮自查缺少“{phrase}”正文边界结论。")
    for phrase in (
        "自然衔接",
        "句式长短变化",
        "括号密度",
        "第一人称必要性",
        "模板摘要示例与实际论文通过文风门禁",
        "真实源代码未修改",
        "局部改名边界正确",
        "注释与空行已清理",
        "代码结构已复核",
        "原版与净化版运行结果一致",
    ):
        if phrase not in text:
            errors.append(f"三轮自查缺少“{phrase}”新增复核证据。")
    if all(value is not None for value in pages.values()):
        start = pages["正文起始页"]
        end = pages["正文结束页"]
        appendix = pages["附录起始页"]
        actual = pages["正文实际页数"]
        assert start is not None and end is not None and appendix is not None and actual is not None
        if start != 1:
            errors.append("三轮自查记录的正文起始页必须为 1。")
        if actual != end - start + 1:
            errors.append("三轮自查记录的正文实际页数与起止页计算不一致。")
        if appendix != end + 1:
            errors.append("三轮自查记录的附录起始页必须等于正文结束页加 1。")
        aux_path = project / "论文" / "main.aux"
        if not aux_path.exists():
            errors.append("缺少 `论文/main.aux`，无法核对三轮自查中的正文边界页码。")
        else:
            aux = read_text(aux_path)
            expected = {
                "正文起始页": aux_label_page(aux, "body:start"),
                "正文结束页": aux_label_page(aux, "body:end"),
                "附录起始页": aux_label_page(aux, "appendix:start"),
            }
            for label, aux_page in expected.items():
                if aux_page is None:
                    errors.append(f"`论文/main.aux` 缺少与“{label}”对应的页码标记。")
                elif pages[label] != aux_page:
                    errors.append(f"三轮自查记录的{label}为 {pages[label]}，与编译页码 {aux_page} 不一致。")
    if not contains_any(text, ("最终通过", "全部通过", "三轮均通过", "通过结论")):
        errors.append("三轮自查缺少最终通过结论。")

    return write_report(not errors, "check_three_round_self_review", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
