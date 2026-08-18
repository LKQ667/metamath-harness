#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check visible paper prose for mechanical transitions and bracket density."""

from __future__ import annotations

import re
from pathlib import Path

from common import paper_body_region, project_arg, read_text, write_report


FORBIDDEN_TRANSITIONS = ("首先", "其次", "然后", "接着")
MECHANICAL_PHRASES = (
    "值得注意的是",
    "不难发现",
    "毋庸置疑",
    "具有重要意义",
    "提供了有力支撑",
    "充分体现了",
)
MAX_BRACKET_GROUPS_PER_1000 = 4.0
MATH_ENV_RE = re.compile(
    r"\\begin\{(?:equation|align|gather|multline|split|cases|matrix|pmatrix|bmatrix)\*?\}"
    r".*?\\end\{(?:equation|align|gather|multline|split|cases|matrix|pmatrix|bmatrix)\*?\}",
    re.DOTALL,
)
CODE_ENV_RE = re.compile(
    r"\\begin\{(?:lstlisting|verbatim)\}.*?\\end\{(?:lstlisting|verbatim)\}",
    re.DOTALL,
)
DISPLAY_MATH_RE = re.compile(r"\\\[.*?\\\]", re.DOTALL)
INLINE_MATH_RE = re.compile(r"\$[^$]*\$|\\\([^)]*\\\)")
REMOVED_COMMAND_RE = re.compile(
    r"\\(?:label|ref|eqref|autoref|cite|citep|citet|url|href|includegraphics|input|include)"
    r"\*?(?:\[[^\]]*\])?\{[^{}]*\}"
)
ENV_COMMAND_RE = re.compile(r"\\(?:begin|end)\{[^{}]*\}(?:\[[^\]]*\])?")
COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?")
CITATION_RE = re.compile(r"\[\s*\d+(?:\s*[-,，]\s*\d+)*\s*\]")
COMMENT_RE = re.compile(r"(?<!\\)%.*")


def prose_scope(text: str) -> tuple[str, list[str]]:
    body, errors = paper_body_region(text)
    if errors:
        return "", errors
    markers = ("\\renewcommand{\\refname}", "\\begin{thebibliography}")
    end = len(body)
    for marker in markers:
        pos = body.find(marker)
        if pos != -1:
            end = min(end, pos)
    return body[:end], []


def visible_prose(text: str) -> str:
    text = CODE_ENV_RE.sub(" ", text)
    text = MATH_ENV_RE.sub(" ", text)
    text = DISPLAY_MATH_RE.sub(" ", text)
    text = INLINE_MATH_RE.sub(" ", text)
    text = "\n".join(COMMENT_RE.sub("", line) for line in text.splitlines())
    text = REMOVED_COMMAND_RE.sub(" ", text)
    text = ENV_COMMAND_RE.sub(" ", text)
    text = CITATION_RE.sub(" ", text)
    text = COMMAND_RE.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", text).strip()


def bracket_groups(text: str) -> int:
    return text.count("（") + text.count("【") + text.count("[")


def main() -> int:
    parser = project_arg("检查论文自然文风、机械连接词和括号密度")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []
    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_paper_prose_style", errors, args.output)
    scope, boundary_errors = prose_scope(read_text(tex_path))
    if boundary_errors:
        return write_report(False, "check_paper_prose_style", boundary_errors, args.output)
    prose = visible_prose(scope)
    for token in FORBIDDEN_TRANSITIONS:
        count = prose.count(token)
        if count:
            errors.append(f"论文可见论述出现机械连接词“{token}” {count} 次。")
    for phrase in MECHANICAL_PHRASES:
        count = prose.count(phrase)
        if count >= 2:
            errors.append(f"论文可见论述重复套话“{phrase}” {count} 次，应改用具体证据推进论证。")
    chars = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", prose))
    groups = bracket_groups(prose)
    density = groups * 1000 / max(chars, 1)
    if density > MAX_BRACKET_GROUPS_PER_1000:
        errors.append(
            f"论文可见论述括号密度为每千字 {density:.2f} 组，"
            f"超过 {MAX_BRACKET_GROUPS_PER_1000:.0f} 组限制。"
        )
    return write_report(not errors, "check_paper_prose_style", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
