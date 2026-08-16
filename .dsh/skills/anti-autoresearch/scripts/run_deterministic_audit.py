#!/usr/bin/env python3
"""Run Anti-Autoresearch's deterministic audit spine from one DSH skill."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True)


def resolve_input(raw: str) -> tuple[Path, list[Path], list[Path]]:
    source = Path(raw).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"输入不存在：{source}")

    paper_dir = source if source.is_dir() else source.parent
    tex_files: list[Path] = []
    text_files: list[Path] = []

    if source.is_file() and source.suffix.lower() == ".tex":
        tex_files = [source]
    elif source.is_file() and source.suffix.lower() in {".txt", ".md"}:
        text_files = [source]
    else:
        tex_files = sorted(paper_dir.rglob("*.tex"))
        text_files = sorted(paper_dir.rglob("*.txt"))

    pdf = source if source.is_file() and source.suffix.lower() == ".pdf" else None
    if not tex_files and not text_files:
        if pdf is None:
            candidates = sorted(paper_dir.glob("*.pdf"))
            pdf = candidates[0] if candidates else None
        if pdf is None:
            raise SystemExit("没有找到可审计的 .tex、.txt 或 .pdf 文件。")
        extractor = shutil.which("pdftotext")
        if not extractor:
            raise SystemExit("检测到 PDF，但系统没有 pdftotext；请先安装 Poppler 或提供提取后的文本。")
        extracted = paper_dir / "paper.txt"
        subprocess.run([extractor, "-layout", str(pdf), str(extracted)], check=True)
        text_files = [extracted]

    return paper_dir, tex_files, text_files


def main() -> int:
    parser = argparse.ArgumentParser(description="运行论文诚信确定性审计骨架。")
    parser.add_argument("input", help="论文目录、PDF、LaTeX 或文本路径")
    parser.add_argument("--paper-id", help="报告中的论文标识；默认使用目录或文件名")
    args = parser.parse_args()

    paper_dir, tex_files, text_files = resolve_input(args.input)
    paper_id = args.paper_id or Path(args.input).resolve().stem
    manifest = paper_dir / "artifact_manifest.json"
    ledger = paper_dir / "claims.json"

    manifest_args = [
        str(HERE / "build_manifest.py"), "--paper-id", paper_id,
        "--dir", str(paper_dir), "--out", str(manifest),
    ]
    if text_files:
        manifest_args.extend(["--pdf-text", str(text_files[0])])
    run(*manifest_args)

    with manifest.open(encoding="utf-8") as handle:
        level = int(json.load(handle)["observability_level"])

    ledger_args = [
        str(HERE / "build_claim_ledger.py"), "--paper-id", paper_id,
        "--observability-level", str(level), "--out", str(ledger),
    ]
    if tex_files:
        ledger_args.extend(["--latex", *map(str, tex_files)])
    else:
        ledger_args.extend(["--pdf-text", *map(str, text_files)])
    run(*ledger_args)

    checks = [
        ("check_numeric_consistency.py", "consistency-audit.deterministic.findings.json"),
        ("check_presentation.py", "presentation-signals.deterministic.findings.json"),
        ("check_stat_consistency.py", "stat-consistency.deterministic.findings.json"),
        ("check_ai_style.py", "ai-style-impressions.deterministic.findings.json"),
    ]
    findings: list[Path] = []
    for script, filename in checks:
        output = paper_dir / filename
        run(str(HERE / script), "--ledger", str(ledger), "--out", str(output))
        findings.append(output)

    run(
        str(HERE / "adjudicate_findings.py"),
        "--findings", *map(str, findings),
        "--ledger", str(ledger),
        "--paper-id", paper_id,
        "--observability-level", str(level),
        "--limitation", "当前报告仅包含确定性检查；语义审计维度需由 DSH 按参考检查表继续执行。",
        "--out", str(paper_dir / "report.json"),
        "--md", str(paper_dir / "REPORT.md"),
    )
    print(f"完成：L{level}，报告位于 {paper_dir / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

