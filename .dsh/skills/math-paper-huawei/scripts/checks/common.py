#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""华为杯论文交付门禁的共享辅助函数。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


BODY_START_MARKER = "\\label{body:start}"
BODY_END_MARKER = "\\label{body:end}"
APPENDIX_START_MARKER = "\\label{appendix:start}"

SUBPOLICY_DEFAULT = "默认（模型自行判断）"
SUBPOLICY_SPARSE = "少用子图"
SUBPOLICY_DISABLED = "禁用子图"
SUBPOLICY_ALIASES = {
    "默认": SUBPOLICY_DEFAULT,
    "默认（模型自行判断）": SUBPOLICY_DEFAULT,
    "默认(模型自行判断)": SUBPOLICY_DEFAULT,
    "少用子图": SUBPOLICY_SPARSE,
    "少用": SUBPOLICY_SPARSE,
    "禁用子图": SUBPOLICY_DISABLED,
    "禁用": SUBPOLICY_DISABLED,
}
SUBPOLICY_SPARSE_MAX_MULTI_PANEL = 4


def normalize_subplot_policy(value: object) -> str:
    text = str(value or "").strip()
    return SUBPOLICY_ALIASES.get(text, SUBPOLICY_DEFAULT)


def project_arg(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--project", required=True, help="数学建模项目根目录")
    parser.add_argument("--output", help="可选 JSON 报告输出路径")
    return parser


def read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() != ".tex":
        return text
    root = path.parent.resolve()
    return _expand_tex_inputs(text, current_dir=path.parent, root=root, seen={path.resolve()})


def _expand_tex_inputs(text: str, *, current_dir: Path, root: Path, seen: set[Path]) -> str:
    """只在当前 TeX 根内递归展开 input/include，供内容门禁读取完整论文。"""
    pattern = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")

    def replace(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        candidate = current_dir / raw
        if candidate.suffix.lower() != ".tex":
            candidate = candidate.with_suffix(".tex")
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            return match.group(0)
        if resolved in seen or not resolved.is_file() or resolved.is_symlink():
            return match.group(0)
        nested = resolved.read_text(encoding="utf-8", errors="replace")
        return _expand_tex_inputs(
            nested,
            current_dir=resolved.parent,
            root=root,
            seen={*seen, resolved},
        )

    return pattern.sub(replace, text)


def aux_label_page(aux_text: str, label: str) -> int | None:
    patterns = [
        rf"\\newlabel\{{{re.escape(label)}\}}\{{\{{[^{{}}]*\}}\{{(\d+)\}}",
        rf"\\newlabel\{{{re.escape(label)}\}}.*?\{{(\d+)\}}",
    ]
    for pattern in patterns:
        match = re.search(pattern, aux_text)
        if match:
            return int(match.group(1))
    return None


def paper_body_region(text: str) -> tuple[str, list[str]]:
    errors: list[str] = []
    markers = (
        ("body:start", BODY_START_MARKER),
        ("body:end", BODY_END_MARKER),
        ("appendix:start", APPENDIX_START_MARKER),
    )
    positions: dict[str, int] = {}
    for label, marker in markers:
        count = text.count(marker)
        if count != 1:
            errors.append(f"论文主文件必须且只能包含 1 个 `{marker}`，当前为 {count} 个。")
            continue
        positions[label] = text.find(marker)
    if errors:
        return "", errors

    start = positions["body:start"]
    end = positions["body:end"]
    appendix = positions["appendix:start"]
    document = text.find("\\begin{document}")
    huawei = "\\documentclass[bwprint]{gmcmthesis}" in text or "\\documentclass{gmcmthesis}" in text
    title = text.find("\\title{") if huawei else text.find("{\\titlefont", start)
    abstract = text.find("\\begin{abstract}", start) if huawei else text.find("{\\sectiontitlefont 摘要}", start)
    bibliography = text.find("\\begin{thebibliography}", start)
    bibliography_end = text.find("\\end{thebibliography}", bibliography)
    appendices = text.find("\\begin{appendices}", appendix)
    catalog = text.find("支撑材料文件目录", appendix)
    appendix_code = text.find("\\section{附录代码文件}", appendix)

    if document == -1 or not (document < start):
        errors.append("`body:start` 必须位于 `\\begin{document}` 之后。")
    if title == -1 or (not huawei and not (start < title < end)):
        errors.append("论文标题信息必须由当前模板定义，并位于合法正文结构中。")
    if abstract == -1 or not (start < abstract < end):
        errors.append("摘要必须位于 `body:start` 与 `body:end` 之间。")
    if bibliography == -1 or bibliography_end == -1 or not (start < bibliography < bibliography_end < end):
        errors.append("完整参考文献必须位于正文边界内，并在 `body:end` 之前结束。")
    if not (start < end < appendix):
        errors.append("正文与附录边界顺序必须为 `body:start`、`body:end`、`appendix:start`。")
    if appendices == -1 or not (appendix < appendices):
        errors.append("`appendix:start` 必须位于 `\\begin{appendices}` 之前。")
    if catalog == -1 or not (appendix < catalog):
        errors.append("支撑材料文件目录必须位于 `appendix:start` 之后。")
    if appendix_code == -1 or not (appendix < appendix_code):
        errors.append("附录代码必须位于 `appendix:start` 之后。")
    between = text[end + len(BODY_END_MARKER):appendix]
    if not re.search(r"\\(?:newpage|clearpage)\b", between):
        errors.append("`body:end` 与 `appendix:start` 之间必须使用 `\\newpage` 或 `\\clearpage` 使附录另起一页。")
    if errors:
        return "", errors
    return text[start:end + len(BODY_END_MARKER)], []


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report(
    ok: bool,
    check: str,
    errors: list[str],
    output: str | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    report = {"check": check, "ok": ok, "errors": errors}
    report["issues"] = [
        {
            "error_code": f"{check.upper()}_{index:03d}",
            "message": error,
            "repair_hint": repair_hint(error),
        }
        for index, error in enumerate(errors, 1)
    ]
    if details is not None:
        report["details"] = details
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if ok else 1


def repair_hint(error: str) -> str:
    if "LaTeX" in error or "编译" in error or ".log" in error or ".aux" in error:
        return "运行 LaTeX doctor/compile，按日志补齐宏包、字体或引用后重跑。"
    if "缺少" in error or "不存在" in error:
        return "创建或恢复所列必需产物，并依据当前阶段契约补齐真实内容。"
    if "解析失败" in error or "格式" in error:
        return "修正文件编码、语法或结构，使其符合对应 JSON/Markdown/LaTeX 契约。"
    if "不一致" in error or "冲突" in error:
        return "回到唯一结果源或锁定配置统一相关产物，禁止复制另一套数值。"
    return "根据错误定位对应产物，做最小修复后重跑当前阶段门禁。"


def final_results_path(project: Path) -> Path:
    return project / "results" / "final_results.json"


def manifest_path(project: Path) -> Path:
    return project / "figures" / "manifest.json"


def numeric_values(obj: Any, prefix: str = "") -> dict[str, float]:
    values: dict[str, float] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            values.update(numeric_values(value, child))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            child = f"{prefix}[{index}]"
            values.update(numeric_values(value, child))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        values[prefix] = float(obj)
    return values


def find_numbers(text: str) -> list[float]:
    pattern = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?")
    return [float(m.group(0)) for m in pattern.finditer(text)]


def iter_project_files(project: Path, suffixes: tuple[str, ...]) -> list[Path]:
    ignored = {".venv", "__pycache__", ".git", "node_modules", "检查结果"}
    files: list[Path] = []
    for path in project.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            files.append(path)
    return files


def normalize_project_path(project: Path, value: object) -> Path | None:
    """把清单内相对路径按实际文件身份归一（分隔符/./..），拒绝绝对路径与项目外目标。"""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("\\", "/")
    if Path(text).is_absolute() or re.match(r"^[A-Za-z]:", text):
        return None
    try:
        resolved = (project / text).resolve()
        resolved.relative_to(project.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def item_export_paths(project: Path, item: dict) -> list[Path]:
    """图项 exports（dict 或 list 形态）归一为绝对路径列表，非法项记为 None 占位。"""
    raw = item.get("exports") or []
    values = list(raw.values()) if isinstance(raw, dict) else raw
    return [normalize_project_path(project, value) for value in values]


GRAPHICEXT_ORDER = (".pdf", ".PDF", ".ai", ".AI", ".png", ".PNG", ".jpg", ".JPG",
                    ".jpeg", ".JPEG", ".jp2", ".JP2", ".jpf", ".JPF", ".bmp", ".BMP",
                    ".ps", ".PS", ".eps", ".EPS", ".mps", ".MPS")
INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics\s*\*?\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}")
GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\{[^{}]*\})+)\}")


def resolve_figure_references(project: Path) -> dict:
    """解析论文 main.tex 的 \\includegraphics 引用，供 step4/5 核对最终入文集合。

    M10：与实际 TeX 编译语义一致——compile_tex() 以 论文/ 为 cwd，TeX 先按
    当前目录（论文/），再按 \\graphicspath 声明顺序查目录；不猜测项目根。
    省略扩展名时按 XeLaTeX 默认扩展名顺序逐项查所有目录。
    支持 input/include 展开；省略扩展名按 GRAPHICEXT_ORDER 尝试。
    含宏构造/嵌套花括号等无法解析的 token 记为 unresolved，不当成"没有引用"；
    解析后越出项目范围（含 `..`/Junction 展开）的引用同样记为 unresolved。
    """
    main_tex = project / "论文" / "main.tex"
    if not main_tex.exists():
        return {"tex_missing": True, "resolved": [], "tokens": [], "unresolved": []}
    text = "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in read_text(main_tex).splitlines())
    main_dir = project / "论文"
    bases: list[Path] = [main_dir]
    for match in GRAPHICSPATH_RE.finditer(text):
        for inner in re.finditer(r"\{([^{}]*)\}", match.group(1)):
            directory = inner.group(1).strip().replace("\\", "/")
            if not directory:
                continue
            candidate = main_dir / directory
            if candidate not in bases:
                bases.append(candidate)
    resolved: list[Path] = []
    tokens: list[str] = []
    unresolved: list[str] = []
    seen: set[Path] = set()
    for match in INCLUDEGRAPHICS_RE.finditer(text):
        token = match.group(1).strip().replace("\\", "/")
        tokens.append(token)
        if "\\" in match.group(1):
            unresolved.append(
                f"\\includegraphics 参数含宏（{token}），无法静态解析，需人工核对该引用的实际图文件"
            )
            continue
        candidate_bases: list[Path] = []
        for raw_base in bases:
            candidate_bases.append(raw_base / token if not Path(token).is_absolute() else Path(token))
        found: Path | None = None
        # graphicx 先枚举扩展名，再对该文件名按当前目录/graphicspath 查找。
        candidates = candidate_bases if Path(token).suffix else [
            base.with_suffix(ext) for ext in GRAPHICEXT_ORDER for base in candidate_bases
        ]
        for candidate in candidates:
            if candidate.is_file():
                found = candidate
                break
        if found is None:
            unresolved.append(token)
            continue
        normalized = found.resolve()
        try:
            normalized.relative_to(project.resolve())
        except ValueError:
            unresolved.append(token)
            continue
        if normalized not in seen:
            seen.add(normalized)
            resolved.append(normalized)
    # 宏构造/嵌套花括号的 \includegraphics 不被严格正则匹配：显式标记未解析，
    # 不得静默漏掉后宣称所有入文图已纳入（M10 步骤 4）。
    loose_count = len(re.findall(r"\\includegraphics\s*\*?\s*(?:\[[^\]]*\]\s*)?\{", text))
    if loose_count > len(tokens):
        unresolved.append(
            f"\\includegraphics 存在 {loose_count - len(tokens)} 处宏构造/嵌套花括号参数，"
            "超出当前解析能力，需人工核对这些引用的实际图文件"
        )
    return {"tex_missing": False, "resolved": resolved, "tokens": tokens, "unresolved": unresolved}


def load_manifest_items(project: Path) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    path = manifest_path(project)
    if not path.exists():
        return [], [f"缺少图片清单: {path}"]
    try:
        data = load_json(path)
    except Exception as exc:
        return [], [f"图片清单 JSON 解析失败: {exc}"]
    items = data.get("items", data.get("figures")) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return [], ["图片清单必须是列表或包含 items/figures 列表的对象"]
    normalized: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            errors.append(f"图片清单条目不是对象: {item!r}")
    return normalized, errors


# ---------------------------------------------------------------------------
# 优秀论文参考记录（Markdown）解析：渲染器写、检查器读，共用同一契约。
# ---------------------------------------------------------------------------

SAMPLE_BLOCK_RE = re.compile(r"(?m)^## (.+?)\s*$")
PAGE_BLOCK_RE = re.compile(r"(?m)^#### p(\d{3})")


def split_sample_blocks(text: str) -> dict[str, str]:
    """按 `## 样本 <名称>` 切分记录；样本块止于下一个同级 `## ` 标题。"""
    headings = list(SAMPLE_BLOCK_RE.finditer(text))
    blocks: dict[str, str] = {}
    for index, match in enumerate(headings):
        title = match.group(1).strip()
        if not title.startswith("样本"):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        blocks[title[len("样本"):].strip()] = text[match.start():end]
    return blocks


def split_page_blocks(sample_block: str) -> dict[int, str]:
    """按 `#### pNNN` 切分单个样本块内的逐页记录。"""
    headings = list(PAGE_BLOCK_RE.finditer(sample_block))
    pages: dict[int, str] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(sample_block)
        pages[int(match.group(1))] = sample_block[match.start():end]
    return pages


def observation_problems(page_block: str, dimensions: tuple[str, ...]) -> list[str]:
    """逐页观察实质内容核对：只写维度关键词或占位不算完成视觉阅读。"""
    problems: list[str] = []
    for dimension in dimensions:
        match = re.search(rf"(?m)^- {re.escape(dimension)}[：:](.*)$", page_block)
        if not match:
            problems.append(f"缺少维度“{dimension}”的观察记录")
            continue
        value = match.group(1).replace("待填写", "").strip()
        if len(re.sub(r"[\s,，。;；、/|()（）\"“”']", "", value)) < 12:
            problems.append(f"维度“{dimension}”只有泛泛表述，缺少具体观察内容（标题密度/空白与图表占比/解释位置/文句组织等）")
    return problems
