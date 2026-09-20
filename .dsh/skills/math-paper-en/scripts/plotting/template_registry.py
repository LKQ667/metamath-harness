# -*- coding: utf-8 -*-
"""math-paper-en Python 绘图模板注册表。

每个模板对应一个唯一的 chart_family；跨问分配图型时不允许重复使用同一个
chart_family，热力图与柱状图在全文最多各出现一次。详见
references/py-chart-selection.md 与 scripts/checks/check_figure_diversity.py。
"""

TEMPLATE_REGISTRY = {
    "trend_confidence_template": {
        "task_family": "evolution",
        "chart_family": "line_band",
        "description": "趋势演化与置信带模板",
        "tags": ["evolution", "trend", "confidence"],
    },
    "causal_effects_line_template": {
        "task_family": "comparison",
        "chart_family": "multi_line",
        "description": "多方法折线对比模板",
        "tags": ["comparison", "multi-line"],
    },
    "sensitivity_tornado_template": {
        "task_family": "sensitivity",
        "chart_family": "tornado",
        "description": "敏感性 tornado 模板",
        "tags": ["sensitivity", "tornado"],
    },
    "sensitivity_sobol_heatmap_template": {
        "task_family": "sensitivity",
        "chart_family": "heatmap",
        "description": "Sobol 二阶交互热图模板（全文最多一张）",
        "tags": ["sensitivity", "heatmap", "sobol"],
    },
    "optimization_pareto_template": {
        "task_family": "optimization",
        "chart_family": "pareto",
        "description": "Pareto 前沿模板",
        "tags": ["optimization", "pareto"],
    },
    "optimization_convergence_template": {
        "task_family": "optimization",
        "chart_family": "convergence_line",
        "description": "优化收敛曲线模板",
        "tags": ["optimization", "convergence"],
    },
    "stats_interval_lollipop_template": {
        "task_family": "comparison",
        "chart_family": "lollipop",
        "description": "棒棒糖排序模板（不要求零基线）",
        "tags": ["comparison", "ranking", "lollipop"],
    },
    "range_interval_plot_template": {
        "task_family": "comparison",
        "chart_family": "interval_plot",
        "description": "区间与误差棒模板",
        "tags": ["comparison", "interval", "uncertainty"],
    },
    "distribution_raincloud_template": {
        "task_family": "distribution",
        "chart_family": "raincloud",
        "description": "雨云图模板（分布形状 + 离散度 + 原始点）",
        "tags": ["distribution", "raincloud", "violin"],
    },
    "distribution_ridgeline_template": {
        "task_family": "distribution",
        "chart_family": "ridgeline",
        "description": "山脊图模板（多组分布堆叠）",
        "tags": ["distribution", "ridgeline", "density"],
    },
    "decomposition_waterfall_template": {
        "task_family": "decomposition",
        "chart_family": "waterfall",
        "description": "贡献分解瀑布图模板（线段形式，避开柱形 API）",
        "tags": ["decomposition", "waterfall", "contribution"],
    },
    "ranking_slope_bump_template": {
        "task_family": "ranking",
        "chart_family": "slope_bump",
        "description": "排名变化斜率图模板",
        "tags": ["ranking", "slope", "bump"],
    },
    "composition_sankey_alluvial_template": {
        "task_family": "composition",
        "chart_family": "sankey_alluvial",
        "description": "桑基/冲积图模板（构成与流向）",
        "tags": ["composition", "sankey", "alluvial", "flow"],
    },
    "cluster_dendrogram_template": {
        "task_family": "clustering",
        "chart_family": "dendrogram",
        "description": "层次聚类树模板",
        "tags": ["clustering", "dendrogram", "hierarchy"],
    },
    "timeline_gantt_segments_template": {
        "task_family": "scheduling",
        "chart_family": "timeline_gantt",
        "description": "进度/排程甘特模板（线段形式，避开柱形 API）",
        "tags": ["scheduling", "timeline", "gantt"],
    },
    "relation_bubble_scatter_template": {
        "task_family": "relation",
        "chart_family": "bubble_scatter",
        "description": "气泡散点模板（三变量同图）",
        "tags": ["relation", "bubble", "scatter"],
    },
    "density_hexbin_template": {
        "task_family": "density",
        "chart_family": "hexbin_density",
        "description": "六边形密度模板（密集双变量）",
        "tags": ["density", "hexbin", "bivariate"],
    },
    "classification_roc_curve_template": {
        "task_family": "classification",
        "chart_family": "roc_curve",
        "description": "ROC 判别能力模板",
        "tags": ["classification", "roc", "auc"],
    },
    "surface3d_response_template": {
        "task_family": "response_surface",
        "chart_family": "surface3d",
        "description": "三维响应面模板（带投影等值线）",
        "tags": ["response-surface", "3d", "surface"],
    },
    "profile_radar_template": {
        "task_family": "multicriteria",
        "chart_family": "radar_profile",
        "description": "多准则雷达图模板",
        "tags": ["multicriteria", "radar", "profile"],
    },
    "dynamics_phase_portrait_template": {
        "task_family": "dynamics",
        "chart_family": "phase_portrait",
        "description": "动力学相图模板",
        "tags": ["dynamics", "phase-portrait"],
    },
    "spatial_contour_flow_template": {
        "task_family": "spatial",
        "chart_family": "contour_quiver",
        "description": "空间等值线与流向模板",
        "tags": ["spatial", "contour", "quiver"],
    },
    "network_resilience_template": {
        "task_family": "network",
        "chart_family": "resilience_curve",
        "description": "网络鲁棒性模板（拓扑 + 失效曲线）",
        "tags": ["network", "resilience", "multi-panel"],
    },
    "network_curvature_multiscale_template": {
        "task_family": "network",
        "chart_family": "network_curvature_multiscale",
        "description": "网络曲率与多尺度社区模板",
        "tags": ["network", "curvature", "multiscale"],
    },
    "spatiotemporal_chronological_network_template": {
        "task_family": "spatiotemporal",
        "chart_family": "chronological_network",
        "description": "时空 Chronnet 模板（空间 + 网络 + 摘要）",
        "tags": ["spatiotemporal", "network", "chronological"],
    },
    "temporal_bursty_activity_template": {
        "task_family": "temporal",
        "chart_family": "bursty_activity",
        "description": "时间突发活动与事件间隔分布模板",
        "tags": ["temporal", "burst", "distribution"],
    },
    "multi_panel_hero_support_template": {
        "task_family": "mechanism",
        "chart_family": "hero_support",
        "description": "hero + supporting 多面板模板",
        "tags": ["multi-panel", "hero-support", "mechanism"],
    },
    "python_flowchart_topdown": {
        "task_family": "flowchart",
        "chart_family": "flowchart",
        "description": "技术路线图与流程图模板（非数据图，不占用图型配额）",
        "tags": ["flowchart", "roadmap", "process"],
    },
}


def chart_families() -> list[str]:
    """返回全部数据图家族（不含非数据流程图）。"""
    return sorted(
        {item["chart_family"] for item in TEMPLATE_REGISTRY.values() if item["task_family"] != "flowchart"}
    )


def template_for_family(family: str) -> str | None:
    for name, item in TEMPLATE_REGISTRY.items():
        if item["chart_family"] == family:
            return name
    return None