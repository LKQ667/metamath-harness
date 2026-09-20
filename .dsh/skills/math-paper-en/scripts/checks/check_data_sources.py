#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check project data directory and data source mapping."""

from __future__ import annotations

import re
from pathlib import Path

from common import iter_project_files, project_arg, read_text, write_report


DATA_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".txt", ".parquet", ".feather", ".pkl", ".zip", ".rar", ".7z"}
DOC_SUFFIXES = {".md", ".tex", ".py"}
SOURCE_HINTS = ("数据集", "附件", "爬取", "下载", "API", "接口", "原始数据", "样本数据", "外部数据")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
FILE_REF_RE = re.compile(r"(赛题/[^\\s,，；;]+|data/[^\\s,，；;]+|附件\\d+[^\\s,，；;]*\\.(?:csv|tsv|xlsx|xls|json|txt|parquet|feather|pkl|zip|rar|7z))", re.IGNORECASE)
GENERATED_HINTS = ("随机生成", "模拟数据", "虚构数据", "伪造数据")


def data_files(project: Path) -> list[Path]:
    base = project / "data"
    if not base.exists():
        return []
    return sorted(
        [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in DATA_SUFFIXES],
        key=lambda p: str(p.relative_to(project)).lower(),
    )


def normalized_rel(path: Path, project: Path) -> str:
    return path.relative_to(project).as_posix()


def main() -> int:
    parser = project_arg("检查 data/ 目录与数据来源清单。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []

    data_dir = project / "data"
    source_map = data_dir / "source_map.md"
    if not data_dir.exists():
        errors.append("缺少 data/ 目录。")
        return write_report(False, "check_data_sources", errors, args.output)

    if not source_map.exists():
        errors.append("缺少 data/source_map.md。")
        return write_report(False, "check_data_sources", errors, args.output)

    text = read_text(source_map)
    if not text.strip():
        errors.append("data/source_map.md 为空。")
        return write_report(False, "check_data_sources", errors, args.output)

    urls = URL_RE.findall(text)
    file_refs = {m.group(1).strip().rstrip(").,，；;") for m in FILE_REF_RE.finditer(text)}
    if not urls and not file_refs:
        errors.append("data/source_map.md 未写明任何 URL 或具体文件依据。")

    required_tokens = ("数据名称", "用途", "来源类型", "具体依据")
    for token in required_tokens:
        if token not in text:
            errors.append(f"data/source_map.md 缺少字段提示: {token}")

    for hint in GENERATED_HINTS:
        if hint in text and "上游源文件" not in text and "生成脚本" not in text and "处理说明" not in text:
            errors.append(f"data/source_map.md 提到“{hint}”，但未说明上游源文件或生成依据。")

    actual_files = data_files(project)
    if actual_files:
        if len(actual_files) == 1 and normalized_rel(actual_files[0], project) == "data/source_map.md":
            errors.append("data/ 目录只有 source_map.md，没有任何实际数据文件。")
        else:
            for path in actual_files:
                rel = normalized_rel(path, project)
                if rel == "data/source_map.md":
                    continue
                if rel not in text:
                    errors.append(f"数据文件未在 data/source_map.md 中登记: {rel}")

    doc_files = [p for p in iter_project_files(project, DOC_SUFFIXES) if p.name != "source_map.md"]
    hinted = False
    for path in doc_files:
        doc_text = read_text(path)
        if any(token in doc_text for token in SOURCE_HINTS):
            hinted = True
            break
    if hinted and not (urls or file_refs):
        errors.append("项目文档提到了数据来源相关内容，但 data/source_map.md 未提供可核验的 URL 或文件依据。")

    return write_report(not errors, "check_data_sources", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
