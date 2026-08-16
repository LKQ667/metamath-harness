#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check AI figure prompt paths referenced by the paper."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report
from ai_prompt_common import PROMPT_PATH_RE, is_prompt_file, parse_prompt_sections


REQUIRED_TYPES = ("原理图", "模型图", "概念示意图")


def main() -> int:
    parser = project_arg("检查论文中显示的 AI 绘图提示词相对路径是否存在且非空。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_ai_prompt_paths", errors, args.output)

    tex = read_text(tex_path)
    refs = sorted(set(PROMPT_PATH_RE.findall(tex)))
    prompt_files = sorted(path for path in (project / "手绘图").glob("*.md") if is_prompt_file(path)) if (project / "手绘图").exists() else []
    if len(prompt_files) < 3:
        errors.append("原理图、模型图、概念示意图为必交内容，`手绘图/` 至少需要 3 份提示词文件。")

    all_prompt_text = ""
    for prompt_file in prompt_files:
        all_prompt_text += "\n" + read_text(prompt_file)
        rel = prompt_file.relative_to(project).as_posix()
        if rel not in refs:
            errors.append(f"AI 绘图提示词文件未在论文中显示相对路径: {rel}")

    for figure_type in REQUIRED_TYPES:
        if figure_type not in all_prompt_text:
            errors.append(f"AI 绘图提示词未覆盖必交图类型: {figure_type}")

    for rel in refs:
        prompt_path = project / rel
        if not prompt_path.exists():
            errors.append(f"论文引用的 AI 绘图提示词文件不存在: {rel}")
            continue
        content = read_text(prompt_path).strip()
        if not content:
            errors.append(f"论文引用的 AI 绘图提示词文件为空: {rel}")
            continue
        sections, parse_errors = parse_prompt_sections(content)
        for item in parse_errors:
            errors.append(f"AI 绘图提示词结构不合法 {rel}: {item}")
        if parse_errors:
            continue
        if not sections.get("服务段落", "").strip():
            errors.append(f"AI 绘图提示词缺少服务段落正文: {rel}")
        if not sections.get("生成图片的提示词", "").strip():
            errors.append(f"AI 绘图提示词缺少生成图片的提示词正文: {rel}")
        if not sections.get("硬约束", "").strip():
            errors.append(f"AI 绘图提示词缺少硬约束正文: {rel}")

    return write_report(not errors, "check_ai_prompt_paths", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
