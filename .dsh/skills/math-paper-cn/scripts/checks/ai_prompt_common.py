#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared AI prompt parsing helpers for math-paper-cn checks."""

from __future__ import annotations

import re
from pathlib import Path


PROMPT_PATH_RE = re.compile(r"(?:手绘图|AI绘图|ai绘图)/[^\s{}\\\\，。、；：,;:]+\.md")
POLLUTION_TOKENS = ("禁止编造", "禁止造假", "结果复核", "三轮复核", "不得抄袭", "可复现", "可信输出")
META_LABELS = ("布局原型", "阅读方向", "主色家族", "区分点")
RELATION_TOKENS = ("输入", "机制", "输出", "关系", "路径", "传播", "状态", "约束")
NO_RENDER_TOKENS = ("不渲染为图内可见文字", "不要渲染为图内可见文字", "不作为图中标签", "不写入图内可见文字")
ALLOWED_H2 = ("服务段落", "生成图片的提示词", "硬约束")
VAGUE_TOKENS = ("美观大气", "高级感", "科技感", "丰富细节", "随意发挥")
REFERENCE_PATH_TOKEN = "assets/reference-pictures/"
REFERENCE_LABEL = "参考图组"
REFERENCE_BORROW_LABEL = "借鉴点"
REFERENCE_BORROW_TOKENS = ("框架", "结构", "排版", "思维链", "配色")
NO_COPY_TOKENS = (
    "仅借鉴形式，不复制具体内容、数据、标签、结论",
    "仅借鉴形式，不复制具体内容",
    "只借鉴形式，不复制具体内容、数据、标签、结论",
    "不复制具体内容、数据、标签、结论",
)
FORBIDDEN_EXTERNAL_PICTURE_PATHS = ("AI-Draw skills\\pictures",)


def is_prompt_file(path: Path) -> bool:
    return path.suffix.lower() == ".md" and path.name.lower() != "readme.md"


def normalize_heading(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


def parse_prompt_sections(text: str) -> tuple[dict[str, str], list[str]]:
    sections: dict[str, list[str]] = {}
    errors: list[str] = []
    current: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("###"):
            errors.append("不允许使用 H3 或更深层级标题。")
            continue
        if stripped.startswith("# "):
            errors.append("不允许使用 H1 标题。")
            continue
        if stripped.startswith("##"):
            heading = normalize_heading(stripped[2:])
            matched = next((name for name in ALLOWED_H2 if normalize_heading(name) == heading), None)
            if matched is None:
                errors.append(f"存在不允许的二级标题: {stripped}")
                current = None
                continue
            if matched in sections:
                errors.append(f"二级标题重复: {matched}")
            sections.setdefault(matched, [])
            current = matched
            continue
        if current is not None:
            sections[current].append(line)
    missing = [name for name in ALLOWED_H2 if name not in sections]
    if missing:
        errors.append("缺少必需的二级标题: " + "、".join(missing))
    if sections and len(sections) != 3:
        errors.append("提示词文件必须且只能包含 3 个顶层 H2 区块。")
    return {key: "\n".join(value).strip() for key, value in sections.items()}, errors


def extract_meta(prompt_text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    labels_pattern = "|".join(re.escape(label) for label in META_LABELS)
    for label in META_LABELS:
        match = re.search(
            rf"{re.escape(label)}\s*[:：]\s*(.*?)(?=(?:{labels_pattern})\s*[:：]|$)",
            prompt_text,
            flags=re.S,
        )
        if match:
            meta[label] = re.sub(r"\s+", " ", match.group(1).strip())
    return meta
