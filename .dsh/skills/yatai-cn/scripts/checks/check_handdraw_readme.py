#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查手绘图 README 是否说明项目级双绘图模式。"""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report


REQUIRED_GROUPS = {
    "模式选路": ("Draw.io 绘图", "AI 全自动绘图"),
    "状态锁定": ("drawing_mode", "项目状态.json"),
    "manifest": ("figures/manifest.json",),
    "提示词范围": ("手绘图/*.md", "`手绘图/*.md`"),
    "自动生图": ("Image Gen", "imagegen"),
    "自动回填": ("自动回填", "回填"),
    "失败阻断": ("硬阻断", "不得交付"),
}


def main() -> int:
    parser = project_arg("检查 `手绘图/README.md` 是否说明后续图片生成与回填协议。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    readme = project / "手绘图" / "README.md"
    errors: list[str] = []

    if not readme.exists():
        errors.append("缺少 `手绘图/README.md`，无法约束后续 AI 绘图生成与论文回填流程。")
        return write_report(False, "check_handdraw_readme", errors, args.output)

    text = read_text(readme).strip()
    if not text:
        errors.append("`手绘图/README.md` 为空。")
        return write_report(False, "check_handdraw_readme", errors, args.output)

    for name, tokens in REQUIRED_GROUPS.items():
        if not any(token in text for token in tokens):
            errors.append(f"`手绘图/README.md` 缺少{name}说明。")

    return write_report(not errors, "check_handdraw_readme", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
