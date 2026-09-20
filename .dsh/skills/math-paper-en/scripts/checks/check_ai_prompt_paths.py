#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check AI prompt paths, structure, pollution gate, and differentiation gate."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, read_text, write_report
from ai_prompt_common import (
    META_LABELS,
    NO_RENDER_TOKENS,
    NO_COPY_TOKENS,
    POLLUTION_TOKENS,
    PROMPT_PATH_RE,
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
    prompt_dir = project / "手绘图"
    prompt_files = sorted(path for path in prompt_dir.glob("*.md") if is_prompt_file(path)) if prompt_dir.exists() else []
    prompt_meta: dict[str, tuple[str, str, str, str]] = {}

    for rel in refs:
        prompt_path = project / rel
        if not prompt_path.exists():
            errors.append(f"论文引用的 AI 绘图提示词文件不存在: {rel}")
            continue
        if not prompt_path.is_file():
            errors.append(f"论文引用的 AI 绘图提示词路径不是文件: {rel}")
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
        service = sections.get("服务段落", "")
        prompt = sections.get("生成图片的提示词", "")
        hard = sections.get("硬约束", "")
        if not any(token in service for token in ("论文", "段落", "章节", "位置", "用于", "放置")):
            errors.append(f"AI 绘图提示词的服务段落未说明放置位置: {rel}")
        if not any(token in service for token in ("依据", "来自", "基于", "根据")):
            errors.append(f"AI 绘图提示词的服务段落未说明论文依据: {rel}")
        if not any(token in service for token in ("知识", "方法", "模型", "原理", "机制")):
            errors.append(f"AI 绘图提示词的服务段落未说明用到的知识或方法: {rel}")
        if not any(token in prompt for token in RELATION_TOKENS):
            errors.append(f"AI 绘图提示词未说明输入-机制-输出或关键关系: {rel}")
        if REFERENCE_LABEL not in prompt or REFERENCE_PATH_TOKEN not in prompt:
            errors.append(f"AI 绘图提示词未明确引用本 skill 内置参考图组: {rel}")
        if REFERENCE_BORROW_LABEL not in prompt or not all(token in prompt for token in REFERENCE_BORROW_TOKENS):
            errors.append(f"AI 绘图提示词未明确写出参考图组借鉴点（框架/结构/排版/思维链/配色）: {rel}")
        if not any(token in (prompt + "\n" + hard) for token in NO_COPY_TOKENS):
            errors.append(f"AI 绘图提示词未声明“仅借鉴形式，不复制具体内容、数据、标签、结论”: {rel}")
        for label in META_LABELS:
            if label not in extract_meta(prompt):
                errors.append(f"AI 绘图提示词缺少差异化元信息“{label}”: {rel}")
        hits = [token for token in POLLUTION_TOKENS if token in prompt]
        if hits:
            errors.append(f"AI 绘图提示词正文含有污染词 {rel}: " + "、".join(hits))
        vague_hits = [token for token in VAGUE_TOKENS if token in prompt]
        if vague_hits:
            errors.append(f"AI 绘图提示词正文含有空泛绘图词 {rel}: " + "、".join(vague_hits))
        hard_hits = [token for token in POLLUTION_TOKENS if token in hard]
        if hard_hits and not any(token in hard for token in NO_RENDER_TOKENS):
            errors.append(f"AI 绘图提示词硬约束提到流程污染词但未声明“不渲染为图内可见文字”: {rel}")
        meta = extract_meta(prompt)
        if len(meta) == 4:
            prompt_meta[rel] = tuple(meta.get(label, "") for label in META_LABELS)

    if len(prompt_files) > 1:
        by_signature: dict[tuple[str, str, str, str], list[str]] = {}
        for rel, signature in prompt_meta.items():
            by_signature.setdefault(signature, []).append(rel)
        for signature, files in by_signature.items():
            if len(files) > 1:
                errors.append(
                    "同批 AI 绘图提示词的布局原型、阅读方向、主色家族、区分点完全相同: "
                    + "、".join(files)
                )

    return write_report(not errors, "check_ai_prompt_paths", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
