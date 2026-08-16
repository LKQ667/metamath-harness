#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick static validation for the yatai-cn skill package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FILES = (
    "SKILL.md",
    "AGENT.md",
    "references/workflow.md",
    "references/auto-checklist.md",
    "references/visual-style.md",
    "references/template-notes.md",
    "scripts/checks/run_all_checks.py",
    "scripts/checks/check_handdraw_readme.py",
    "scripts/checks/check_ai_prompt_alignment.py",
    "scripts/checks/check_main_tex_compile_record.py",
    "手绘图/README.md",
    "assets/templates/handdraw/README.md",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="快速校验 yatai-cn skill 静态结构。")
    parser.add_argument("--skill", default=str(Path(__file__).resolve().parents[2]), help="yatai-cn skill 根目录")
    args = parser.parse_args()
    root = Path(args.skill).resolve()
    errors: list[str] = []

    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        errors.append("缺少 SKILL.md")
    else:
        text = read_text(skill_md)
        if not text.startswith("---"):
            errors.append("SKILL.md 缺少 YAML frontmatter")
        if "name: yatai-cn" not in text:
            errors.append("SKILL.md frontmatter 缺少 name: yatai-cn")

    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            errors.append(f"缺少必需文件: {rel}")

    guarded_files = [root / "SKILL.md", root / "AGENT.md", *sorted((root / "references").glob("*.md"))]
    for path in guarded_files:
        if path.exists() and "F:\\yatai-cn" in read_text(path):
            errors.append(f"workflow 规则中存在禁止写入的固定路径: {path.relative_to(root).as_posix()}")

    report = {"check": "quick_validate", "ok": not errors, "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
