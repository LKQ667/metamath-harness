#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared helpers for yatai-cn deliverable checks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def project_arg(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--project", required=True, help="数学建模项目根目录")
    parser.add_argument("--output", help="可选 JSON 报告输出路径")
    return parser


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(ok: bool, check: str, errors: list[str], output: str | None = None) -> int:
    report = {"check": check, "ok": ok, "errors": errors}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if ok else 1


def final_results_path(project: Path) -> Path:
    return project / "results" / "final_results.json"


def manifest_path(project: Path) -> Path:
    return project / "figures" / "manifest.json"


def numeric_values(obj: Any, prefix: str = "") -> dict[str, float]:
    values: dict[str, float] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            values.update(numeric_values(value, child))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            child = f"{prefix}[{index}]"
            values.update(numeric_values(value, child))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        values[prefix] = float(obj)
    return values


def find_numbers(text: str) -> list[float]:
    pattern = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?")
    return [float(m.group(0)) for m in pattern.finditer(text)]


def iter_project_files(project: Path, suffixes: tuple[str, ...]) -> list[Path]:
    ignored = {".venv", "__pycache__", ".git", "node_modules", "检查结果"}
    files: list[Path] = []
    for path in project.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            files.append(path)
    return files


def load_manifest_items(project: Path) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    path = manifest_path(project)
    if not path.exists():
        return [], [f"缺少图片清单: {path}"]
    try:
        data = load_json(path)
    except Exception as exc:
        return [], [f"图片清单 JSON 解析失败: {exc}"]
    items = data.get("items", data.get("figures")) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return [], ["图片清单必须是列表或包含 items/figures 列表的对象"]
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            errors.append(f"图片清单条目不是对象: {item!r}")
    return normalized, errors
