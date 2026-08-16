#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check AI figure prompts are aligned with problem, paper, code, results, and symbols."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report
from ai_prompt_common import NO_COPY_TOKENS, REFERENCE_LABEL, REFERENCE_PATH_TOKEN, is_prompt_file, parse_prompt_sections


FORMULA_TOKENS = ("公式", "符号", "变量名", "方程", "$", "\\(", "\\[", "\\frac", "\\sum", "\\hat", "\\alpha", "\\beta")
CONSISTENCY_TOKENS = ("符号说明", "模型公式", "results/final_results.json", "Qn/result.md", "保持一致", "不得自行创造符号", "不得改写公式")


def main() -> int:
    parser = project_arg("检查 AI 绘图提示词是否贴合赛题、论文、代码、结果和符号公式。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    prompt_dir = project / "手绘图"
    errors: list[str] = []

    if not prompt_dir.exists():
        errors.append("缺少 `手绘图/` 目录，无法检查 AI 绘图提示词。")
        return write_report(False, "check_ai_prompt_alignment", errors, args.output)

    prompt_files = sorted(path for path in prompt_dir.glob("*.md") if is_prompt_file(path))
    if not prompt_files:
        errors.append("`手绘图/` 中缺少 AI 绘图提示词文件。")
        return write_report(False, "check_ai_prompt_alignment", errors, args.output)

    for path in prompt_files:
        rel = path.relative_to(project).as_posix()
        text = read_text(path).strip()
        sections, parse_errors = parse_prompt_sections(text)
        for item in parse_errors:
            errors.append(f"AI 绘图提示词结构不合法 {rel}: {item}")
        if parse_errors:
            continue
        service = sections.get("服务段落", "")
        prompt = sections.get("生成图片的提示词", "")
        hard = sections.get("硬约束", "")
        if not any(token in service for token in ("赛题", "题目", "问题", "Q1", "Q2", "Q3", "Q4", "问题一", "问题二", "问题三", "问题四")):
            errors.append(f"AI 绘图提示词缺少对应问题或赛题依据: {rel}")
        if not any(token in service for token in ("论文", "段落", "章节", "放置", "位置")):
            errors.append(f"AI 绘图提示词缺少论文段落或放置位置说明: {rel}")
        if not any(token in service for token in ("依据", "来自", "基于")):
            errors.append(f"AI 绘图提示词缺少论文依据说明: {rel}")
        if not any(token in service for token in ("知识", "方法", "模型", "原理", "机制")):
            errors.append(f"AI 绘图提示词缺少所用知识或方法说明: {rel}")
        if not any(token in service or token in hard for token in ("results/final_results.json", "Qn/result.md", "结果来源", "代码或结果来源", "代码依据")):
            errors.append(f"AI 绘图提示词缺少代码或结果来源约束: {rel}")
        if not any(token in service or token in hard for token in ("符号说明", "变量来源", "符号来源", "变量/符号来源")):
            errors.append(f"AI 绘图提示词缺少变量或符号来源约束: {rel}")
        if REFERENCE_LABEL not in prompt or REFERENCE_PATH_TOKEN not in prompt:
            errors.append(f"AI 绘图提示词未把内置参考图组绑定到当前论文任务: {rel}")
        if not any(token in (prompt + "\n" + hard) for token in NO_COPY_TOKENS):
            errors.append(f"AI 绘图提示词缺少“只借鉴形式、不复制参考图具体内容”的约束: {rel}")
        if any(token in prompt for token in FORMULA_TOKENS):
            merged = service + "\n" + hard
            missing = [token for token in CONSISTENCY_TOKENS if token not in merged]
            if missing:
                errors.append(f"AI 绘图提示词涉及符号或公式但一致性约束不完整 {rel}: 缺少 " + "、".join(missing))

    return write_report(not errors, "check_ai_prompt_alignment", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
