#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the English paper prose for mechanical transitions and bracket density."""

from __future__ import annotations

import re
from pathlib import Path

from common import paper_body_region, project_arg, read_text, write_report


DOLLAR = chr(36)
FORBIDDEN_TRANSITIONS = (
    "Firstly",
    "Secondly",
    "Thirdly",
    "First of all",
    "Last but not least",
    "In conclusion",
    "To sum up",
    "As we all know",
)
LIMITED_PHRASES = (
    "Moreover,",
    "Furthermore,",
    "In addition,",
    "It is worth noting that",
    "It is important to note that",
    "It is obvious that",
    "Obviously,",
    "Clearly,",
    "Needless to say",
)
MAX_LIMITED_TOTAL = 6
MAX_BRACKETS_PER_1000 = 6.0
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")
CODE_ENV_RE = re.compile(r"\\begin\{(?:lstlisting|verbatim)\}.*?\\end\{(?:lstlisting|verbatim)\}", re.DOTALL)
MATH_ENV_RE = re.compile(
    r"\\begin\{(?:equation|align|gather|multline|split|cases|matrix|pmatrix|bmatrix)\*?\}"
    r".*?\\end\{(?:equation|align|gather|multline|split|cases|matrix|pmatrix|bmatrix)\*?\}",
    re.DOTALL,
)
DISPLAY_MATH_RE = re.compile(r"\\\[.*?\\\]", re.DOTALL)
INLINE_MATH_RE = re.compile(r"\\\(.*?\\\)|" + re.escape(DOLLAR) + r"[^" + re.escape(DOLLAR) + r"]*" + re.escape(DOLLAR))
REMOVED_COMMAND_RE = re.compile(
    r"\\(?:label|ref|eqref|autoref|cite|citep|citet|url|href|includegraphics|input|include)"
    r"\*?(?:\[[^\]]*\])?\{[^{}]*\}"
)
ENV_COMMAND_RE = re.compile(r"\\(?:begin|end)\{[^{}]*\}(?:\[[^\]]*\])?")
COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?")
COMMENT_RE = re.compile(r"(?<!\\)" + chr(37) + r".*")


def prose_scope(text: str) -> tuple[str, list[str]]:
    body, errors = paper_body_region(text)
    if errors:
        return "", errors
    end = len(body)
    for marker in (r"\renewcommand{\refname}", r"\begin{thebibliography}"):
        pos = body.find(marker)
        if pos != -1:
            end = min(end, pos)
    return body[:end], []


def visible_prose(text: str) -> str:
    text = CODE_ENV_RE.sub(" ", text)
    text = MATH_ENV_RE.sub(" ", text)
    text = DISPLAY_MATH_RE.sub(" ", text)
    text = INLINE_MATH_RE.sub(" ", text)
    text = chr(10).join(COMMENT_RE.sub("", line) for line in text.splitlines())
    text = REMOVED_COMMAND_RE.sub(" ", text)
    text = ENV_COMMAND_RE.sub(" ", text)
    text = COMMAND_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text.replace("{", " ").replace("}", " ")).strip()


def bracket_groups(text: str) -> int:
    return text.count("(") + text.count("[") + text.count("【")


def main() -> int:
    parser = project_arg("检查英文论文自然文风、机械连接词、括号密度与中文残留")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    tex_path = project / "论文" / "main.tex"
    errors: list[str] = []
    if not tex_path.exists():
        return write_report(False, "check_paper_prose_style", [f"缺少论文主文件: {tex_path}"], args.output)
    scope, boundary_errors = prose_scope(read_text(tex_path))
    if boundary_errors:
        return write_report(False, "check_paper_prose_style", boundary_errors, args.output)
    prose = visible_prose(scope)

    cjk_hits = CJK_RE.findall(prose)
    if cjk_hits:
        errors.append(f"论文可见论述出现 {len(cjk_hits)} 个中文字符，美赛交付论文必须全英文。")

    for token in FORBIDDEN_TRANSITIONS:
        count = len(re.findall(r"(?<![A-Za-z])" + re.escape(token), prose))
        if count:
            errors.append(f"论文可见论述出现机械连接词 {token} 共 {count} 次。")

    limited_total = 0
    for phrase in LIMITED_PHRASES:
        count = prose.count(phrase)
        limited_total += count
        if count >= 3:
            errors.append(f"论文可见论述重复套话 {phrase} 共 {count} 次，应改用具体证据推进论证。")
    if limited_total > MAX_LIMITED_TOTAL:
        errors.append(f"过渡与强调套话合计 {limited_total} 次，超过 {MAX_LIMITED_TOTAL} 次上限。")

    words = len(WORD_RE.findall(prose))
    groups = bracket_groups(prose)
    density = groups * 1000 / max(words, 1)
    if density > MAX_BRACKETS_PER_1000:
        errors.append(
            f"论文可见论述括号密度为每千词 {density:.2f} 组，超过 {MAX_BRACKETS_PER_1000:.0f} 组限制。"
        )
    return write_report(not errors, "check_paper_prose_style", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
