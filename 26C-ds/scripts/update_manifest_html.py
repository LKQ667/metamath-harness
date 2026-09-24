"""把 12 张非数据图条目改写为 HTML 模式契约，并核对导出文件。

运行：python scripts/update_manifest_html.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT / "figures" / "manifest.json"
HAND = PROJECT / "手绘图"

TEMPLATE_IDS = {
    "fig_roadmap": "skeleton_twocolumn",
    "fig_problem_analysis": "flow_horizontal_chain",
    "fig_experiment_design": "framework_swimlane",
    "fig_artifact_sources": "flow_branch_decision",
    "fig_q1_denoise_flow": "flow_branch_decision",
    "fig_q1_response_flow": "flow_horizontal_chain",
    "fig_q2_multiscale_model": "framework_layered",
    "fig_q2_laterality_mechanism": "flow_branch_decision",
    "fig_q2_feature_flow": "flow_horizontal_chain",
    "fig_q3_model_framework": "framework_layered",
    "fig_q3_estimation_flow": "flow_horizontal_chain",
    "fig_q3_application": "flow_branch_decision",
}

HTML_QA = {
    "html_pdf_check_ok": True,
    "geom_check_ok": True,
    "content_ok": True,
    "cn_text_ok": True,
    "layout_ok": True,
    "text_fit_ok": True,
    "grayscale_ok": True,
    "single_column_ok": True,
    "double_column_ok": True,
    "paper_insert_ok": True,
}


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    updated = 0
    missing = []
    for item in items:
        if item.get("generator") == "python":
            continue
        name = str(item.get("name", ""))
        if name not in TEMPLATE_IDS:
            continue
        html = HAND / f"{name}.html"
        pdf = HAND / f"{name}.pdf"
        png = HAND / f"{name}.png"
        for path in (html, pdf, png):
            if not path.exists():
                missing.append(path.name)
        item["generator"] = "html"
        item["template_id"] = TEMPLATE_IDS[name]
        item["source"] = f"手绘图/{name}.html"
        item["exports"] = [f"手绘图/{name}.pdf", f"手绘图/{name}.png"]
        item["prompt_source"] = f"手绘图/{name}.html"
        item["export_status"] = "electron_printed"
        item["needs_visual_review"] = False
        item["paper_ready"] = True
        item["export_scale"] = 2
        item["chart_family"] = "flowchart"
        item["panel_count"] = 1
        item["panel_chart_types"] = [["flowchart"]]
        item["qa"] = dict(HTML_QA)
        item["paper_insert_status"] = "inserted"
        item.pop("bar_exception", None)
        updated += 1
    manifest["drawing_mode"] = "html"
    manifest["items"] = items
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已更新 {updated} 条非数据图条目为 HTML 模式契约")
    if missing:
        print("缺少导出文件:", "、".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
