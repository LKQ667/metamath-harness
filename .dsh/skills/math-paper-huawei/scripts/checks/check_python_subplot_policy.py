#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按锁定 `subplot_policy` 检查 Python 入文图的语义面板数。"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from common import (
    SUBPOLICY_DEFAULT,
    SUBPOLICY_DISABLED,
    SUBPOLICY_SPARSE,
    SUBPOLICY_SPARSE_MAX_MULTI_PANEL,
    item_export_paths,
    load_json,
    load_manifest_items,
    manifest_path,
    normalize_project_path,
    normalize_subplot_policy,
    project_arg,
    resolve_figure_references,
    write_report,
)
from gate_registry import STAGES


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "plotting" / "template_registry.py"
POLICY_KEYS = ("subplot_policy", "subplotPolicy", "subplots")


def load_registry() -> dict:
    import importlib.util

    spec = importlib.util.spec_from_file_location("huawei_template_registry", REGISTRY_PATH)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(getattr(module, "TEMPLATE_REGISTRY", {}))


def is_python_item(item: dict) -> bool:
    source = str(item.get("source", "")).lower()
    return item.get("generator") == "python" or source.endswith(".py")


def sparse_override(project: Path, errors: list[str]) -> int | None:
    """读取显式少用限额覆盖；`subplot_sparse_max`（非负整数）与 `subplot_sparse_override_request`
    （用户原话）必须同时存在，否则按默认 4 张执行并报告配置不完整。
    自然语言子串不构成授权；覆盖只作用于少用模式，禁用模式不读取本函数。"""
    state_path = project / "项目状态.json"
    state: dict = {}
    if state_path.exists():
        try:
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = loaded
        except Exception as exc:
            errors.append(f"项目状态.json 解析失败: {exc}")
            return None
    raw_max = state.get("subplot_sparse_max")
    raw_request = state.get("subplot_sparse_override_request")
    if raw_max is None and raw_request is None:
        return None
    max_ok = isinstance(raw_max, int) and not isinstance(raw_max, bool) and raw_max >= 0
    request_ok = isinstance(raw_request, str) and bool(raw_request.strip())
    if not (max_ok and request_ok):
        errors.append(
            "少用子图限额覆盖配置不完整：subplot_sparse_max（非负整数）与 subplot_sparse_override_request"
            "（真实用户原话）必须同时存在且类型正确，当前按默认 4 张执行；"
            "“不允许放宽”等否定句或无明确整数的“放宽一些”不构成授权。"
        )
        return None
    return raw_max


def load_policy(project: Path, errors: list[str]) -> str:
    manifest = load_json(manifest_path(project))
    manifest_policy = None
    if isinstance(manifest, dict):
        for key in POLICY_KEYS:
            if manifest.get(key):
                manifest_policy = manifest[key]
                break
    state_policy = None
    state_path = project / "项目状态.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                for key in POLICY_KEYS:
                    if state.get(key):
                        state_policy = state[key]
                        break
        except Exception as exc:
            errors.append(f"项目状态.json 解析失败: {exc}")
    if state_policy and manifest_policy:
        left, right = normalize_subplot_policy(state_policy), normalize_subplot_policy(manifest_policy)
        if left != right:
            errors.append(f"子图策略不一致: 项目状态={left}，manifest={right}")
            return left
    return normalize_subplot_policy(state_policy or manifest_policy or SUBPOLICY_DEFAULT)


# ---------------------------------------------------------------------------
# 源码辅助分析：只覆盖已登记 source 内的可达调用（模块顶层、main 入口、直接调用的
# 本地函数）。未调用定义不构成实际生成，只列待审事项；不实现通用静态解释器。
# ---------------------------------------------------------------------------

DEF_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _collect_funcs(tree: ast.Module) -> dict[str, ast.AST]:
    funcs: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name not in funcs:
            funcs[node.name] = node
    return funcs


def _walk_reachable(nodes: list[ast.AST], visited: set[str]):
    """遍历可达语句；函数/类子树只有被显式展开（visited）才进入。"""
    stack = list(nodes)
    while stack:
        node = stack.pop()
        if isinstance(node, DEF_NODES):
            name = getattr(node, "name", None)
            if name is None or name not in visited:
                continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _const_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def finding_for_call(node: ast.Call) -> dict | None:
    """识别可能产生多面板的常见调用；单图、colorbar、legend、同域 twinx 不命中。"""
    name = _call_name(node)
    if name == "compose_multi_panel":
        return {"line": node.lineno, "call": name, "hint": "多面板合成函数"}
    if name == "subplots":
        for keyword in node.keywords:
            if keyword.arg in {"nrows", "ncols"} and isinstance(keyword.value, ast.Constant):
                count = _const_int(keyword.value.value)
                if count is not None and count > 1:
                    return {"line": node.lineno, "call": f"subplots({keyword.arg}={count})", "hint": "多行/多列子图"}
        ints = [value for value in (_const_int(arg.value) for arg in node.args[:2] if isinstance(arg, ast.Constant)) if value is not None]
        if ints:
            rows = ints[0]
            cols = ints[1] if len(ints) > 1 else 1
            if rows > 0 and cols > 0 and rows * cols > 1:
                return {"line": node.lineno, "call": f"subplots({rows}, {cols})", "hint": "位置参数多行/多列子图"}
    elif name == "add_subplot" and isinstance(node.func, ast.Attribute):
        first = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
        if isinstance(first, int) and not isinstance(first, bool) and 111 <= first <= 999:
            rows, cols = first // 100, (first // 10) % 10
            if rows * cols > 1:
                return {"line": node.lineno, "call": f"add_subplot({first})", "hint": "网格子图索引（整数三位布局）"}
        elif isinstance(first, str) and len(first) == 3 and first.isdigit():
            rows, cols = int(first[0]), int(first[1])
            if rows * cols > 1:
                return {"line": node.lineno, "call": f"add_subplot({first!r})", "hint": "网格子图索引"}
        else:
            int_args = [value for arg in node.args if isinstance(arg, ast.Constant) and (value := _const_int(arg.value)) is not None]
            if len(int_args) >= 2 and int_args[0] * int_args[1] > 1:
                return {"line": node.lineno, "call": f"add_subplot({int_args[0]}, {int_args[1]}, …)", "hint": "位置参数网格布局"}
    elif name in {"inset_axes", "mark_inset"} and isinstance(node.func, ast.Attribute):
        return {"line": node.lineno, "call": name, "hint": "显式 inset 嵌入坐标区"}
    return None


def reachable_multiaxial_findings(path: Path) -> tuple[list[dict], list[dict]]:
    """返回 (可达多面板调用发现, 待审事项)；语法失败/动态分派进入待审事项。"""
    relative = path.as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=relative)
    except SyntaxError as exc:
        return [], [{"file": relative, "line": None, "reason": f"源码语法错误，无法静态分析: {exc}"}]
    funcs = _collect_funcs(tree)
    top_nodes = [node for node in tree.body if not isinstance(node, DEF_NODES)]
    reachable_nodes = list(top_nodes)
    visited: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in _walk_reachable(reachable_nodes, visited):
            if isinstance(node, ast.Call):
                callee = getattr(node.func, "id", None)
                if callee and callee in funcs and callee not in visited:
                    visited.add(callee)
                    reachable_nodes.extend(funcs[callee].body)
                    changed = True
    findings: list[dict] = []
    for node in _walk_reachable(reachable_nodes, visited):
        if isinstance(node, ast.Call):
            finding = finding_for_call(node)
            if finding:
                findings.append({"file": relative, **finding})
    review: list[dict] = []
    for name, definition in funcs.items():
        if name in visited:
            continue
        for node in ast.walk(definition):
            if isinstance(node, ast.Call) and finding_for_call(node):
                review.append({"file": relative, "line": node.lineno, "reason": f"未调用定义 {name} 内含多面板调用，不构成实际生成，请结合实际图像复核"})
                break
    return findings, review


def item_referenced(project: Path, item: dict, refs: set[Path]) -> bool:
    return any(path is not None and path in refs for path in item_export_paths(project, item))


def main() -> int:
    parser = project_arg("按 subplot_policy 检查 Python 入文图的语义面板数")
    parser.add_argument("--stage", choices=STAGES, help="当前门禁阶段；缺省按 step3 预排版口径执行")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    stage = args.stage or "step3"
    stage_source = "default_step3" if args.stage is None else "explicit"
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    try:
        registry = load_registry()
    except Exception as exc:
        registry = {}
        errors.append(f"模板注册表读取失败: {exc}")
    if not registry:
        errors.append("模板注册表为空，无法核对 panel_count 语义")
    try:
        policy = load_policy(project, errors)
    except Exception as exc:
        policy = SUBPOLICY_DEFAULT
        errors.append(f"图片清单 JSON 解析失败: {exc}")

    refs: set[Path] | None = None
    if stage != "step3":
        ref_info = resolve_figure_references(project)
        if ref_info["tex_missing"]:
            errors.append(f"阶段 {stage} 需要核对最终入文集合，但缺少论文/main.tex；请先完成论文排版。")
        else:
            refs = set(ref_info["resolved"])
            for token in ref_info["unresolved"]:
                errors.append(f"论文引用路径无法解析为项目内实际文件，请人工核对该图是否入文: {token}")

    python_items = [item for item in items if is_python_item(item)]
    if refs is not None:
        python_items = [item for item in python_items if item_referenced(project, item, refs)]
    multi_panel: list[dict] = []
    scan_sources: list[Path] = []
    for item in python_items:
        source = str(item.get("source", "")) or str(item)
        template_id = str(item.get("template_id", "") or "")
        entry = registry.get(template_id)
        if not template_id or entry is None:
            errors.append(f"Python 图的 template_id 不在内置模板注册表中，无法核对面板数: {source}（template_id={template_id or '缺失'}）")
            continue
        expected = int(entry.get("panel_count") or 1)
        raw = item.get("panel_count")
        if isinstance(raw, bool) or not isinstance(raw, int):
            errors.append(f"Python 图 manifest 条目缺少整数 panel_count: {source}")
            continue
        if raw != expected:
            errors.append(f"panel_count 与模板语义不一致: {source} 记录 {raw}，{template_id} 语义为 {expected}")
            continue
        if raw > 1:
            multi_panel.append({"source": source, "template_id": template_id, "panel_count": raw})
        source_path = normalize_project_path(project, source)
        if source_path is not None and source_path.is_file():
            scan_sources.append(source_path)

    review_items: list[dict] = []
    if policy == SUBPOLICY_SPARSE and multi_panel:
        override = sparse_override(project, errors)
        limit = SUBPOLICY_SPARSE_MAX_MULTI_PANEL if override is None else override
        if len(multi_panel) > limit:
            names = "、".join(f"{item['source']}({item['panel_count']})" for item in multi_panel)
            errors.append(
                f"子图策略为少用子图，多面板入文图最多 {limit} 张，当前 {len(multi_panel)} 张: {names}；"
                "请改写为等价单 panel 模板或拆为独立编号图。确需调整上限时，由执行者在 项目状态.json 同时写入 "
                "subplot_sparse_max（非负整数）与 subplot_sparse_override_request（真实用户原话）；自然语言子串不构成授权。"
            )
    elif policy == SUBPOLICY_DISABLED:
        for item in multi_panel:
            errors.append(f"子图策略为禁用子图，但 {item['source']} 的 panel_count={item['panel_count']}；请拆为多张 panel_count=1 的独立图。")
        for path in scan_sources:
            findings, review = reachable_multiaxial_findings(path)
            review_items.extend(review)
            for finding in findings:
                errors.append(
                    f"子图策略为禁用子图，入文图源码不得生成多面板: {finding['file']}:{finding['line']} 的 {finding['call']}（{finding['hint']}）。"
                )

    return write_report(
        not errors,
        "check_python_subplot_policy",
        errors,
        args.output,
        {
            "policy": policy,
            "stage": stage,
            "stage_source": stage_source,
            "sparse_limit": SUBPOLICY_SPARSE_MAX_MULTI_PANEL,
            "python_figures": len(python_items),
            "multi_panel": multi_panel,
            "review_items": review_items,
        },
    )


if __name__ == "__main__":
    sys.exit(main())
