#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check manifest contract for Python-generated paper figures.

同时承载第七项“Python 图型重复策略”统计：读取三模式策略（默认少重复/模型自行分析/禁止
重复），按图项 `panel_chart_types`（或注册表默认元数据）统计各图型覆盖的图项数 n(t) 与
重复图型数 G。step3 统计拟入文（manifest）图；step4/5 核对最终入文引用集合与清单一致性。
检查器只读取配置，不回写。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import (
    item_export_paths,
    load_json,
    load_manifest_items,
    normalize_project_path,
    project_arg,
    resolve_figure_references,
    write_report,
)
from gate_registry import STAGES

REQUIRED_EXPORT_SUFFIXES = {".svg", ".pdf", ".png"}
STATE_PATH = "项目状态.json"

REPEAT_DEFAULT = "默认（少重复）"
REPEAT_FREE = "模型自行分析"
REPEAT_FORBID = "禁止重复"
REPEAT_ALIASES = {
    "默认（少重复）": REPEAT_DEFAULT,
    "默认(少重复)": REPEAT_DEFAULT,
    "默认": REPEAT_DEFAULT,
    "少重复": REPEAT_DEFAULT,
    "模型自行分析": REPEAT_FREE,
    "自由分析": REPEAT_FREE,
    "自行分析": REPEAT_FREE,
    "禁止重复": REPEAT_FORBID,
    "禁止": REPEAT_FORBID,
}
REPEAT_KEYS = ("python_chart_repeat_policy", "pythonChartRepeatPolicy")
REPEAT_DEFAULT_LIMIT = 2


def load_registry() -> dict:
    import importlib.util

    registry_path = Path(__file__).resolve().parents[1] / "plotting" / "template_registry.py"
    spec = importlib.util.spec_from_file_location("huawei_template_registry", registry_path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    supported = set(getattr(module, "SUPPORTED_CHART_TYPES", set()))
    non_data = set(getattr(module, "NON_DATA_CHART_TYPES", {"flowchart"}))
    return {"templates": dict(getattr(module, "TEMPLATE_REGISTRY", {})), "supported": supported, "non_data": non_data}


def is_python_item(item: dict) -> bool:
    source = str(item.get("source", "")).lower()
    return item.get("generator") == "python" or source.endswith(".py")


def is_flowchart_item(item: dict) -> bool:
    """流程图排除只依据生成器语义（注册模板/图型族），不按路径或标题词语分类
    （M07：文件名含 roadmap 的数据折线图必须照常计数）。"""
    if str(item.get("template_id", "")) == "python_flowchart_topdown":
        return True
    chart_family = str(item.get("chart_family", "")).lower()
    return "flowchart" in chart_family


def read_project_state(project: Path, errors: list[str]) -> dict:
    state_path = project / STATE_PATH
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"项目状态.json 解析失败: {exc}")
        return {}
    if not isinstance(state, dict):
        errors.append("项目状态.json 顶层必须是对象")
        return {}
    return state


def normalize_repeat_policy(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return REPEAT_ALIASES.get(value.strip())
    return None


def resolve_chart_repeat_policy(state: dict, manifest: dict | None, errors: list[str]) -> tuple[str | None, str]:
    """按 4.1 节固定规则解析三模式策略；缺字段与 null/空串严格区分，不猜项目年龄。"""
    state_raw, manifest_raw = None, None
    state_present, manifest_present = False, False
    for key in REPEAT_KEYS:
        if isinstance(state, dict) and key in state:
            state_raw, state_present = state[key], True
            break
    if isinstance(manifest, dict):
        for key in REPEAT_KEYS:
            if key in manifest:
                manifest_raw, manifest_present = manifest[key], True
                break
    if not state_present and not manifest_present:
        return REPEAT_FREE, "legacy_missing"
    state_value = normalize_repeat_policy(state_raw) if state_present else None
    manifest_value = normalize_repeat_policy(manifest_raw) if manifest_present else None
    if state_present and state_value is None:
        errors.append(
            f"项目状态.json 的 {REPEAT_KEYS[0]} 值非法（{state_raw!r}）：字段值为 null/空串/未知值必须报配置错误，不能默认降级。"
        )
    if manifest_present and manifest_value is None:
        errors.append(
            f"图片清单的 {REPEAT_KEYS[0]} 值非法（{manifest_raw!r}）：字段值为 null/空串/未知值必须报配置错误，不能默认降级。"
        )
    if state_present and manifest_present and state_value and manifest_value and state_value != manifest_value:
        errors.append(f"图型重复策略不一致: 项目状态={state_value}，manifest={manifest_value}；两处都存在时必须一致。")
        return state_value or manifest_value, "conflict"
    if state_value:
        return state_value, "explicit_state"
    if manifest_value:
        return manifest_value, "explicit_manifest"
    return None, "invalid"


def validate_panel_chart_types(item: dict, registry: dict, errors: list[str]) -> tuple[list[str], bool]:
    """校验/推导图项图型元数据。结构非法直接报错；未知类型 ID 由调用方按策略模式处理。
    返回 (已知类型集合, 是否存在未知或缺失)。

    M06：先校验二维结构与成员类型（字符串且非空）再去重；空面板、字典、嵌套数组、
    数字、布尔值都是明确配置错误，不允许用空列表绕过禁止重复约束。"""
    source = str(item.get("source", "")) or str(item)
    supported: set = registry["supported"]
    raw = item.get("panel_chart_types")
    panel_count = item.get("panel_count")
    if raw is not None:
        if not isinstance(raw, list) or not all(isinstance(panel, list) for panel in raw):
            errors.append(f"panel_chart_types 必须是二维字符串数组（如 [['line_2d'], ['heatmap_2d']]），不接受字符串/扁平数组混用: {source}")
            return [], True
        if isinstance(panel_count, int) and not isinstance(panel_count, bool) and len(raw) != panel_count:
            errors.append(f"panel_chart_types 外层长度必须等于 panel_count={panel_count}: {source} 当前 {len(raw)}")
            return [], True
        if len(raw) == 0:
            errors.append(f"panel_chart_types 为空列表：计入 panel_count 的图项必须至少声明一个面板: {source}")
            return [], True
        types: list[str] = []
        unknown = False
        for index, panel in enumerate(raw):
            string_entries = [entry for entry in panel if isinstance(entry, str)]
            if len(panel) == 0:
                errors.append(f"panel_chart_types 第 {index + 1} 个面板为空：计入 panel_count 的独立数据面板必须至少声明一个真实图型（装饰坐标轴/色条不属于独立数据面板，不能用空列表替代）: {source}")
                unknown = True
                continue
            if len(string_entries) != len(panel):
                errors.append(f"panel_chart_types 第 {index + 1} 个面板含非字符串成员（字典/嵌套数组/数字/布尔值等）: {source}")
                unknown = True
            if len(set(string_entries)) != len(string_entries):
                errors.append(f"panel_chart_types 第 {index + 1} 个面板内类型重复: {source}")
                unknown = True
            for entry in string_entries:
                if entry not in supported:
                    unknown = True
                else:
                    types.append(entry)
        return sorted(set(types)), unknown
    template_id = str(item.get("template_id", "") or "")
    entry = registry["templates"].get(template_id)
    if entry and item.get("chart_family") == entry.get("chart_family"):
        default = entry.get("chart_types")
        if isinstance(default, list) and isinstance(panel_count, int) and len(default) == panel_count:
            return sorted({t for panel in default for t in panel}), False
    # 缺元数据：未改绘可推导，改绘（chart_family 与注册表不一致）必须显式提供；此处仅标记未知。
    return [], True


def repeat_reasons_recorded(state: dict, manifest: dict | None, repeat_types: list[str]) -> bool:
    for holder in (state, manifest if isinstance(manifest, dict) else {}):
        reasons = holder.get("chart_repeat_reasons")
        if isinstance(reasons, dict):
            if all(str(reasons.get(t, "")).strip() for t in repeat_types):
                return True
    return False


def main() -> int:
    parser = project_arg("检查 Python 绘图最小契约与图型重复策略。")
    parser.add_argument("--stage", choices=STAGES, help="当前门禁阶段；缺省按 step3 预排版口径执行")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    stage = args.stage or "step3"
    stage_source = "default_step3" if args.stage is None else "explicit"
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    manifest_raw: dict = {}
    manifest_path = project / "figures" / "manifest.json"
    if manifest_path.exists():
        try:
            loaded = load_json(manifest_path)
            if isinstance(loaded, dict):
                manifest_raw = loaded
        except Exception:
            pass
    state = read_project_state(project, errors)
    try:
        registry = load_registry()
    except Exception as exc:
        registry = {"templates": {}, "supported": set(), "non_data": {"flowchart"}}
        errors.append(f"模板注册表读取失败: {exc}")

    policy, policy_source = resolve_chart_repeat_policy(state, manifest_raw, errors)
    strict_stats = policy in (REPEAT_DEFAULT, REPEAT_FORBID) and policy_source != "legacy_missing"

    # ---- 导出路径冲突（任意生成器图项之间）----
    # M09：按"图项出现序"而非 source 字符串判定归属——相同 source 原样重复声明
    # 相同 exports 也算清单条目重复；同一图项内部格式别名已由导出归一处理。
    export_owner: dict[Path, tuple[int, str]] = {}
    for item_index, item in enumerate(items):
        source = str(item.get("source", "")) or str(item)
        for path in item_export_paths(project, item):
            if path is None:
                errors.append(f"图项导出路径非法或指向项目外: {item}")
                continue
            previous = export_owner.setdefault(path, (item_index, source))
            if previous[0] != item_index:
                errors.append(
                    f"同一导出文件被多个图项重复声明，清单冲突（清单条目重复）: {path.as_posix()}"
                    f" 同时属于 {previous[1]}（清单第 {previous[0] + 1} 项）与 {source}（清单第 {item_index + 1} 项）；"
                    "请整理 manifest（同一脚本合法生成多张不同导出图不受影响），不要为重复计数改图。"
                )

    # ---- 阶段口径与最终入文集合 ----
    refs: set[Path] | None = None
    ref_info: dict | None = None
    if stage != "step3":
        ref_info = resolve_figure_references(project)
        if ref_info["tex_missing"]:
            errors.append(f"阶段 {stage} 需要核对最终入文集合，但缺少论文/main.tex；请先完成论文排版。")
        else:
            refs = set(ref_info["resolved"])
            for token in ref_info["unresolved"]:
                errors.append(f"论文引用路径无法解析为项目内实际文件，不能当作没有引用，请人工核对: {token}")

    counted_items: list[dict] = []
    types_by_item: list[tuple[str, str, list[str]]] = []  # (图项唯一键, source, 类型)
    unknown_items: list[str] = []
    for item in items:
        if not is_python_item(item):
            continue
        source = str(item.get("source", "")) or str(item)
        if item.get("generator") != "python":
            errors.append(f"Python 图缺少 generator=python: {source or item}")
        if not item.get("template_id"):
            errors.append(f"Python 图缺少 template_id: {source or item}")
        if not item.get("chart_family"):
            errors.append(f"Python 图缺少 chart_family: {source or item}")
        panel_count = item.get("panel_count")
        if isinstance(panel_count, bool) or not isinstance(panel_count, int) or panel_count < 1:
            errors.append(f"Python 图缺少正整数 panel_count（语义面板数，colorbar/legend 不计）: {source or item}")
        if item.get("paper_ready") is not True:
            errors.append(f"Python 图未标记 paper_ready=true: {source or item}")
        qa = item.get("qa")
        if isinstance(qa, dict) and qa.get("profile") == "research" and qa.get("research_preflight_ok") is not True:
            errors.append(f"科研图的 paper_ready 缺少严格预检证据: {source or item}")

        source_path = project / source if source else None
        if not source:
            errors.append(f"Python 图缺少 source: {item}")
        elif source_path is not None and not source_path.exists():
            errors.append(f"Python 图源不存在: {source}")

        raw_exports = item.get("exports") or []
        exports = list(raw_exports.values()) if isinstance(raw_exports, dict) else raw_exports
        if not exports:
            errors.append(f"Python 图缺少导出文件: {source or item}")
        else:
            suffixes = {Path(exp).suffix.lower() for exp in exports}
            missing = sorted(REQUIRED_EXPORT_SUFFIXES - suffixes)
            if missing:
                errors.append(f"Python 图导出格式不完整 {source or item}: 缺少 {'、'.join(missing)}")
            for rel in exports:
                if not (project / rel).exists():
                    errors.append(f"Python 图导出文件不存在: {rel}")

        # ---- 图型重复统计对象过滤 ----
        if is_flowchart_item(item):
            entry = registry["templates"].get(str(item.get("template_id", "")))
            declared_types = item.get("panel_chart_types", [])
            if (entry and "flowchart" not in str(entry.get("chart_family", "")).lower()) or (
                isinstance(declared_types, list) and any(t not in registry["non_data"] for t in declared_types if isinstance(t, str))
            ):
                errors.append(f"流程图声明与数据图模板或panel_chart_types冲突，不能豁免计数: {source}")
            continue
        if refs is not None:
            exported = {path for path in item_export_paths(project, item) if path is not None}
            if not exported & refs:
                errors.append(
                    f"清单中的 Python 数据图未出现在最终论文引用中（不得静默缩小集合规避数量限制；确认移出清单时保留图源与图像）: {source}"
                )
                continue
        counted_items.append(item)
        types, unknown = validate_panel_chart_types(item, registry, errors)
        known = [t for t in types if t not in registry["non_data"]]
        if unknown:
            if strict_stats:
                errors.append(
                    f"图型重复计数不可完成：图项缺少或含未知的 panel_chart_types 元数据（策略 {policy} 下未知类型不能按 0 计）: {source}"
                )
            else:
                unknown_items.append(source)
        item_key = f"{source}#{len(counted_items)}"  # 同 source 多张图按图项分别计数，禁止按 source 去重
        types_by_item.append((item_key, source, known))

    if refs is not None and ref_info is not None and not ref_info["tex_missing"]:
        covered = {path for item in items for path in item_export_paths(project, item) if path is not None}
        for ref in sorted(refs):
            if ref not in covered:
                errors.append(f"论文实际引用了但未登记进图片清单的图，缺项: {ref.relative_to(project).as_posix()}")

    # ---- G 统计与三模式门禁 ----
    per_type: dict[str, list[str]] = {}
    display: dict[str, str] = {}
    for item_key, source, types in types_by_item:
        display[item_key] = source
        for t in types:
            per_type.setdefault(t, []).append(item_key)
    repeat_types = sorted(t for t, owners in per_type.items() if len(set(owners)) >= 2)
    g_value: int | None
    if unknown_items and not strict_stats:
        g_value = None
    else:
        g_value = len(repeat_types)
    details: dict = {
        "mode": policy,
        "policy_source": policy_source,
        "stage": stage,
        "stage_source": stage_source,
        "scope": "最终入文（step4/5 按实际引用核对）" if stage != "step3" else "拟入文（step3 预排版统计）",
        "n_by_type": {t: len(set(owners)) for t, owners in sorted(per_type.items())},
        "per_type_items": {t: sorted({display[key] for key in owners}) for t, owners in sorted(per_type.items())},
        "repeat_types": repeat_types,
        "G": g_value,
        "unknown_types_items": unknown_items,
        "counted_figures": len(counted_items),
    }
    if policy is not None:
        if policy == REPEAT_DEFAULT and g_value is not None and g_value > REPEAT_DEFAULT_LIMIT:
            detail = "、".join(f"{t}(n={len(set(per_type[t]))})" for t in repeat_types)
            errors.append(
                f"图型重复策略为默认（少重复），重复图型类别数 G={g_value} 超过 {REPEAT_DEFAULT_LIMIT}：{detail}；"
                "请合并同族图、改用已用图型承载新结论，或按论证需要申请更换策略。"
            )
        if policy == REPEAT_FORBID and g_value is not None and g_value > 0:
            detail = "、".join(f"{t}(n={len(set(per_type[t]))})" for t in repeat_types)
            errors.append(f"图型重复策略为禁止重复，仍存在重复图型 G={g_value}：{detail}；同类图型只能出现在一张入文图中。")
        if policy == REPEAT_FREE and repeat_types and policy_source != "legacy_missing":
            if not repeat_reasons_recorded(state, manifest_raw, repeat_types):
                errors.append(
                    "模型自行分析模式存在重复图型，须在 项目状态.json（或 manifest）写 chart_repeat_reasons 记录每种重复图型用于什么比较，"
                    "并禁止同数据同结论只换配色凑图。"
                )
            # M08：legacy_missing（旧项目缺策略字段）沿用"模型自行分析"语义但不新增
            # 理由硬要求，只提示补充；显式非法策略值已在策略解析处报错。

    return write_report(not errors, "check_python_figure_contract", errors, args.output, details)


if __name__ == "__main__":
    sys.exit(main())
