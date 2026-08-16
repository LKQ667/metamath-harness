#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check that required draw.io paper diagrams exist and are traceable."""

from __future__ import annotations

import json
from pathlib import Path

from common import load_manifest_items, project_arg, write_report


EXPORT_SUFFIXES = {".png", ".svg", ".pdf"}


def item_text(item: dict) -> str:
    parts: list[str] = []
    for value in item.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
        elif isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    return "\n".join(parts).replace("\\", "/")


def has_drawio_manifest_entry(items: list[dict]) -> bool:
    for item in items:
        text = item_text(item)
        if ".drawio" in text and ("手绘图/" in text or "手绘图" in text):
            return True
    return False


def main() -> int:
    parser = project_arg("检查 Step4 前是否已经生成 draw.io 源文件、导出图和 manifest 记录。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    state_path = project / "项目状态.json"
    if state_path.exists():
        try:
            if json.loads(state_path.read_text(encoding="utf-8")).get("drawing_mode") != "drawio":
                return write_report(True, "check_drawio_required", [], args.output)
        except Exception:
            pass

    hand_dir = project / "手绘图"
    drawio_files = sorted(hand_dir.glob("*.drawio")) if hand_dir.exists() else []
    export_files = sorted([p for p in hand_dir.glob("*") if p.is_file() and p.suffix.lower() in EXPORT_SUFFIXES]) if hand_dir.exists() else []

    if not hand_dir.exists():
        errors.append("缺少 `手绘图/` 目录，无法接收当前技能内置 Draw.io 产物。")
    if not drawio_files:
        errors.append("`手绘图/` 中缺少 `.drawio` 源文件，说明未触发必需的 draw.io 链路。")
    if not export_files:
        errors.append("`手绘图/` 中缺少 PNG/SVG/PDF 导出图，不能直接入文。")

    if drawio_files and export_files:
        export_stems = {p.stem for p in export_files}
        missing_export = [p.name for p in drawio_files if p.stem not in export_stems]
        if missing_export:
            errors.append("以下 `.drawio` 缺少同名导出图: " + "、".join(missing_export))

    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)
    if items and not has_drawio_manifest_entry(items):
        errors.append("`figures/manifest.json` 缺少指向 `手绘图/*.drawio` 的流程图条目。")

    return write_report(not errors, "check_drawio_required", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
