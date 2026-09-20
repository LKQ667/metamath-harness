#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查技术路线图按项目锁定模式生成并插入论文。"""

from __future__ import annotations

from pathlib import Path

from common import load_manifest_items, project_arg, read_text, write_report


EXPORT_SUFFIXES = {".png", ".svg", ".pdf"}
ROADMAP_TOKENS = ("技术路线", "路线图", "roadmap", "问题分析流程")


def item_values(item: dict) -> list[str]:
    values: list[str] = []
    for value in item.values():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(v) for v in value)
        elif isinstance(value, dict):
            values.extend(str(v) for v in value.values())
    return values


def item_exports(item: dict) -> list[str]:
    exports = item.get("exports")
    if isinstance(exports, list):
        return [str(x) for x in exports]
    if isinstance(exports, dict):
        return [str(x) for x in exports.values()]
    export = item.get("export")
    if isinstance(export, str):
        return [export]
    return []


def is_roadmap_item(item: dict) -> bool:
    text = "\n".join(item_values(item)).lower()
    return any(token.lower() in text for token in ROADMAP_TOKENS)


def normalized(path: str) -> str:
    return path.replace("\\", "/")


def main() -> int:
    parser = project_arg("检查技术路线图是否按锁定模式生成并插入论文。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    hand_dir = project / "手绘图"
    tex_path = project / "论文" / "main.tex"

    export_files = sorted([p for p in hand_dir.glob("*") if p.is_file() and p.suffix.lower() in EXPORT_SUFFIXES]) if hand_dir.exists() else []
    if not export_files:
        errors.append("`手绘图/` 缺少技术路线图 PNG/SVG/PDF 导出图。")

    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    roadmap_items = [item for item in items if is_roadmap_item(item)]
    if not roadmap_items:
        errors.append("`figures/manifest.json` 缺少技术路线图或问题分析流程图条目。")
    else:
        if not any(str(item.get("source", "")).replace("\\", "/").startswith("手绘图/") and str(item.get("generator", "")).lower() in {"drawio", "imagegen", "image gen", "openai-imagegen"} for item in roadmap_items):
            errors.append("技术路线图 source 必须位于 `手绘图/` 且 generator 与锁定模式一致。")
        if not any(any(normalized(exp).startswith("手绘图/") and Path(exp).suffix.lower() in EXPORT_SUFFIXES for exp in item_exports(item)) for item in roadmap_items):
            errors.append("技术路线图 manifest 条目必须记录 `手绘图/` 下的 PNG/SVG/PDF 导出图。")

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
    else:
        tex = read_text(tex_path)
        include_lines = [line for line in tex.splitlines() if "\\includegraphics" in line]
        roadmap_refs = [line for line in include_lines if any(token in line for token in ("技术路线", "路线图", "roadmap", "手绘图"))]
        if not roadmap_refs:
            errors.append("`论文/main.tex` 未用 `\\includegraphics` 插入技术路线图。")

    return write_report(not errors, "check_roadmap_in_paper", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
