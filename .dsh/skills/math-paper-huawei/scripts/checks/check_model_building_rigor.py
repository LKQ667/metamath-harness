#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check model-building section contains formula-driven rigorous reasoning."""

from __future__ import annotations

import re
from pathlib import Path

from common import project_arg, read_text, write_report


SECTION_RE = re.compile(r"(?m)^\\section\*?\{([^{}]+)\}")
DISPLAY_MATH_RE = re.compile(r"\\begin\{(?:equation|align|gather|multline|split)\*?\}|\\\[|\\\]")
INLINE_MATH_RE = re.compile(r"(?<!\\)\$[^$\n]{2,}?(?<!\\)\$")
DERIVATION_TOKENS = ("推导", "得到", "可得", "因此", "由此", "代入", "化简", "构造", "定义")
TARGET_TOKENS = ("目标函数", "目标", "最小化", "最大化", "评价函数", "损失函数")
CONSTRAINT_TOKENS = ("约束", "条件", "可行域", "范围", "边界", "适用条件")
SOLVE_TOKENS = ("求解", "算法", "迭代", "步骤", "流程", "优化", "计算")
RESULT_TOKENS = ("结果", "解释", "说明", "验证", "合理性", "结论")
PARAM_TOKENS = ("变量", "参数", "符号", "定义", "权重", "指标")


def section_block(text: str, title: str) -> str:
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1).strip() != title:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return text[match.start():end]
    return ""


def count_any(text: str, tokens: tuple[str, ...]) -> int:
    return sum(text.count(token) for token in tokens)


def main() -> int:
    parser = project_arg("检查五、模型建立与求解是否具备公式推导和论证深度")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_model_building_rigor", errors, args.output)

    text = read_text(tex_path)
    block = section_block(text, "模型建立与求解")
    if not block:
        errors.append("缺少“五、模型建立与求解”章节。")
        return write_report(False, "check_model_building_rigor", errors, args.output)

    display_math = len(DISPLAY_MATH_RE.findall(block))
    inline_math = len(INLINE_MATH_RE.findall(block))
    if display_math < 3 and inline_math < 8:
        errors.append("“模型建立与求解”公式推导痕迹不足；页数不足时只能回到本节深化公式与论证。")

    checks = (
        ("变量/参数定义", PARAM_TOKENS),
        ("目标函数或评价目标", TARGET_TOKENS),
        ("约束或适用条件", CONSTRAINT_TOKENS),
        ("推导连接", DERIVATION_TOKENS),
        ("求解步骤", SOLVE_TOKENS),
        ("结果解释", RESULT_TOKENS),
    )
    for label, tokens in checks:
        if count_any(block, tokens) == 0:
            errors.append(f"“模型建立与求解”缺少{label}证据；不得用新增主章节或套话替代模型深化。")

    if len(re.findall(r"(?m)^\\subsection\*?\{", block)) < 2:
        errors.append("“模型建立与求解”应按问题或模型层次展开，至少包含 2 个小节。")

    return write_report(not errors, "check_model_building_rigor", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
