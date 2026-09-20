#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""华为杯专属：把共享发现脚本命中的同题优秀论文渲染为代表页 PNG，并生成逐页观察记录入口。

只消费 `_shared/scripts/discover_excellent_papers.py` 已按 SHA-256 校验过的 PDF 路径，
不重新扫描论文库：开关关闭时不扫描也不创建截图；无匹配样本时只记录真实回退原因。
开启时默认写权威报告 `检查结果/excellent_paper_visual_review.json`（--output 仅是相同内容的额外副本）；
重跑按样本身份（relativePath+sha256）保留已填写的视觉观察，不无提示覆盖用户记录。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "checks"))
from common import split_page_blocks, split_sample_blocks  # noqa: E402


DISCOVER = Path(__file__).resolve().parents[2] / "_shared" / "scripts" / "discover_excellent_papers.py"
SHOT_DIR = "截图"
RECORD_NAME = "优秀论文参考记录.md"
REPORT_REL = Path("检查结果") / "excellent_paper_visual_review.json"
DPI = 150
MAX_PAGES_PER_PAPER = 5
MIN_PAGES_PER_PAPER = 3
TARGET_PAPERS = 2

BUCKETS = (
    ("摘要", ("摘要", "关键词", "abstract"), 1),
    ("模型建立", ("模型建立", "模型假设", "符号说明", "模型构建"), 1),
    ("求解", ("求解", "算法", "计算结果", "数值结果"), 1),
    ("图表组织", ("图1", "图 1", "表1", "表 1", "如表", "如图"), 1),
    ("整体版式", ("模型评价", "总结", "参考文献", "灵敏度"), 1),
)
OBSERVATION_DIMENSIONS = ("版式留白与信息密度", "布局与图表组织", "文风与句式节奏")
UNREAD_LINE = "未读取，待完成视觉观察"


def strip_extension(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", name)


def run_discover(args: argparse.Namespace) -> dict:
    command = [
        sys.executable,
        str(DISCOVER),
        "--competition",
        args.competition,
        "--limit",
        str(args.limit),
    ]
    if args.problem:
        command.extend(["--problem", args.problem])
    if args.year is not None:
        command.extend(["--year", str(args.year)])
    if args.dsh_home:
        command.extend(["--dsh-home", args.dsh_home])
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        return json.loads(proc.stdout)
    except Exception:
        return {
            "status": "discover_failed",
            "count": 0,
            "files": [],
            "fallback_reason": f"共享发现脚本输出无法解析：{proc.stdout.strip()[:200]}",
        }


def score_pages(fitz_module, document) -> list[tuple[str, int]]:
    """按关键词为每页打分，返回 (桶名, 页码)。少于 3 页的源 PDF 只取真实存在页。"""
    text_cache: dict[int, str] = {}
    for index in range(min(document.page_count, 40)):
        text_cache[index] = document.load_page(index).get_text("text") or ""
    selected: list[tuple[str, int]] = []
    used: set[int] = set()
    for label, keywords, wanted in BUCKETS:
        scored = []
        for index, text in text_cache.items():
            if index in used:
                continue
            score = sum(text.count(keyword) for keyword in keywords)
            if index < 4 and label == "摘要":
                score += 5
            scored.append((score, index))
        scored.sort(key=lambda item: (-item[0], item[1]))
        picked = 0
        for score, index in scored:
            if picked >= wanted:
                break
            if label != "摘要" and score <= 0:
                break
            selected.append((label, index))
            used.add(index)
            picked += 1
    if len(selected) < MIN_PAGES_PER_PAPER:
        step = max(1, document.page_count // MIN_PAGES_PER_PAPER)
        for index in range(0, document.page_count, step):
            if len(selected) >= MIN_PAGES_PER_PAPER:
                break
            if index in used:
                continue
            selected.append(("均匀抽样", index))
            used.add(index)
    return sorted(selected, key=lambda item: item[1])[:MAX_PAGES_PER_PAPER]


def _page_is_filled(page_text: str) -> bool:
    return "待填写" not in page_text and UNREAD_LINE not in page_text


def _reusable_observations(record: str, entry: dict) -> dict[int, list[str]]:
    """从旧记录提取同一样本（relativePath+sha256 身份）已填写的逐页观察。"""
    if not record:
        return {}
    reused: dict[int, list[str]] = {}
    for block in split_sample_blocks(record).values():
        identity = re.search(r"relativePath=([^\s]+) sha256=([0-9a-f]{64})", block)
        if identity is not None:
            if identity.group(1) != entry.get("relativePath") or identity.group(2) != entry.get("sha256"):
                continue
        else:
            pdf_match = re.search(r"(?m)^- 样本 PDF：(.+?)（", block)
            if not pdf_match or pdf_match.group(1).strip() != entry.get("relativePath"):
                continue
        for page, page_text in split_page_blocks(block).items():
            if _page_is_filled(page_text):
                lines = [line for line in page_text.splitlines() if line.startswith("- ")]
                if lines:
                    reused[page] = lines
    return reused


def render_paper(fitz_module, entry: dict, shot_root: Path, folder: str, reused: dict[int, list[str]]) -> dict:
    pdf_path = Path(entry["path"])
    document = fitz_module.open(pdf_path)
    pages = score_pages(fitz_module, document)
    target = shot_root / folder
    target.mkdir(parents=True, exist_ok=True)
    shots: list[dict] = []
    failures: list[dict] = []
    for label, index in pages:
        name = f"p{index + 1:03d}_{strip_extension(label)}.png"
        relative = f"{SHOT_DIR}/{folder}/{name}"
        png_path = target / name
        reused_ok = False
        if png_path.is_file():
            try:
                fitz_module.Pixmap(str(png_path))
                reused_ok = True
            except Exception:
                reused_ok = False
        if not reused_ok:
            try:
                pixmap = document.load_page(index).get_pixmap(dpi=DPI)
                pixmap.save(png_path)
            except Exception as exc:
                failures.append({"paper": entry.get("relativePath"), "page": index + 1, "reason": str(exc)})
                shots.append({"label": label, "page": index + 1, "relative": relative, "render_failed": True, "render_reason": str(exc)})
                continue
        shots.append({"label": label, "page": index + 1, "relative": relative})
    page_count = document.page_count
    document.close()
    return {
        "competition": entry.get("competition"),
        "year": entry.get("year"),
        "problem": entry.get("problem"),
        "pdf": entry.get("relativePath") or str(pdf_path),
        "relativePath": entry.get("relativePath"),
        "sha256": entry.get("sha256"),
        "page_count": page_count,
        "folder": f"{SHOT_DIR}/{folder}",
        "shots": shots,
        "reused_pages": sorted(reused),
    }


def _observation_lines(page: int, shots_by_page: dict[int, dict], reused: dict[int, list[str]]) -> list[str]:
    shot = shots_by_page.get(page) or {}
    if reused.get(page):
        return list(reused[page])
    if shot.get("render_failed"):
        lines = [f"- 视觉读取：渲染失败（{shot.get('render_reason', '原因未记录')}），{UNREAD_LINE}"]
    else:
        lines = [f"- 视觉读取：{UNREAD_LINE} `{shot.get('relative', '')}`"]
    lines.extend(f"- {dimension}：待填写" for dimension in OBSERVATION_DIMENSIONS)
    lines.append("- 明确禁止复制的内容：待填写")
    return lines


def record_markdown(papers: list[dict], status: str, fallback_reason: str | None, problem_match: bool, previous: str) -> str:
    lines = [
        "# 优秀论文参考记录（华为杯视觉校准）",
        "",
        f"- 共享发现状态：{status}",
        f"- 回退原因：{fallback_reason or '无'}",
        f"- 同题匹配：{'是' if problem_match else '否——未能完成同题参考，仅同赛事参考'}",
        "- 硬边界：本目录只作为项目内审计证据，绝不插入最终论文，也不进入参考文献；",
        "  禁止复制样本原文、近似改写、公式、变量、数据、图表、数值结论与装饰性符号（`·`、`•`、`☐`）。",
        "",
    ]
    if status != "matched":
        lines.extend(["本次运行未进入逐页渲染；以下为历史样本记录，均不参与本次统计。", ""])
    matched_identities = set()
    for paper in papers:
        matched_identities.add((paper.get("relativePath"), paper.get("sha256")))
        lines.extend(
            [
                f"## 样本 {paper['folder']}",
                "",
                f"- 赛事：{paper['competition']}　年份：{paper['year']}　题号：{paper['problem']}",
                f"- 样本 PDF：{paper['pdf']}（共 {paper['page_count']} 页，仅渲染代表页）",
                f"- 样本身份：relativePath={paper.get('relativePath')} sha256={paper.get('sha256')}",
                "",
                "### 逐页视觉读取记录",
                "",
            ]
        )
        shots_by_page = {shot["page"]: shot for shot in paper["shots"]}
        reused = paper.get("_reused") or {}
        for shot in paper["shots"]:
            page = shot["page"]
            lines.extend(
                [
                    f"#### p{page:03d}（{shot['label']}）`{shot['relative']}`",
                    "",
                ]
            )
            lines.extend(_observation_lines(page, shots_by_page, reused))
            lines.append("")
    # 保留旧样本记录：本次未选中的历史样本标注为不参与统计，不无提示覆盖。
    # 身份匹配必须是 relativePath+sha256 双匹配：路径相同但内容变化（sha 不同）的旧块仍要归档保留。
    for name, block in split_sample_blocks(previous or "").items():
        base_name = name.replace("（旧样本，不参与本次统计）", "").strip()
        entry_identity = re.search(r"relativePath=([^\s]+) sha256=([0-9a-f]{64})", block)
        pdf_prefix = re.search(r"(?m)^- 样本 PDF：(.+?)（", block)
        identity = (entry_identity.group(1), entry_identity.group(2)) if entry_identity else (pdf_prefix.group(1).strip() if pdf_prefix else None, None)
        if identity[0] and any(identity[0] == relative and identity[1] == digest for relative, digest in matched_identities):
            continue
        if identity[0] is None and identity[1] is None and base_name in {paper["folder"] for paper in papers}:
            continue
        renamed = block.replace(f"## 样本 {name}", f"## 样本 {base_name}（旧样本，不参与本次统计）", 1)
        lines.extend([renamed.rstrip(), ""])
    lines.extend(
        [
            "## 进入 Step4/Step5 前必须完成",
            "",
            "- 逐个读取上面列出的 PNG，再回填每一页的观察结论；没有视觉读取记录时不得声称“已参考优秀论文”。",
            "- 只校准页面留白与信息密度、标题层级与段落节奏、单图/多图使用频率、图表与解释的相对位置、图表尺寸占比、摘要与问题段落的信息组织、文风的克制程度。",
            "- 重跑本脚本会保留已填写的观察；样本内容变化（sha256 不同）时旧观察不会复用。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="华为杯优秀论文视觉校准：渲染代表页并生成观察记录")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--competition", default="华为杯")
    parser.add_argument("--problem")
    parser.add_argument("--year", type=int)
    parser.add_argument("--limit", type=int, default=TARGET_PAPERS)
    parser.add_argument("--dsh-home")
    parser.add_argument("--disabled", action="store_true", help="卡片开关关闭：不扫描论文库，不创建截图")
    parser.add_argument("--output", help="可选 JSON 报告输出路径（额外副本；权威报告固定写 检查结果/）")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not project.is_dir():
        print(json.dumps({"ok": False, "errors": [f"项目根目录不存在: {project}"]}, ensure_ascii=False, indent=2))
        return 2

    if args.disabled:
        report = {"ok": True, "status": "disabled", "shots": 0, "papers": 0}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    discovery = run_discover(args)
    status = str(discovery.get("status") or "unknown")
    fallback_reason = discovery.get("fallback_reason")
    problem_match = bool(discovery.get("problem_match"))
    if status != "matched":
        report = {
            "ok": True,
            "status": status,
            "fallback_reason": fallback_reason,
            "problem_match": problem_match,
            "papers": 0,
            "shots": 0,
            "note": "未命中同题样本，只记录真实回退原因，不伪造截图。",
        }
        (project / REPORT_REL).parent.mkdir(parents=True, exist_ok=True)
        (project / REPORT_REL).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        record_path = project / SHOT_DIR / RECORD_NAME
        previous = record_path.read_text(encoding="utf-8") if record_path.exists() else ""
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(record_markdown([], status, fallback_reason, problem_match, previous), encoding="utf-8")
        if args.output:
            Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    try:
        import fitz
    except ImportError:
        report = {"ok": False, "status": "pymupdf_missing", "errors": ["缺少 PyMuPDF(fitz)，无法渲染代表页截图。"]}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    shot_root = project / SHOT_DIR
    shot_root.mkdir(parents=True, exist_ok=True)
    record_path = shot_root / RECORD_NAME
    previous = record_path.read_text(encoding="utf-8") if record_path.exists() else ""
    papers: list[dict] = []
    render_failures: list[dict] = []
    for index, entry in enumerate(discovery.get("files") or [], 1):
        reused = _reusable_observations(previous, entry)
        paper = render_paper(fitz, entry, shot_root, f"优秀论文{index}", reused)
        paper["_reused"] = reused
        papers.append(paper)
    # 收集渲染失败明细
    for paper in papers:
        for shot in paper["shots"]:
            if shot.get("render_failed"):
                render_failures.append({"paper": paper.get("relativePath"), "page": shot["page"], "reason": shot.get("render_reason", "")})
    record = record_markdown(papers, status, fallback_reason, problem_match, previous)
    record_path.write_text(record, encoding="utf-8")
    report = {
        "ok": not render_failures,
        "status": status,
        "problem_match": problem_match,
        "papers": len(papers),
        "shots": sum(len(paper["shots"]) for paper in papers),
        "record": f"{SHOT_DIR}/{RECORD_NAME}",
        "selected_papers": [
            {
                "relativePath": paper.get("relativePath"),
                "sha256": paper.get("sha256"),
                "folder": paper["folder"],
                "page_count": paper["page_count"],
                "shots": [
                    {"page": shot["page"], "label": shot["label"], "relative": shot["relative"]}
                    for shot in paper["shots"]
                    if not shot.get("render_failed")
                ],
            }
            for paper in papers
        ],
        "render_failures": render_failures,
        "details": [{k: v for k, v in paper.items() if k != "_reused"} for paper in papers],
    }
    (project / REPORT_REL).parent.mkdir(parents=True, exist_ok=True)
    (project / REPORT_REL).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not render_failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
