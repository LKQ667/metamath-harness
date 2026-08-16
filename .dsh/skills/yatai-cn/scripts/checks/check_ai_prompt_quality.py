#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check AI figure prompts are detailed, traceable, and non-fabricating."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report
from ai_prompt_common import (
    META_LABELS,
    NO_RENDER_TOKENS,
    NO_COPY_TOKENS,
    POLLUTION_TOKENS,
    REFERENCE_BORROW_LABEL,
    REFERENCE_BORROW_TOKENS,
    REFERENCE_LABEL,
    REFERENCE_PATH_TOKEN,
    RELATION_TOKENS,
    VAGUE_TOKENS,
    extract_meta,
    is_prompt_file,
    parse_prompt_sections,
)


MIN_CHARS = 420


def main() -> int:
    parser = project_arg("检查 AI 绘图提示词是否足够严谨、细致、可追溯。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    prompt_dir = project / "手绘图"
    errors: list[str] = []

    if not prompt_dir.exists():
        errors.append("缺少 `手绘图/` 目录，无法检查 AI 绘图提示词。")
        return write_report(False, "check_ai_prompt_quality", errors, args.output)

    prompt_files = sorted(path for path in prompt_dir.glob("*.md") if is_prompt_file(path))
    if len(prompt_files) < 3:
        errors.append("原理图、模型图、概念示意图为必交内容，至少需要 3 份 `手绘图/*.md` 提示词。")

    signatures: dict[tuple[str, str, str, str], list[str]] = {}

    for path in prompt_files:
        rel = path.relative_to(project).as_posix()
        text = read_text(path).strip()
        compact_len = len("".join(text.split()))
        if compact_len < MIN_CHARS:
            errors.append(f"AI 绘图提示词过短，难以支撑严谨绘图: {rel}（有效字符约 {compact_len}）")
        sections, parse_errors = parse_prompt_sections(text)
        for item in parse_errors:
            errors.append(f"AI 绘图提示词结构不合法 {rel}: {item}")
        if parse_errors:
            continue
        prompt = sections.get("生成图片的提示词", "")
        hard = sections.get("硬约束", "")
        if not any(token in prompt for token in RELATION_TOKENS):
            errors.append(f"AI 绘图提示词未说明输入-机制-输出或作用关系: {rel}")
        if REFERENCE_LABEL not in prompt or REFERENCE_PATH_TOKEN not in prompt:
            errors.append(f"AI 绘图提示词未明确引用本 skill 内置参考图组: {rel}")
        if REFERENCE_BORROW_LABEL not in prompt or not all(token in prompt for token in REFERENCE_BORROW_TOKENS):
            errors.append(f"AI 绘图提示词未明确写出参考图组借鉴点（框架/结构/排版/思维链/配色）: {rel}")
        if not any(token in (prompt + "\n" + hard) for token in NO_COPY_TOKENS):
            errors.append(f"AI 绘图提示词未声明“仅借鉴形式，不复制具体内容、数据、标签、结论”: {rel}")
        meta = extract_meta(prompt)
        for label in META_LABELS:
            if label not in meta:
                errors.append(f"AI 绘图提示词缺少差异化元信息“{label}”: {rel}")
        pollution_hits = [token for token in POLLUTION_TOKENS if token in prompt]
        if pollution_hits:
            errors.append(f"AI 绘图提示词正文含有污染词 {rel}: " + "、".join(pollution_hits))
        vague_hits = [token for token in VAGUE_TOKENS if token in prompt]
        if vague_hits:
            errors.append(f"AI 绘图提示词包含空泛绘图词 {rel}: " + "、".join(vague_hits))
        hard_hits = [token for token in POLLUTION_TOKENS if token in hard]
        if hard_hits and not any(token in hard for token in NO_RENDER_TOKENS):
            errors.append(f"AI 绘图提示词硬约束提到流程污染词但未声明“不渲染为图内可见文字”: {rel}")
        if len(meta) == 4:
            signatures.setdefault(tuple(meta.get(label, "") for label in META_LABELS), []).append(rel)

    for signature, files in signatures.items():
        if len(files) > 1:
            errors.append("同批 AI 绘图提示词在布局原型/阅读方向/主色家族/区分点上完全同构: " + "、".join(files))

    return write_report(not errors, "check_ai_prompt_quality", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
