#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按锁定策略检查 Python 源码中的柱形图调用。"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from common import iter_project_files, load_json, load_manifest_items, manifest_path, project_arg, write_report


BAR_METHODS = {"bar", "Bar", "barh", "broken_barh", "barplot", "mark_bar", "vbar", "hbar"}
BAR_KINDS = {"bar", "barh"}


def normalized(value: object) -> str:
    return str(value or "").replace("\\", "/").lstrip("./").lower()


def valid_exception(item: dict) -> bool:
    exc = item.get("bar_exception")
    if not isinstance(exc, dict):
        return False
    required = (
        "necessary",
        "category_count_small",
        "zero_baseline_required",
        "absolute_height_comparison",
    )
    return all(exc.get(key) is True for key in required) and bool(str(exc.get("reason", "")).strip())


def bar_call(call: ast.Call, aliases: set[str] | None = None) -> str | None:
    aliases = aliases or set()
    name = call.func.id if isinstance(call.func, ast.Name) else call.func.attr if isinstance(call.func, ast.Attribute) else ""
    if name in BAR_METHODS or name in aliases:
        return name
    if isinstance(call.func, ast.Call) and isinstance(call.func.func, ast.Name) and call.func.func.id == "getattr":
        args = call.func.args
        if len(args) >= 2 and isinstance(args[1], ast.Constant) and args[1].value in BAR_METHODS:
            return f"getattr(..., {args[1].value!r})"
    if name in {"plot", "catplot"}:
        for keyword in call.keywords:
            if keyword.arg == "kind" and isinstance(keyword.value, ast.Constant) and keyword.value.value in BAR_KINDS:
                return f"{name}(kind={keyword.value.value!r})"
    for keyword in call.keywords:
        if keyword.arg in {"type", "mark"} and isinstance(keyword.value, ast.Constant) and keyword.value.value == "bar":
            return f"{name}({keyword.arg}='bar')"
    return None


def imported_or_assigned_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(alias.asname for alias in node.names if alias.name in BAR_METHODS and alias.asname)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if value is None or not any(isinstance(child, ast.Attribute) and child.attr in BAR_METHODS for child in ast.walk(value)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            aliases.update(target.id for target in targets if isinstance(target, ast.Name))
    return aliases


def bar_dict(node: ast.Dict) -> str | None:
    for key, value in zip(node.keys, node.values):
        if (
            isinstance(key, ast.Constant)
            and key.value in {"type", "mark"}
            and isinstance(value, ast.Constant)
            and value.value == "bar"
        ):
            return f"{{{key.value!r}: 'bar'}}"
    return None


def find_bar_calls(project: Path) -> tuple[list[dict], list[str]]:
    findings: list[dict] = []
    errors: list[str] = []
    for path in iter_project_files(project, (".py",)):
        relative = path.relative_to(project).as_posix()
        if relative.startswith(("论文/附录代码/", "文献/", "赛题/")):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=relative)
        except SyntaxError as exc:
            errors.append(f"无法解析 Python 源码 {relative}:{exc.lineno}: {exc.msg}")
            continue
        aliases = imported_or_assigned_aliases(tree)
        for node in ast.walk(tree):
            name = bar_call(node, aliases) if isinstance(node, ast.Call) else bar_dict(node) if isinstance(node, ast.Dict) else None
            if name:
                findings.append({"source": relative, "line": node.lineno, "call": name})
    return findings, errors


def load_policy(project: Path, errors: list[str]) -> str:
    manifest = load_json(manifest_path(project))
    manifest_policy = manifest.get("bar_policy", manifest.get("bar_chart_policy")) if isinstance(manifest, dict) else None
    state_policy = None
    state_path = project / "项目状态.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state_policy = state.get("bar_policy") if isinstance(state, dict) else None
        except Exception as exc:
            errors.append(f"项目状态.json 解析失败: {exc}")
    if state_policy and manifest_policy and state_policy != manifest_policy:
        errors.append(f"柱状图策略不一致: 项目状态={state_policy}，manifest={manifest_policy}")
    policy = state_policy or manifest_policy or "少用"
    if policy not in {"禁用", "少用", "正常"}:
        errors.append(f"未知柱状图策略: {policy!r}")
        return "少用"
    return policy


def main() -> int:
    parser = project_arg("按禁用/少用/正常策略检查 Python 柱形图真实调用")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    try:
        policy = load_policy(project, errors)
    except Exception as exc:
        policy = "少用"
        errors.append(f"图片清单 JSON 解析失败: {exc}")
    findings, source_errors = find_bar_calls(project)
    errors.extend(source_errors)
    by_source = {normalized(item.get("source")): item for item in items}

    for finding in findings:
        if policy == "禁用":
            errors.append(
                f"柱状图策略为禁用，源码不得调用 {finding['call']}: "
                f"{finding['source']}:{finding['line']}；时间区间请改用 hlines/plot + 端点标记。"
            )
        elif policy == "少用" and not valid_exception(by_source.get(normalized(finding["source"]), {})):
            errors.append(
                f"柱状图策略为少用，但 {finding['source']}:{finding['line']} 的 {finding['call']} "
                "缺少同源 manifest 条目及完整 bar_exception。"
            )

    return write_report(
        not errors,
        "check_python_bar_chart_policy",
        errors,
        args.output,
        {"policy": policy, "bar_calls": findings},
    )


if __name__ == "__main__":
    raise SystemExit(main())
