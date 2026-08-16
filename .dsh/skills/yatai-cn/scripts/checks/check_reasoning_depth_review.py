#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the reasoning and derivation review is present."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report


REQUIRED_SECTIONS = (
    "主线骨架",
    "变量定义",
    "公式推导链",
    "假设来源",
    "上下文衔接",
    "边界讨论",
    "结果回扣",
)


def main() -> int:
    parser = project_arg("检查推理论证复核是否覆盖深度写作硬约束")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    review_path = project / "检查结果" / "推理论证复核.md"
    errors: list[str] = []

    if not review_path.exists():
        errors.append(f"缺少推理论证复核文件: {review_path}")
        return write_report(False, "check_reasoning_depth_review", errors, args.output)

    text = read_text(review_path)
    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"推理论证复核缺少“{section}”部分。")

    if "待补" in text or "TODO" in text.upper():
        errors.append("推理论证复核仍包含待补内容。")
    if len(text.strip()) < 400:
        errors.append("推理论证复核内容过短，无法支撑公式推导、上下文衔接和边界讨论。")

    return write_report(not errors, "check_reasoning_depth_review", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
