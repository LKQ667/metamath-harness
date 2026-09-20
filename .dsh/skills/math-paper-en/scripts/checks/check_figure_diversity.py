#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check cross-question figure-type diversity for the English competition paper.

硬规则：
1. 每个小问的数据图必须声明 chart_family，且同一 chart_family 不得跨问重复；
2. 同一个小问内默认也不允许重复同一 chart_family，除非条目写明 repeat_exception；
3. 热力图家族全文最多一张，柱状图家族全文最多一张且必须写明 bar_exception；
4. 每个小问至少有一张数据图，或在 manifest / Q*/result.md 写明不出图理由；
5. 全文不重复的图型数量不得少于小问数。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from common import load_manifest_items, project_arg, read_text, write_report


BS = chr(92)
QUESTION_RE = re.compile(r"(?:^|[" + BS + r"/])Q(\d+)(?:[" + BS + r"/]|$)", re.I)
NON_DATA_FAMILIES = {
    "flowchart", "roadmap", "process", "diagram", "schematic", "concept",
    "concept_prompt", "illustration", "architecture",
}
HEATMAP_FAMILIES = {"heatmap", "grid_heatmap", "sobol_heatmap", "matrix_heatmap"}
BAR_FAMILIES = {"bar", "barh", "column", "stacked_bar", "vertical_bar", "grouped_bar"}
NO_FIGURE_TOKENS = ("不出图理由", "no figure reason", "no_figure", "不出图")


def normalize_family(value: object) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[\s\-]+", "_", text)


def state_question_count(project: Path) -> int:
    path = project / "项目状态.json"
    if not path.exists():
        return 0
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    value = state.get("question_count") if isinstance(state, dict) else None
    return value if isinstance(value, int) and value > 0 else 0


def item_question(item: dict) -> str | None:
    for key in ("question", "question_id", "qid", "problem", "problem_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            match = QUESTION_RE.search(text) or re.fullmatch(r"[Qq]?(\d+)", text)
            return "Q" + match.group(1) if match else text
    source = str(item.get("source", ""))
    match = QUESTION_RE.search(source)
    return "Q" + match.group(1) if match else None


def has_no_figure_reason(project: Path, question: str) -> bool:
    root = project / question
    if not root.exists():
        return False
    for path in root.rglob("*.md"):
        text = read_text(path)
        if any(token in text for token in NO_FIGURE_TOKENS):
            return True
    return False


def main() -> int:
    parser = project_arg("检查跨问 Python 图型多样性、热力图与柱状图上限")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    if manifest_errors and not items:
        return write_report(False, "check_figure_diversity", errors, args.output)

    by_question: dict[str, dict[str, list[str]]] = {}
    heatmaps: list[str] = []
    bars: list[str] = []
    data_count = 0

    for item in items:
        family = normalize_family(item.get("chart_family"))
        source = str(item.get("source", ""))
        if not family:
            errors.append(f"数据图缺少 chart_family，无法核对图型多样性: {source or item}")
            continue
        if family in NON_DATA_FAMILIES or item.get("non_data") is True:
            continue
        data_count += 1
        question = item_question(item)
        if question is None:
            errors.append(f"数据图未标注所属小问（question 或 Qn/ 路径），无法核对跨问多样性: {source or family}")
            continue
        bucket = by_question.setdefault(question, {})
        bucket.setdefault(family, []).append(source or family)
        if family in HEATMAP_FAMILIES:
            heatmaps.append(source or family)
        if family in BAR_FAMILIES:
            bars.append(source or family)

    if not by_question:
        errors.append("figures/manifest.json 中没有任何带 chart_family 的数据图条目。")
        return write_report(False, "check_figure_diversity", errors, args.output)

    if len(heatmaps) > 1:
        errors.append("热力图家族全文最多一张，当前为 " + str(len(heatmaps)) + " 张: " + "、".join(heatmaps))
    if bars:
        if len(bars) > 1:
            errors.append("柱状图家族全文最多一张，当前为 " + str(len(bars)) + " 张: " + "、".join(bars))
        for item in items:
            family = normalize_family(item.get("chart_family"))
            if family in BAR_FAMILIES:
                if not str(item.get("bar_exception", "")).strip():
                    errors.append("使用柱状图家族但未写明完整 bar_exception: " + str(item.get("source", "")))

    owners: dict[str, list[str]] = {}
    for question, families in by_question.items():
        for family, sources in families.items():
            owners.setdefault(family, []).append(question)
            if len(sources) > 1:
                if not any(str(item.get("source", "")) in sources and str(item.get("repeat_exception", "")).strip() for item in items):
                    errors.append(
                        f"{question} 内重复使用同一图型 {family} 共 {len(sources)} 张，"
                        "需改用其它图型，或在该 manifest 条目写明 repeat_exception。"
                    )
    for family, questions in owners.items():
        unique = sorted(set(questions))
        if len(unique) > 1:
            errors.append(
                "图型 " + family + " 被多个小问重复使用：" + "、".join(unique)
                + "；每一问的图型必须互不相同。"
            )

    all_families = {family for families in by_question.values() for family in families}
    if data_count:
        for question in by_question:
            if not by_question[question] and not has_no_figure_reason(project, question):
                errors.append(f"{question} 没有任何数据图，且未写明不出图理由。")

    expected = state_question_count(project)
    if expected:
        missing = [f"Q{index}" for index in range(1, expected + 1) if f"Q{index}" not in by_question]
        for question in missing:
            if not has_no_figure_reason(project, question):
                errors.append(f"项目状态 question_count={expected}，但 {question} 没有任何数据图条目。")
        if data_count >= expected and len(all_families) < expected:
            errors.append(
                f"不重复图型数量为 {len(all_families)}，少于小问数 {expected}；"
                "每一问必须使用不同的图型家族。"
            )

    details = {
        "data_figures": data_count,
        "distinct_families": len(all_families),
        "families": sorted(all_families),
        "per_question": {question: sorted(families) for question, families in sorted(by_question.items())},
        "heatmap_count": len(heatmaps),
        "bar_count": len(bars),
    }
    return write_report(not errors, "check_figure_diversity", errors, args.output, details)


if __name__ == "__main__":
    raise SystemExit(main())
