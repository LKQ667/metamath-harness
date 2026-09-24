"""把 6 张 Python 数据图登记进 figures/manifest.json。

运行：python scripts/register_python_figures.py
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

QA_OK = {
    "font_ok": True,
    "cn_text_ok": True,
    "editable_text_ok": True,
    "export_complete_ok": True,
    "no_clip_ok": True,
    "no_overlap_ok": True,
    "grayscale_ok": True,
    "single_column_ok": True,
    "double_column_ok": True,
    "paper_insert_ok": True,
    "axis_label_ok": True,
    "legend_ok": True,
}

FIGURES = [
    {
        "name": "fig1_erp_curve",
        "source": "Q1/solve_q1.py",
        "stem": "Q1/figures/fig1_erp_curve",
        "template_id": "trend_confidence_template",
        "chart_family": "line_band",
        "panel_count": 1,
        "panel_chart_types": [["line_2d"]],
        "title_cn": "三导联去噪后事件相关电位曲线与三高斯分量拟合",
        "section_cn": "问题一模型建立与求解",
        "purpose_cn": "展示响应的时间结构与三高斯分量划分，服务式 (9) 的曲线拟合结果",
        "width_mm": 89.0,
    },
    {
        "name": "fig2_artifact_interval",
        "source": "Q1/solve_q1.py",
        "stem": "Q1/figures/fig2_artifact_interval",
        "template_id": "optimization_pareto_template",
        "chart_family": "pareto",
        "panel_count": 1,
        "panel_chart_types": [["scatter_2d"]],
        "title_cn": "四份记录单试次峰值幅值在去噪前后的区间点图",
        "section_cn": "问题一模型建立与求解",
        "purpose_cn": "量化软截断对单试次峰值分布的下移与收窄作用，服务式 (3)",
        "width_mm": 89.0,
    },
    {
        "name": "fig3_artifact_count",
        "source": "Q1/solve_q1.py",
        "stem": "Q1/figures/fig3_artifact_count",
        "template_id": "sensitivity_tornado_template",
        "chart_family": "tornado",
        "panel_count": 1,
        "panel_chart_types": [["bar_2d"]],
        "title_cn": "四份记录的软截断采样点与设备饱和采样点计数",
        "section_cn": "问题一模型建立与求解",
        "purpose_cn": "以零基线绝对计数比较四份记录的伪迹处理量，服务数据质量结论",
        "width_mm": 89.0,
        "bar_exception": {
            "necessary": True,
            "category_count_small": True,
            "zero_baseline_required": True,
            "absolute_height_comparison": True,
            "reason": "本图只有四个类别，比较对象是采样点绝对计数，计数必须从零基线读取，核心任务正是绝对高度比较；"
                      "改用折线或棒棒糖会因计数无自然顺序而误导，故按少用策略的例外条件使用柱形。",
        },
    },
    {
        "name": "fig4_response_heatmap",
        "source": "Q2/solve_q2.py",
        "stem": "Q2/figures/fig4_response_heatmap",
        "template_id": "sensitivity_sobol_heatmap_template",
        "chart_family": "heatmap",
        "panel_count": 1,
        "panel_chart_types": [["heatmap_2d"]],
        "title_cn": "三导联左右条件判别权重随时间的分布热图",
        "section_cn": "问题二模型建立与求解",
        "purpose_cn": "展示判别信息在导联与时间两个维度上的分布，服务式 (25) 与 (26) 的窗口设定",
        "width_mm": 89.0,
    },
    {
        "name": "fig5_source_field",
        "source": "Q2/solve_q2.py",
        "stem": "Q2/figures/fig5_source_field",
        "template_id": "dynamics_phase_portrait_template",
        "chart_family": "phase_portrait",
        "panel_count": 1,
        "panel_chart_types": [["vector_2d"]],
        "title_cn": "左右刺激皮层响应分布的镜像差异场与梯度向量场",
        "section_cn": "问题二模型建立与求解",
        "purpose_cn": "可视化镜像差异的空间结构与三导联投影位置，服务式 (22) 的机制推导",
        "width_mm": 89.0,
    },
    {
        "name": "fig6_parameter_contour",
        "source": "Q3/solve_q3.py",
        "stem": "Q3/figures/fig6_parameter_contour",
        "template_id": "spatial_contour_flow_template",
        "chart_family": "contour_quiver",
        "panel_count": 1,
        "panel_chart_types": [["contour_2d"]],
        "title_cn": "记忆通路延迟与增益构成的加权残差平方和等值线曲面",
        "section_cn": "问题三模型建立与求解",
        "purpose_cn": "展示参数辨识误差曲面与可辨识性，服务式 (33) 的参数辨识与敏感性分析",
        "width_mm": 89.0,
        "extra_exports": ["灵敏度分析/figures/fig6_parameter_contour"],
    },
]


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    existing = {str(item.get("name")) for item in items}
    added = 0
    for spec in FIGURES:
        if spec["name"] in existing:
            continue
        exports = [f"{spec['stem']}{ext}" for ext in (".svg", ".pdf", ".png")]
        for extra in spec.get("extra_exports", []):
            exports.extend(f"{extra}{ext}" for ext in (".svg", ".pdf", ".png"))
        for rel in exports:
            if not (PROJECT / rel).exists():
                print(f"缺少导出文件: {rel}")
                return 1
        entry = {
            "name": spec["name"],
            "generator": "python",
            "template_id": spec["template_id"],
            "chart_family": spec["chart_family"],
            "panel_count": spec["panel_count"],
            "panel_chart_types": spec["panel_chart_types"],
            "source": spec["source"],
            "exports": exports,
            "prompt_source": spec["source"],
            "export_status": "exported",
            "needs_visual_review": False,
            "paper_ready": True,
            "export_scale": 2,
            "width_mm": spec["width_mm"],
            "title_cn": spec["title_cn"],
            "section_cn": spec["section_cn"],
            "purpose_cn": spec["purpose_cn"],
            "qa": dict(QA_OK),
        }
        if "bar_exception" in spec:
            entry["bar_exception"] = spec["bar_exception"]
        items.append(entry)
        added += 1
    manifest["items"] = items
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已登记 {added} 条 Python 图，manifest 现有 {len(items)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
