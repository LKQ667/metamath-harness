#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查华为杯“参考往届优秀论文（视觉校准）”是否留下可审计的截图证据。

权威证据源是渲染器生成的 `检查结果/excellent_paper_visual_review.json`（已选样本与代表页清单）。
门禁只核对可审计证据：样本已发现 → PNG 真实可解码 → 逐页观察记录存在且具体；
不宣称能证明模型内部思维。开关只以锁定配置为准，缺省 false；任何开关状态下都检查截图入文。
"""

from __future__ import annotations

import json
from pathlib import Path

from common import (
    project_arg,
    resolve_figure_references,
    split_page_blocks,
    split_sample_blocks,
    observation_problems,
    write_report,
)


SHOT_DIR = "截图"
RECORD_NAME = "优秀论文参考记录.md"
REPORT_REL = Path("检查结果") / "excellent_paper_visual_review.json"
# 共享发现脚本的失败/回退状态：只要求记录真实原因，不要求伪造截图。
FALLBACK_STATUS = {
    "disabled",
    "catalog_missing",
    "catalog_invalid",
    "no_matching_sample",
    "file_missing",
    "hash_mismatch",
    "discover_failed",
}
OBSERVATION_DIMENSIONS = ("版式留白与信息密度", "布局与图表组织", "文风与句式节奏")
SWITCH_KEYS = ("reference_excellent_papers", "referenceExcellentPapers")
TRUE_TOKENS = {"true", "1", "yes", "on", "是", "开启"}
FALSE_TOKENS = {"false", "0", "no", "off", "否", "关闭"}
UNREAD_MARK = "未读取"


def locked_switch(project: Path, errors: list[str]) -> bool:
    """开关仅读锁定配置；缺省 false；非法类型报告配置问题。"""
    state_path = project / "项目状态.json"
    if not state_path.exists():
        return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"项目状态.json 解析失败: {exc}")
        return False
    if not isinstance(state, dict):
        errors.append("项目状态.json 顶层必须是对象")
        return False
    for key in SWITCH_KEYS:
        if key not in state:
            continue
        value = state[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in TRUE_TOKENS:
                return True
            if text in FALSE_TOKENS:
                return False
        errors.append(f"项目状态.json 的 {key} 不是合法布尔值（{value!r}）；请修复锁定配置，检查器不从论文文本推断开关。")
        return False
    return False


def screenshot_leaks(project: Path) -> list[str]:
    """用实际 includegraphics/graphicspath 解析核对截图是否入文；未解析 token 只兜底检查字面前缀。"""
    info = resolve_figure_references(project)
    shot_root = (project / SHOT_DIR).resolve()
    hits: list[str] = []
    for path in info["resolved"]:
        try:
            path.relative_to(shot_root)
        except ValueError:
            continue
        hits.append(f"实际引用文件: {path.relative_to(project).as_posix()}")
    for token in info["unresolved"]:
        normalized = token.replace("\\", "/")
        if normalized.startswith(SHOT_DIR) or f"/{SHOT_DIR}/" in normalized:
            hits.append(f"未解析但指向截图目录的引用: {token}")
    return hits


def verify_matched_evidence(project: Path, report: dict, errors: list[str]) -> dict:
    try:
        import fitz
    except ImportError:
        errors.append("缺少 PyMuPDF(fitz)，无法核验截图真实可解码；不能默认通过。")
        return {"enabled": True, "status": "matched"}
    record_path = project / SHOT_DIR / RECORD_NAME
    if not record_path.exists():
        errors.append(f"缺少优秀论文参考记录: {SHOT_DIR}/{RECORD_NAME}")
        return {"enabled": True, "status": "matched"}
    record_text = record_path.read_text(encoding="utf-8")
    blocks = split_sample_blocks(record_text)
    selected = report.get("selected_papers") or []
    declared = report.get("papers")
    if declared is not None and isinstance(declared, int) and declared != len(selected):
        errors.append(
            f"发现报告声明 {declared} 篇但 selected_papers 只有 {len(selected)} 篇证据；缺少的样本必须补齐渲染与观察，不能按一篇冒充。"
        )
    if not selected:
        errors.append("发现报告状态为 matched 但未登记任何已选样本；请重新执行发现/渲染。")
        return {"enabled": True, "status": "matched"}
    for paper in selected:
        folder = str(paper.get("folder") or "")
        shots = paper.get("shots") or []
        if not folder or not (project / folder).is_dir():
            errors.append(f"发现报告选中的样本目录不存在: {folder}")
            continue
        if not shots:
            errors.append(f"样本 {folder} 没有任何代表页记录；不能少样本通过。")
            continue
        block = blocks.get(folder)
        if block is None:
            errors.append(f"优秀论文参考记录缺少样本块“样本 {folder}”，或该块被标注为旧样本。")
            continue
        pages = split_page_blocks(block)
        for shot in shots:
            page = shot.get("page")
            relative = str(shot.get("relative") or "")
            png_path = project / relative
            if page is None or not relative:
                errors.append(f"样本 {folder} 存在页信息不完整的代表页记录: {shot}")
                continue
            if not png_path.is_file():
                errors.append(f"样本 {folder} 缺少代表页截图: {relative}")
                continue
            try:
                fitz.Pixmap(str(png_path))
            except Exception as exc:
                errors.append(f"截图无法被 PyMuPDF 解码（损坏或非 PNG 内容）: {relative}: {exc}")
                continue
            page_block = pages.get(page)
            if page_block is None:
                errors.append(f"优秀论文参考记录缺少 {folder} 第 {page} 页的逐页观察块。")
                continue
            if f"`{relative}`" not in page_block:
                errors.append(f"优秀论文参考记录第 {page} 页块未登记对应截图 {relative}。")
            if UNREAD_MARK in page_block:
                errors.append(f"{folder} 第 {page} 页仍处于“未读取，待完成视觉观察”状态，不得声称已参考。")
                continue
            for problem in observation_problems(page_block, OBSERVATION_DIMENSIONS):
                errors.append(f"{folder} 第 {page} 页 {problem}。")
    if report.get("problem_match") is False:
        if "未能完成同题参考" not in record_text:
            errors.append(
                "发现结果 problem_match=false（缺真实题号，仅同赛事参考）；参考记录必须写明“未能完成同题参考”，不得当成同题校准。"
            )
    return {"enabled": True, "status": "matched", "papers": len(selected), "shots": sum(len(p.get("shots") or []) for p in selected)}


def main() -> int:
    parser = project_arg("核对优秀论文视觉校准的截图与观察记录证据")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []

    leaks = screenshot_leaks(project)
    for item in leaks:
        errors.append(f"截图证据不得被 \\includegraphics 引入论文: {item}")

    enabled = locked_switch(project, errors)
    if not enabled:
        return write_report(
            not errors,
            "check_excellent_paper_visual_reference",
            errors,
            args.output,
            {"enabled": False, "note": "开关关闭或缺省，不要求视觉参考证据；截图入文检查仍然执行。"},
        )

    report_path = project / REPORT_REL
    if not report_path.exists():
        errors.append(
            f"开启视觉校准但缺少权威报告 {REPORT_REL.as_posix()}；请先运行 excellent_paper_visual_review.py 完成发现与渲染，"
            "不能凭旧截图或占位文案充当证据。"
        )
        return write_report(False, "check_excellent_paper_visual_reference", errors, args.output, {"enabled": True})
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"权威报告无法解析: {exc}")
        return write_report(False, "check_excellent_paper_visual_reference", errors, args.output, {"enabled": True})

    status = str(report.get("status") or "unknown")
    if status == "disabled":
        errors.append(
            "配置开启视觉校准，但权威报告状态为 disabled：开关与发现状态冲突；请核对锁定配置并重新运行发现脚本。"
        )
        return write_report(False, "check_excellent_paper_visual_reference", errors, args.output, {"enabled": True, "status": status})

    if status in FALLBACK_STATUS:
        reason = str(report.get("fallback_reason") or "").strip()
        if not reason:
            errors.append(f"共享发现状态为 {status} 但报告未记录真实回退原因；必须原样保存共享发现状态与原因，不能写成普通“无样本”。")
        return write_report(
            not errors,
            "check_excellent_paper_visual_reference",
            errors,
            args.output,
            {"enabled": True, "status": status, "fallback_reason": reason, "note": "回退状态可继续原论文流程，但本次未完成视觉参考。"},
        )

    if status != "matched":
        errors.append(f"权威报告状态“{status}”不是 matched 或已知回退状态，无法核对视觉参考证据。")
        return write_report(False, "check_excellent_paper_visual_reference", errors, args.output, {"enabled": True, "status": status})

    details = verify_matched_evidence(project, report, errors)
    return write_report(not errors, "check_excellent_paper_visual_reference", errors, args.output, details)


if __name__ == "__main__":
    raise SystemExit(main())
