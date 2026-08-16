#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run all yatai-cn deliverable checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


CHECKS = [
    "check_result_ranges.py",
    "check_result_consistency.py",
    "check_code_distribution.py",
    "check_data_sources.py",
    "check_abstract_no_formula.py",
    "check_abstract_one_page.py",
    "check_paper_emphasis.py",
    "check_latex_log.py",
    "check_figures_manifest.py",
    "check_drawing_contract.py",
    "check_python_figure_contract.py",
    "check_python_figure_quality.py",
    "check_python_bar_chart_policy.py",
    "check_python_3d_recommendation.py",
    "check_flowchart_required.py",
    "check_flowchart_visual_quality.py",
    "check_roadmap_in_paper.py",
    "check_roadmap_quality_notes.py",
    "check_question_assets.py",
    "check_template_adherence.py",
    "check_paper_layout_whitespace.py",
    "check_pdf_page_blank_ratio.py",
    "check_paper_internal_paths.py",
    "check_paper_body_forbidden_symbols.py",
    "check_paper_prose_style.py",
    "check_support_material_catalog.py",
    "check_required_result_artifact_allowlist.py",
    "check_appendix_code_cleanliness.py",
    "check_appendix_code_scope.py",
    "check_handdraw_readme.py",
    "check_ai_prompt_paths.py",
    "check_ai_prompt_quality.py",
    "check_ai_prompt_alignment.py",
    "check_ai_prompt_layout.py",
    "check_main_tex_compile_record.py",
    "check_reasoning_depth_review.py",
    "check_page_count_deepening_policy.py",
    "check_body_page_count_minimum.py",
    "check_three_round_self_review.py",
    "check_no_absolute_paths.py",
    "check_no_env_or_cache.py",
    "check_readme_agent_status.py",
    "check_bibliography_sources.py",
    "check_deliverable_scorecard.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all yatai-cn checks.")
    parser.add_argument("--project", required=True, help="数学建模项目根目录")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    report_dir = project / "检查结果"
    report_dir.mkdir(parents=True, exist_ok=True)
    base = Path(__file__).resolve().parent
    results = []
    ok_all = True
    for check in CHECKS:
        output = report_dir / f"{Path(check).stem}.json"
        cmd = [sys.executable, str(base / check), "--project", str(project), "--output", str(output)]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        ok = proc.returncode == 0
        ok_all = ok_all and ok
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
        except Exception:
            data = {"check": Path(check).stem, "ok": ok, "errors": [proc.stderr.strip() or proc.stdout.strip()]}
        results.append(data)
    summary = {"ok": ok_all, "checks": results}
    (report_dir / "check_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# yatai-cn 检查报告", "", f"总体状态：{'通过' if ok_all else '失败'}", ""]
    for item in results:
        md.append(f"## {item.get('check')}")
        md.append(f"- 状态：{'通过' if item.get('ok') else '失败'}")
        for error in item.get("errors", []):
            md.append(f"- {error}")
        md.append("")
    (report_dir / "check_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
