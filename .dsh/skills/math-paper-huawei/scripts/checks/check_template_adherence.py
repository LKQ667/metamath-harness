#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查论文是否保持华为杯 GMCMthesis 内置模板身份与官方结构。"""

from __future__ import annotations

import re
from pathlib import Path

from collections import Counter
from common import project_arg, read_text, write_report
from check_paper_section_whitelist import strip_comments


REQUIRED_TEMPLATE_MARKERS = [
    "\\documentclass[bwprint]{gmcmthesis}",
    "\\baominghao{",
    "\\schoolname{",
    "\\membera{",
    "\\begin{abstract}",
    "\\keywords{",
    "\\begin{thebibliography}",
    "\\begin{appendices}",
]

SYMBOL_TITLE_RE = re.compile(r"^\d\.\d\s*符号说明\s*$")
ASSUME_TITLE_RE = re.compile(r"^\d\.\d\s*模型假设\s*$")
PROBLEM1_RE = re.compile(r"^\d+\s*问题一模型建立与求解\s*$")
TOC_LEADER_RE = re.compile(r"[\.·．]{3,}")


def _block_texts(page: object) -> list[tuple[int, str]]:
    return [
        (round(block[1], 1), block[4].strip().replace("\n", ""))
        for block in page.get_text("blocks")
        if block[4].strip()
    ]


def _cjk(text: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fff]", text))


def _symbol_row_descriptions(tex_path: Path) -> list[str]:
    """只提取唯一符号表的中文释义；复杂宏/纯数学释义由视觉核对兜底。"""
    text = strip_comments(read_text(tex_path))
    anchor = re.search(r"\\subsection\s*\{符号说明\}", text)
    if anchor is None:
        return []
    block = re.split(r"\\(?:subsection|section)\*?\s*\{", text[anchor.end():], maxsplit=1)[0]
    tables = list(re.finditer(r"\\begin\{(tabularx|tabular|longtable)\}(.*?)\\end\{\1\}", block, re.S))
    if len(tables) != 1:
        return []
    rows = []
    for row in re.split(r"\\\\(?:\[[^\]]*\])?", tables[0].group(2)):
        cells = re.split(r"(?<!\\)&", row)
        if len(cells) < 2:
            continue
        # 首表头和 longtable 重复表头均不计为数据行。
        if "符号" in _cjk(cells[0]) and "意义" in _cjk("".join(cells[1:])):
            continue
        description = _cjk("".join(cells[1:]))
        if len(description) < 2:
            return []
        rows.append(description)
    return rows


def _source_dependencies(tex_path: Path) -> set[Path]:
    """静态依赖补足无recorder时的input检查；有fls时加入实际项目内编译输入。"""
    root = tex_path.parent.resolve()
    dependencies = {tex_path.resolve()}
    pending = [tex_path]
    while pending:
        path = pending.pop()
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        for raw in re.findall(r"\\(?:input|include)\s*\{([^{}]+)\}", text):
            child = root / raw
            if not child.suffix:
                child = child.with_suffix(".tex")
            child = child.resolve()
            if child.is_file() and child not in dependencies:
                dependencies.add(child)
                pending.append(child)
    fls = tex_path.with_suffix(".fls")
    if fls.exists():
        for line in fls.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("INPUT "):
                continue
            source = (root / line[6:].strip('"')).resolve()
            if source.is_relative_to(root.parent) and source.suffix.lower() in {".tex", ".cls", ".sty", ".bib", ".pdf", ".png", ".jpg", ".jpeg"} and source.is_file():
                dependencies.add(source)
    return dependencies


def check_symbol_position_pdf(project: Path, errors: list[str]) -> None:
    """对照源码全部符号释义检查落版；缺失或歧义必须显式转入视觉核对。"""
    tex_path = project / "论文" / "main.tex"
    pdf_path = tex_path.with_suffix(".pdf")
    if not pdf_path.exists():
        errors.append("符号说明 PDF 位置检查需要 论文/main.pdf：请先完成编译再运行 step4 门禁。")
        return
    newer = [p.name for p in _source_dependencies(tex_path) if p.stat().st_mtime_ns > pdf_path.stat().st_mtime_ns]
    if newer:
        errors.append("论文/main.pdf 早于编译输入（旧输出）：" + "、".join(sorted(newer)) + "；请重新编译后再跑本检查。")
        return
    descriptions = _symbol_row_descriptions(tex_path)
    if not descriptions:
        errors.append("需人工视觉核对：无法从源码唯一符号表提取全部数据行释义，不能证明 PDF 符号行完整。")
        return
    try:
        import fitz
        doc = fitz.open(pdf_path)
    except Exception as exc:
        errors.append(f"需人工视觉核对：main.pdf 文本无法提取（{exc}）。")
        return
    blocks = []
    glyphs = []
    try:
        for pno, page in enumerate(doc, 1):
            for y, text in _block_texts(page):
                if not TOC_LEADER_RE.search(text):
                    blocks.append((pno, y, re.sub(r"\s+", "", text)))
            # 用逐字坐标，避免整张表被合并为一个文本块时首末行y相同。
            lines = [line for block in page.get_text("rawdict")["blocks"] if block["type"] == 0 for line in block["lines"]]
            for line in sorted(lines, key=lambda line: (round(line["bbox"][1], 1), line["bbox"][0])):
                for span in line["spans"]:
                    for char in span["chars"]:
                        if _cjk(char["c"]):
                            glyphs.append((char["c"], (pno, round(char["bbox"][1], 1))))
    finally:
        doc.close()
    def anchor(pattern: str) -> tuple[int, float] | None:
        matches = [(p, y) for p, y, text in blocks if re.fullmatch(pattern, text)]
        return matches[0] if len(matches) == 1 else None
    assume = anchor(r"2\.1模型假设")
    title = anchor(r"2\.2符号说明")
    problem = anchor(r"3问题一模型建立与求解")
    headers = [(p, y) for p, y, text in blocks if text.startswith("符号") and "意义" in text]
    if not (assume and title and problem and headers):
        errors.append("需人工视觉核对：未能唯一提取 2.1模型假设、2.2符号说明、符号表头和3问题一标题。")
        return
    # 检索范围包括问题一之后，不能先截断再把漏排末行当作通过。
    text = "".join(char for char, _ in glyphs)
    row_positions = []
    for description, count in Counter(descriptions).items():
        hits = [m.start() for m in re.finditer(re.escape(description), text)]
        if len(hits) != count:
            errors.append(f"需人工视觉核对：源码符号释义“{description}”有{count}行，PDF命中{len(hits)}处；数据行缺失或定位有歧义，不能自动通过。")
            continue
        row_positions.extend((glyphs[i][1], glyphs[i + len(description) - 1][1]) for i in hits)
    if len(row_positions) != len(descriptions):
        return
    first = min(start for start, end in row_positions)
    last = max(end for start, end in row_positions)
    relevant_headers = [h for h in headers if assume < h <= first]
    if not relevant_headers:
        errors.append("PDF 阅读顺序错误：符号表首表头未出现在首数据行之前。")
        return
    header = min(relevant_headers)
    if not (assume < title < header < first <= last < problem):
        errors.append("PDF 阅读顺序错误：必须为模型假设→符号说明标题→首表头→全部数据行→问题一；存在倒置或跨入问题一的符号行。")
    if not (title[0] == header[0] == first[0]):
        errors.append("符号说明标题必须与符号表首表头、首数据行同页（长表后续页允许自然跨页）。")


def main() -> int:
    parser = project_arg("检查 main.tex 是否偏离华为杯内置模板。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    tex_path = project / "论文" / "main.tex"

    if not tex_path.exists():
        errors.append(f"缺少论文主文件: {tex_path}")
        return write_report(False, "check_template_adherence", errors, args.output)

    text = read_text(tex_path)
    if "\\maketitle" not in text:
        errors.append("华为杯封面必须由 GMCMthesis 模板的 `\\maketitle` 生成，不得删除或另造封面。")
    maketoc_match = re.search(r"(?m)^[ \t]*\\maketoc\b", text)
    if maketoc_match is None:
        errors.append("华为杯目录必须由 GMCMthesis 模板原生的 `\\maketoc` 生成（位于摘要之后），不得省略。")
    else:
        end_abstract = text.find("\\end{abstract}")
        if end_abstract != -1 and maketoc_match.start() < end_abstract:
            errors.append("`\\maketoc` 必须位于摘要之后（官方顺序：封面→摘要→目录→正文，与官方示例 example.tex 一致）。")
    if "\\tableofcontents" in text:
        errors.append("目录必须使用模板原生 `\\maketoc`，禁止直接调用 `\\tableofcontents` 或手写目录环境。")
    if "\\begin{abstract}" not in text or "\\end{abstract}" not in text:
        errors.append("华为杯模板必须使用 gmcmthesis 提供的 `abstract` 环境。")

    missing = [marker for marker in REQUIRED_TEMPLATE_MARKERS if marker not in text]
    if missing:
        errors.append(
            "缺少华为杯模板关键结构，疑似没有以 `assets/templates/main.tex` 为基座: "
            + "、".join(missing)
        )

    # M14：编译后符号说明位置检查（只针对华为杯模板论文，PDF 缺失/过期按失败处理）。
    if "\\documentclass[bwprint]{gmcmthesis}" in text or "\\documentclass{gmcmthesis}" in text:
        check_symbol_position_pdf(project, errors)

    return write_report(not errors, "check_template_adherence", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
