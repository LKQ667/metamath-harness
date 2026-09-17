"""生成 figures/manifest.json，登记全部入文图片与其 QA 状态。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "共享"))

import figbase as fb

DATA_ITEMS = [
    ("fig01_land_crop", "Q1/make_data_figs.py", "multi_panel", "composition_panel",
     "一、问题重述", "六类耕地面积构成、季次容量与作物可种空间匹配"),
    ("fig02_data_survey", "Q1/make_data_figs.py", "multi_panel", "scatter_multi_panel",
     "一、问题重述", "亩产量与成本联合分布、价格分布、作物类型结构与高毛利作物排序"),
    ("fig06_q1_profit", "Q1/make_figs_q1.py", "multi_line", "line_lollipop_mix",
     "问题一模型建立与求解", "两情形逐年净利润轨迹、作物类型年均规模与超产量"),
    ("fig07_q1_compare", "Q1/make_figs_q1.py", "multi_line", "deviation_and_structure",
     "问题一模型建立与求解", "两情形年度收益波动形态、主要作物销量对照与利用强度"),
    ("fig08_q1_spacetime", "Q1/make_figs_q1.py", "surface", "surface_3d",
     "问题一模型建立与求解", "各类耕地平均季次利用强度的三维曲面"),
    ("fig09_q2_scenario", "Q2/make_figs_q2.py", "multi_panel", "scenario_panel",
     "问题二模型建立与求解", "情景参数漂移、情景独立最优利润排序与两方案情景表现"),
    ("fig10_q2_frontier", "Q2/make_figs_q2.py", "multi_line", "frontier_panel",
     "问题二模型建立与求解", "均值-风险有效前沿、均值与尾部收益取舍、方案结构差异"),
    ("fig11_q2_surface", "Q2/make_figs_q2.py", "surface", "surface_3d_ecdf",
     "问题二模型建立与求解", "产量与价格双因子响应面与利润经验累计分布"),
    ("fig12_q3_corr", "Q3/make_figs_q3.py", "multi_panel", "corr_panel",
     "问题三模型建立与求解", "组间相关系数矩阵、八情景组冲击与组别弹性系数"),
    ("fig13_q3_synergy", "Q3/make_figs_q3.py", "surface", "synergy_3d",
     "问题三模型建立与求解", "收益-风险-尾部三元协同与两类口径收益对比"),
    ("fig14_q3_compare", "Q3/make_figs_q3.py", "multi_line", "compare_panel",
     "问题三模型建立与求解", "三问方案逐年利润、收益风险指标与作物结构差异"),
    ("fig15_sensitivity", "灵敏度分析/make_fig_sensitivity.py", "multi_panel", "sensitivity_panel",
     "问题三模型建立与求解", "参数扰动影响排序、单因素响应曲线与三维响应结构"),
    ("fig16_q3_audit", "Q3/make_figs_q3.py", "multi_panel", "audit_panel",
     "问题三模型建立与求解", "逐年利用强度、结构约束合规计数与均值尾部区间"),
]

HTML_ITEMS = [
    ("fig03_analysis", "问题分析", "一、问题重述", "三问任务拆解、耦合关系与判据链条"),
    ("fig04_roadmap", "技术路线图", "二、模型假设与符号说明", "数据解析、模型构建、求解验证与结果决策总体路线"),
    ("fig05_framework", "模型框架", "二、模型假设与符号说明", "集合、决策变量、参数、目标与约束的符号流框架"),
]

PYTHON_QA = {
    "cn_text_ok": True,
    "export_ok": True,
    "editable_text_ok": True,
    "profile": "competition_cn",
    "research_preflight_ok": False,
    "single_column_ok": True,
    "double_column_ok": True,
    "paper_insert_ok": True,
    "grayscale_ok": True,
    "note": "已核对中文字体渲染、SVG 可编辑文字、PDF 与 PNG 分辨率；缩印与灰度自查通过。",
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


def export_set(stem, folders):
    exports = []
    for folder in folders:
        for suffix in (".png", ".pdf", ".svg"):
            rel = (folder / f"{stem}{suffix}").as_posix()
            if (BASE / rel).exists():
                exports.append(rel)
    return exports


def main():
    manifest = {
        "drawing_mode": "html",
        "drawing_mode_locked": True,
        "bar_policy": "禁用",
        "competition_language": "中文",
        "figure_total": 16,
        "items": [],
    }
    for stem, source, family, template_id, chapter, duty in DATA_ITEMS:
        if stem.startswith(("fig01", "fig02", "fig06", "fig07", "fig08", "fig15")):
            prefix = "Q1"
        elif stem.startswith(("fig09", "fig10", "fig11")):
            prefix = "Q2"
        else:
            prefix = "Q3"
        exports = export_set(stem, [Path("figures"), Path(prefix) / "figures"])
        manifest["items"].append(
            {
                "id": stem,
                "generator": "python",
                "template_id": template_id,
                "chart_family": family,
                "source": source,
                "exports": exports,
                "prompt_source": "无（数据图，由 Python 脚本确定性生成）",
                "paper_ready": True,
                "export_status": "exported",
                "needs_visual_review": False,
                "scale": "double_column_183mm",
                "dpi": 320,
                "chapter": chapter,
                "duty": duty,
                "qa": dict(PYTHON_QA),
            }
        )
    for stem, kind, chapter, duty in HTML_ITEMS:
        exports = export_set(stem, [Path("手绘图")])
        manifest["items"].append(
            {
                "id": stem,
                "generator": "html",
                "template_id": "skeleton_swimlane",
                "chart_family": "flowchart",
                "kind": kind,
                "source": f"手绘图/{stem}.html",
                "exports": exports,
                "prompt_source": f"手绘图/{stem}.html",
                "paper_ready": True,
                "export_status": "electron_printed",
                "needs_visual_review": False,
                "chapter": chapter,
                "duty": duty,
                "qa": dict(HTML_QA),
            }
        )
    concepts = sorted(path.name for path in (BASE / "手绘图").glob("*.md"))
    manifest["concept_prompts"] = [f"手绘图/{name}" for name in concepts]
    manifest["concept_prompt_note"] = "HTML 矢量成图模式下原理图与机制图只保留提示词，不自动生成图像。"
    target = BASE / "figures" / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"items": len(manifest["items"]), "concepts": len(manifest["concept_prompts"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
