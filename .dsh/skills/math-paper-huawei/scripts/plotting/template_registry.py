"""内置 Python 模板注册表。

`panel_count` 是语义面板数：一张成图内的独立数据视图数量，colorbar 与 legend 不计入。
`single_panel_equivalent` 指向语义等价的单面板模板；为 None 表示必须拆成多张独立图。
`chart_types` 是未改绘模板的默认图型元数据（二维数组）：外层按语义面板顺序、长度等于
panel_count，内层为该面板的视觉编码类型（无数据内容的图例/装饰轴为空列表）。归并规则：
multi_line/line_band/收敛折线/带点折线/置信带 → line_2d；一行列与矩阵热图 → heatmap_2d；
带误差线的区间点图 → scatter_2d；棒棒糖/tornado 长度编码 → bar_2d；CCDF/分布曲线 →
distribution_2d；等值线填充 → contour_2d；quiver/streamplot → vector_2d；网络结构 → network_2d。
图型重复统计只认 `panel_chart_types`/本默认元数据，改颜色、标题或模板名不产生新类型。
"""

TEMPLATE_REGISTRY = {
    "causal_effects_line_template": {
        "task_family": "comparison",
        "chart_family": "multi_line",
        "description": "直接因果效应多方法折线模板",
        "tags": ["comparison", "causal", "multi-line"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["line_2d"]],
    },
    "trend_confidence_template": {
        "task_family": "evolution",
        "chart_family": "line_band",
        "description": "趋势演化与置信带模板",
        "tags": ["evolution", "trend", "confidence"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["line_2d"]],
    },
    "sensitivity_tornado_template": {
        "task_family": "sensitivity",
        "chart_family": "tornado",
        "description": "敏感性 tornado 模板",
        "tags": ["sensitivity", "tornado"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["bar_2d"]],
    },
    "sensitivity_sobol_heatmap_template": {
        "task_family": "sensitivity",
        "chart_family": "heatmap",
        "description": "Sobol 热图模板",
        "tags": ["sensitivity", "heatmap", "sobol"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["heatmap_2d"]],
    },
    "optimization_pareto_template": {
        "task_family": "optimization",
        "chart_family": "pareto",
        "description": "Pareto 前沿模板",
        "tags": ["optimization", "pareto"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["scatter_2d", "line_2d"]],
    },
    "optimization_convergence_template": {
        "task_family": "optimization",
        "chart_family": "line_band",
        "description": "优化收敛模板",
        "tags": ["optimization", "convergence", "line-band"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["line_2d"]],
    },
    "network_resilience_template": {
        "task_family": "network",
        "chart_family": "network_curve",
        "description": "网络鲁棒性模板（结构 + 渗流曲线）",
        "tags": ["network", "resilience", "multi-panel"],
        "panel_count": 3,
        "single_panel_equivalent": None,
        "chart_types": [["network_2d"], ["line_2d"], []],
    },
    "network_curvature_multiscale_template": {
        "task_family": "network",
        "chart_family": "network_curvature_multiscale",
        "description": "网络曲率与多尺度社区模板",
        "tags": ["network", "curvature", "multiscale"],
        "panel_count": 3,
        "single_panel_equivalent": None,
        "chart_types": [["network_2d"], ["line_2d"], ["line_2d"]],
    },
    "dynamics_phase_portrait_template": {
        "task_family": "dynamics",
        "chart_family": "phase_portrait",
        "description": "动力学相图模板",
        "tags": ["dynamics", "phase-portrait"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["vector_2d", "line_2d"]],
    },
    "spatial_contour_flow_template": {
        "task_family": "spatial",
        "chart_family": "contour_quiver",
        "description": "空间等值线与流向模板（colorbar 不计 panel）",
        "tags": ["spatial", "contour", "quiver"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["contour_2d", "vector_2d"]],
    },
    "spatiotemporal_chronological_network_template": {
        "task_family": "spatiotemporal",
        "chart_family": "chronological_network",
        "description": "时空 Chronnet 网络模板（空间 + 网络 + 摘要）",
        "tags": ["spatiotemporal", "network", "chronological"],
        "panel_count": 3,
        "single_panel_equivalent": None,
        "chart_types": [["heatmap_2d"], ["network_2d"], ["line_2d"]],
    },
    "stats_interval_lollipop_template": {
        "task_family": "comparison",
        "chart_family": "interval_lollipop",
        "description": "区间图与棒棒糖排序模板",
        "tags": ["comparison", "interval", "lollipop"],
        "panel_count": 4,
        "single_panel_equivalent": None,
        "chart_types": [["scatter_2d"], ["bar_2d"], [], []],
    },
    "temporal_bursty_activity_template": {
        "task_family": "temporal",
        "chart_family": "bursty_activity",
        "description": "时间网络突发活动模板（时间线 + 分布）",
        "tags": ["temporal", "burst", "distribution"],
        "panel_count": 3,
        "single_panel_equivalent": "trend_confidence_template",
        "chart_types": [["line_2d"], ["distribution_2d"], []],
    },
    "multi_panel_hero_support_template": {
        "task_family": "mechanism",
        "chart_family": "hero_support",
        "description": "hero + supporting 多面板模板",
        "tags": ["multi-panel", "hero-support", "mechanism"],
        "panel_count": 4,
        "single_panel_equivalent": None,
        "chart_types": [["network_2d"], ["line_2d"], ["bar_2d"], ["scatter_2d", "line_2d"]],
    },
    "python_flowchart_topdown": {
        "task_family": "flowchart",
        "chart_family": "flowchart",
        "description": "技术路线图与流程图模板",
        "tags": ["flowchart", "roadmap", "process"],
        "panel_count": 1,
        "single_panel_equivalent": None,
        "chart_types": [["flowchart"]],
    },
}

# 受支持的图型 ID；流程图/非数据图不参与图型重复统计，但保留其 ID 以登记非数据面板。
SUPPORTED_CHART_TYPES = {
    "line_2d",
    "heatmap_2d",
    "scatter_2d",
    "bar_2d",
    "box_2d",
    "distribution_2d",
    "contour_2d",
    "vector_2d",
    "network_2d",
    "flowchart",
}
# 不参与图型重复统计的类型（非数据流程图）。
NON_DATA_CHART_TYPES = {"flowchart"}


def template_panel_count(template_id: str) -> int | None:
    entry = TEMPLATE_REGISTRY.get(str(template_id or ""))
    return entry.get("panel_count") if entry else None


def single_panel_equivalent(template_id: str) -> str | None:
    entry = TEMPLATE_REGISTRY.get(str(template_id or ""))
    return entry.get("single_panel_equivalent") if entry else None


def template_chart_types(template_id: str) -> list[list[str]] | None:
    """未经改绘模板的默认图型元数据；未注册返回 None。"""
    entry = TEMPLATE_REGISTRY.get(str(template_id or ""))
    value = entry.get("chart_types") if entry else None
    return [list(panel) for panel in value] if isinstance(value, list) else None


def is_multi_panel(template_id: str) -> bool:
    count = template_panel_count(template_id)
    return bool(count and count > 1)


def select_template(template_id: str, subplot_policy: str = "默认") -> dict:
    """按子图策略给出可直接使用且已注册的模板；不产生未注册的伪模板 ID。

    返回 {"template_id","policy","ok","templates","needs_manual_split","reason"}：
    - 非禁用或单面板：templates=[template_id]；
    - 禁用+多面板且有 single_panel_equivalent：templates=[等价单图模板]（必须已注册）；
    - 禁用+多面板且无等价：ok=False、needs_manual_split=True、templates=[]，
      reason 指明需要按原图语义拆分并编写真正的单图模板，禁止用 `#panelN` 字符串凑数。
    """
    policy = str(subplot_policy or "").strip() or "默认"
    result = {
        "template_id": template_id,
        "policy": policy,
        "ok": True,
        "templates": [template_id],
        "needs_manual_split": False,
        "reason": "",
    }
    if "禁用" not in policy or not is_multi_panel(template_id):
        return result
    equivalent = single_panel_equivalent(template_id)
    if equivalent and equivalent in TEMPLATE_REGISTRY:
        result["templates"] = [equivalent]
        result["reason"] = f"已切换为语义等价单图模板: {equivalent}"
        return result
    result["ok"] = False
    result["templates"] = []
    result["needs_manual_split"] = True
    result["reason"] = (
        f"需要按原图语义拆分：{template_id} 为 {template_panel_count(template_id)} 面板模板且无单图等价实现；"
        "请编写真正的单图模板并登记元数据，不得使用未注册的伪模板 ID。"
    )
    return result
