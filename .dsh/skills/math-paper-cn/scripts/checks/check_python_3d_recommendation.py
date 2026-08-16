#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check top-journal Chinese 3D figure recommendation is reviewed."""

from __future__ import annotations

from pathlib import Path

from common import load_manifest_items, project_arg, read_text, write_report


REVIEW_TOKEN = "顶刊一区中文三维图可行性评估"


def is_python_item(item: dict) -> bool:
    source = str(item.get("source", "")).lower()
    return item.get("generator") == "python" or source.endswith(".py")


def is_3d_item(item: dict) -> bool:
    qa = item.get("qa") if isinstance(item.get("qa"), dict) else {}
    text = " ".join(str(item.get(key, "")) for key in ("chart_family", "template_id", "source", "title")).lower()
    return "3d" in text or "三维" in text or qa.get("top_journal_cn_3d_recommended") is True


def main() -> int:
    parser = project_arg("检查顶刊一区中文三维图强建议是否经过可行性评估")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    review_path = project / "检查结果" / "三轮自查.md"
    errors: list[str] = []
    items, manifest_errors = load_manifest_items(project)
    errors.extend(manifest_errors)

    python_items = [item for item in items if is_python_item(item)]
    used_3d = any(is_3d_item(item) for item in python_items)

    if not review_path.exists():
        errors.append(f"缺少三轮自查文件，无法确认{REVIEW_TOKEN}: {review_path}")
    else:
        review = read_text(review_path)
        if REVIEW_TOKEN not in review:
            errors.append(f"三轮自查缺少“{REVIEW_TOKEN}”，不得静默忽略三维图强建议。")
        elif not used_3d and not any(token in review for token in ("不采用", "放弃", "不适用", "无需三维", "二维更清晰")):
            errors.append("未使用三维图时，三轮自查需说明不采用三维图的原因。")

    return write_report(not errors, "check_python_3d_recommendation", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
