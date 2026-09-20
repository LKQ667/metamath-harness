#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查图/表是否全篇连续编号（图1、图2、表1、表2，不使用章节复合编号）。

识别对象是真实 figure/table 浮动体内的 \\label（经 input/include 展开后的完整论文），
而不是依赖 fig:/tab: 前缀约定：任意合法 label 不漏、一图多 label 只算一个浮动体；
浮动体内有 caption 无 label 等无法确定的情况列入 review_required 待核对，不默默跳过。"""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


COUNTERWITHOUT = re.compile(
    r"\\counterwithout\s*\{\s*(figure|table)\s*\}\s*\{\s*section\s*\}"
)
NUMBERWITHIN = re.compile(
    r"(?<!\\)\\numberwithin\s*\{\s*(figure|table)\s*\}\s*\{\s*section\s*\}"
)
NUMBERWITHIN_BY_TYPE = re.compile(
    r"\\@addtoreset\s*\{\s*(figure|table)\s*\}\s*\{\s*section\s*\}"
)
COMPOSITE_NUMBER = re.compile(r"^\d+\.\d+")
FLOAT_RE = re.compile(r"\\begin\{(figure\*?|table\*?)\}.*?\\end\{\1\}", re.DOTALL)
LABEL_RE = re.compile(r"\\label\{([^{}]+)\}")
CAPTION_RE = re.compile(r"\\caption\*?\s*[\[{]")


def strip_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def newlabel_numbers(aux_text: str) -> dict[str, str]:
    """从 main.aux 收集 label → 编译后编号。"""
    numbers: dict[str, str] = {}
    pattern = re.compile(r"\\newlabel\{([^{}]+)\}\{\{([^{}]*)\}\{(\d+)\}")
    for match in pattern.finditer(aux_text):
        label, number = match.group(1), match.group(2)
        if number:
            numbers[label] = number
    return numbers


def float_labels(tex_text: str) -> dict[str, list[list[str]]]:
    """按出现顺序收集 figure/table 浮动体内的 label 分组（一组=一个浮动体）。"""
    groups: dict[str, list[list[str]]] = {"figure": [], "table": []}
    for match in FLOAT_RE.finditer(tex_text):
        kind = "figure" if match.group(1).startswith("figure") else "table"
        labels = LABEL_RE.findall(match.group(0))
        if labels:
            groups[kind].append(labels)
    return groups


def main() -> int:
    parser = project_arg("检查图/表全篇连续编号，禁止章节复合编号")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    review_required: list[str] = []

    main_tex = project / "论文" / "main.tex"
    cls_path = project / "论文" / "gmcmthesis.cls"
    if not main_tex.exists():
        errors.append(f"缺少论文主文件: {main_tex}")
        return write_report(False, "check_figure_table_numbering", errors, args.output)

    main_text = strip_comments(read_text(main_tex))
    cls_text = strip_comments(read_text(cls_path)) if cls_path.exists() else ""
    overridden = {match.group(1) for match in COUNTERWITHOUT.finditer(main_text)}
    for kind, name in (("figure", "图"), ("table", "表")):
        if kind not in overridden:
            errors.append(
                f"论文/main.tex 缺少 `\\counterwithout{{{kind}}}{{section}}`，{name}编号会随章节重置为 {name}1.1 形式。"
            )

    # 官方 class 的 \numberwithin 属模板原生行为，由 main.tex 的 \counterwithout 覆盖；
    # 只有 class 被改写（不再保留官方计数方式）时才提示，保持 class 可替换可升级。
    if cls_text and not NUMBERWITHIN.search(cls_text):
        errors.append(
            "论文/gmcmthesis.cls 已不再保留 figure/table 对 section 的 `\\numberwithin`；"
            "请恢复官方 class，编号覆盖只写在 main.tex。"
        )

    aux_path = project / "论文" / "main.aux"
    if not aux_path.exists():
        errors.append("缺少 `论文/main.aux`，无法核对编译后的图表编号；请先编译再重跑本检查。")
    else:
        aux_numbers = newlabel_numbers(read_text(aux_path))
        groups = float_labels(main_text)
        for kind, name in (("figure", "图"), ("table", "表")):
            values: list[str] = []
            for labels in groups[kind]:
                numbers = {label: aux_numbers[label] for label in labels if label in aux_numbers}
                if not numbers:
                    review_required.append(
                        f"一个 {name} 浮动体的 label {labels} 在 main.aux 中无编译记录（可能未编译或 label 未解析），请核对。"
                    )
                    continue
                distinct = set(numbers.values())
                if len(distinct) > 1:
                    errors.append(
                        f"同一 {name} 浮动体内多个 label 得到不同编号 {numbers}；请检查 label 放置位置。"
                    )
                values.append(numbers[labels[0]] if labels[0] in numbers else next(iter(numbers.values())))
            if groups[kind] and values:
                composite = sorted({value for value in values if COMPOSITE_NUMBER.match(value)})
                if composite:
                    errors.append(
                        f"编译后的{name}编号出现章节复合编号 {'、'.join(composite)}；"
                        f"{name}必须全篇连续编号为 {name}1、{name}2…"
                    )
                expected = [str(index) for index in range(1, len(values) + 1)]
                if values != expected:
                    errors.append(
                        f"编译后的{name}编号不连续或有重复: {'、'.join(values)}；期望 {'、'.join(expected)}。"
                    )
            # aux 中带常见前缀但不在任何浮动体内的 label：列待核对，不默默跳过
            prefix = "fig" if kind == "figure" else "tab"
            for label, number in aux_numbers.items():
                if re.match(rf"^(fig|figure|图)[:._-]", label, re.IGNORECASE) and kind == "figure":
                    if not any(label in group for group in groups["figure"]):
                        review_required.append(f"aux 中 {prefix} 前缀 label `{label}`（编号 {number}）未在任何 figure 浮动体内找到，请核对其身份。")
                elif re.match(r"^(tab|table|表)[:._-]", label, re.IGNORECASE) and kind == "table":
                    if not any(label in group for group in groups["table"]):
                        review_required.append(f"aux 中 {prefix} 前缀 label `{label}`（编号 {number}）未在任何 table 浮动体内找到，请核对其身份。")
            # 有 caption 无 label 的浮动体
            for match in FLOAT_RE.finditer(main_text):
                kind_match = "figure" if match.group(1).startswith("figure") else "table"
                if kind_match != kind:
                    continue
                if CAPTION_RE.search(match.group(0)) and not LABEL_RE.search(match.group(0)):
                    review_required.append(f"一个 {name} 浮动体含 caption 但无 label，无法核对其编译编号，请补充 \\label 或人工核对。")

    return write_report(
        not errors,
        "check_figure_table_numbering",
        errors,
        args.output,
        {"counterwithout": sorted(overridden), "review_required": review_required},
    )


if __name__ == "__main__":
    raise SystemExit(main())
