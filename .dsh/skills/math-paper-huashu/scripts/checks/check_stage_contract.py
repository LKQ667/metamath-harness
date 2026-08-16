#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查 step0 至 step5 当前阶段的最小可交接产物。"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from common import project_arg, read_text, write_report
from gate_registry import STAGES, gates_for
from run_stage_gate import CONTRACT_VERSION, fingerprint, safe_project_path


MODEL_TOKENS = ("目标", "输入", "假设", "变量", "公式", "约束", "方法", "验证")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_gate_chain(project: Path, state: dict, stage: str, errors: list[str]) -> None:
    contract = state.get("gate_contract")
    if not isinstance(contract, dict) or contract.get("version") != CONTRACT_VERSION:
        errors.append("项目未由当前版本门禁初始化，禁止进入任何阶段")
        return
    launchers = contract.get("launchers")
    if not isinstance(launchers, dict) or not launchers:
        errors.append("门禁契约缺少项目内启动器清单")
    else:
        for relative, expected in launchers.items():
            path = safe_project_path(project, relative)
            if path is None:
                errors.append(f"项目门禁启动器路径非法: {relative}")
            elif not path.is_file():
                errors.append(f"缺少项目门禁启动器: {relative}")
            elif sha256(path) != expected:
                errors.append(f"项目门禁启动器已被修改: {relative}")

    current_index = STAGES.index(stage)
    for previous in STAGES[:current_index]:
        record = state.get("stages", {}).get(previous, {})
        if record.get("status") != "passed":
            errors.append(f"前序阶段 {previous} 未通过，禁止进入 {stage}")
            continue
        if record.get("input_fingerprint") != fingerprint(project, previous):
            errors.append(f"前序阶段 {previous} 产物已变化，必须重新运行门禁")
        report = safe_project_path(project, record.get("report"))
        if report is None:
            errors.append(f"前序阶段 {previous} 门禁报告路径非法")
            continue
        if not report.is_file():
            errors.append(f"前序阶段 {previous} 缺少门禁报告")
            continue
        if record.get("report_sha256") != sha256(report):
            errors.append(f"前序阶段 {previous} 门禁报告在通过后被修改")
            continue
        try:
            report_data = json.loads(report.read_text(encoding="utf-8"))
        except Exception:
            errors.append(f"前序阶段 {previous} 门禁报告无法解析")
            continue
        if report_data.get("ok") is not True or report_data.get("stage") != previous:
            errors.append(f"前序阶段 {previous} 门禁报告无效")
            continue
        expected = [Path(gate.script).stem for gate in gates_for(previous)]
        if STAGES.index(previous) >= 4:
            expected.insert(0, "compile_paper")
        actual = [item.get("check") for item in report_data.get("checks", []) if isinstance(item, dict)]
        if actual != expected or not all(item.get("ok") is True for item in report_data.get("checks", [])):
            errors.append(f"前序阶段 {previous} 门禁报告检查项不完整或包含失败项")


def require_paths(project: Path, paths: tuple[str, ...], errors: list[str]) -> None:
    for relative in paths:
        path = project / relative
        if not path.exists():
            errors.append(f"缺少阶段产物: {relative}")
        elif path.is_file() and not path.read_text(encoding="utf-8", errors="replace").strip():
            errors.append(f"阶段产物为空: {relative}")


def load_state(project: Path, errors: list[str]) -> dict:
    path = project / "项目状态.json"
    if not path.exists():
        errors.append("缺少项目状态.json")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"项目状态.json 解析失败: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append("项目状态.json 顶层必须是对象")
        return {}
    return data


def check_step0(project: Path, state: dict, errors: list[str]) -> None:
    require_paths(
        project,
        (
            "README.md",
            "AGENT.md",
            "data/source_map.md",
            "文献/source_map.md",
            "figures/manifest.json",
        ),
        errors,
    )
    if state.get("drawing_mode") not in {"drawio", "ai"}:
        errors.append("项目状态缺少有效 drawing_mode")
    if state.get("drawing_mode_locked") is not True or state.get("drawing_mode_confirmed") is not True:
        errors.append("绘图模式必须已确认并锁定")
    if not isinstance(state.get("question_count"), int) or state.get("question_count", 0) < 1:
        errors.append("项目状态必须记录正整数 question_count")


def check_step1(project: Path, state: dict, errors: list[str]) -> None:
    require_paths(project, ("数据预处理/README.md",), errors)
    data_mode = state.get("data_mode")
    if data_mode not in {"data", "none"}:
        errors.append("项目状态必须记录 data_mode=data 或 data_mode=none")
        return
    readme = project / "数据预处理" / "README.md"
    text = read_text(readme) if readme.exists() else ""
    for token in ("原始输入", "处理规则", "EDA", "输出", "结论"):
        if token not in text:
            errors.append(f"数据预处理/README.md 缺少栏目: {token}")
    if data_mode == "data":
        scripts = list((project / "数据预处理").rglob("*.py")) + list((project / "data").glob("*.py"))
        derived = [
            path
            for path in (project / "data").rglob("*")
            if path.is_file() and path.name != "source_map.md"
        ]
        if not scripts:
            errors.append("数据型赛题缺少可运行的预处理脚本")
        if not derived:
            errors.append("数据型赛题缺少清洗或派生数据产物")
    elif "无数据依据" not in text:
        errors.append("无数据型赛题必须在数据预处理说明中记录“无数据依据”")


def check_step2(project: Path, state: dict, errors: list[str]) -> None:
    count = state.get("question_count")
    if not isinstance(count, int) or count < 1:
        return
    for index in range(1, count + 1):
        readme = project / f"Q{index}" / "README.md"
        if not readme.exists():
            errors.append(f"Q{index} 缺少 README.md")
            continue
        text = read_text(readme)
        for token in MODEL_TOKENS:
            if token not in text:
                errors.append(f"Q{index}/README.md 缺少建模设计栏目: {token}")


def check_step3(project: Path, errors: list[str]) -> None:
    path = project / "results" / "final_results.json"
    if not path.exists():
        errors.append("step3 缺少 results/final_results.json")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data:
            errors.append("results/final_results.json 必须是非空对象")
    except Exception as exc:
        errors.append(f"results/final_results.json 解析失败: {exc}")


def check_step4(project: Path, errors: list[str]) -> None:
    require_paths(project, ("论文/main.tex",), errors)


def check_step5(project: Path, errors: list[str]) -> None:
    paper = project / "论文"
    if not list(paper.glob("*.pdf")):
        errors.append("step5 缺少最终 PDF")


def main() -> int:
    parser = project_arg("检查当前阶段最小交付契约")
    parser.add_argument("--stage", required=True, choices=STAGES)
    args = parser.parse_args()
    project = Path(args.project).resolve()
    stage_index = STAGES.index(args.stage)
    errors: list[str] = []
    state = load_state(project, errors)
    check_gate_chain(project, state, args.stage, errors)
    check_step0(project, state, errors)
    if stage_index >= 1:
        check_step1(project, state, errors)
    if stage_index >= 2:
        check_step2(project, state, errors)
    if stage_index >= 3:
        check_step3(project, errors)
    if stage_index >= 4:
        check_step4(project, errors)
    if stage_index >= 5:
        check_step5(project, errors)
    return write_report(not errors, "check_stage_contract", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
