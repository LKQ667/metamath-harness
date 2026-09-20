# Python 绘图模板清单与 manifest 范式 (math-paper-en)

模板目录: `assets/templates/py-figures/`；注册表: `scripts/plotting/template_registry.py`；绘图核心: `scripts/plotting/py_nature_core.py`。

所有模板都以 `PROFILE = "competition_en"` 调用 `apply_py_nature_style` 与 `save_py_nature_figure`，导出 `svg + pdf + png`，因此模板内文字、图例、坐标轴默认就是英文字体与英文标签。

## 1. 模板与图型家族对照

| 模板文件 | chart_family | 适用场景 | 标签 |
|---|---|---|---|
| `causal_effects_line_template.py` | `multi_line` | 多方法折线对比模板 | comparison, multi-line |
| `classification_roc_curve_template.py` | `roc_curve` | ROC 判别能力模板 | classification, roc, auc |
| `cluster_dendrogram_template.py` | `dendrogram` | 层次聚类树模板 | clustering, dendrogram, hierarchy |
| `composition_sankey_alluvial_template.py` | `sankey_alluvial` | 桑基/冲积图模板（构成与流向） | composition, sankey, alluvial, flow |
| `decomposition_waterfall_template.py` | `waterfall` | 贡献分解瀑布图模板（线段形式，避开柱形 API） | decomposition, waterfall, contribution |
| `density_hexbin_template.py` | `hexbin_density` | 六边形密度模板（密集双变量） | density, hexbin, bivariate |
| `distribution_raincloud_template.py` | `raincloud` | 雨云图模板（分布形状 + 离散度 + 原始点） | distribution, raincloud, violin |
| `distribution_ridgeline_template.py` | `ridgeline` | 山脊图模板（多组分布堆叠） | distribution, ridgeline, density |
| `dynamics_phase_portrait_template.py` | `phase_portrait` | 动力学相图模板 | dynamics, phase-portrait |
| `multi_panel_hero_support_template.py` | `hero_support` | hero + supporting 多面板模板 | multi-panel, hero-support, mechanism |
| `network_curvature_multiscale_template.py` | `network_curvature_multiscale` | 网络曲率与多尺度社区模板 | network, curvature, multiscale |
| `network_resilience_template.py` | `resilience_curve` | 网络鲁棒性模板（拓扑 + 失效曲线） | network, resilience, multi-panel |
| `optimization_convergence_template.py` | `convergence_line` | 优化收敛曲线模板 | optimization, convergence |
| `optimization_pareto_template.py` | `pareto` | Pareto 前沿模板 | optimization, pareto |
| `profile_radar_template.py` | `radar_profile` | 多准则雷达图模板 | multicriteria, radar, profile |
| `python_flowchart_topdown.py` | `flowchart` | 技术路线图与流程图模板（非数据图，不占用图型配额） | flowchart, roadmap, process |
| `range_interval_plot_template.py` | `interval_plot` | 区间与误差棒模板 | comparison, interval, uncertainty |
| `ranking_slope_bump_template.py` | `slope_bump` | 排名变化斜率图模板 | ranking, slope, bump |
| `relation_bubble_scatter_template.py` | `bubble_scatter` | 气泡散点模板（三变量同图） | relation, bubble, scatter |
| `sensitivity_sobol_heatmap_template.py` | `heatmap` | Sobol 二阶交互热图模板（全文最多一张） | sensitivity, heatmap, sobol |
| `sensitivity_tornado_template.py` | `tornado` | 敏感性 tornado 模板 | sensitivity, tornado |
| `spatial_contour_flow_template.py` | `contour_quiver` | 空间等值线与流向模板 | spatial, contour, quiver |
| `spatiotemporal_chronological_network_template.py` | `chronological_network` | 时空 Chronnet 模板（空间 + 网络 + 摘要） | spatiotemporal, network, chronological |
| `stats_interval_lollipop_template.py` | `lollipop` | 棒棒糖排序模板（不要求零基线） | comparison, ranking, lollipop |
| `surface3d_response_template.py` | `surface3d` | 三维响应面模板（带投影等值线） | response-surface, 3d, surface |
| `temporal_bursty_activity_template.py` | `bursty_activity` | 时间突发活动与事件间隔分布模板 | temporal, burst, distribution |
| `timeline_gantt_segments_template.py` | `timeline_gantt` | 进度/排程甘特模板（线段形式，避开柱形 API） | scheduling, timeline, gantt |
| `trend_confidence_template.py` | `line_band` | 趋势演化与置信带模板 | evolution, trend, confidence |

每个 `chart_family` 只对应一个模板；跨问分配时不得重复使用同一家族，详见 `py-chart-selection.md`。

## 2. 标准调用方式

```python
from py_nature_core import choose_chart_family, apply_py_nature_style, save_py_nature_figure

pick = choose_chart_family("sensitivity", used_families=["line_band", "pareto"])
# pick["family"] 给出未被占用且在本文可用的家族，pick["diversity_forced"] 表示已按多样性升级
apply_py_nature_style(font_size=7.0, profile="competition_en")
save_py_nature_figure(fig, Path(out) / "q2_sensitivity", profile="competition_en")
```

## 3. manifest 条目范式

```json
{
  "source": "Q2/figures/q2_sensitivity.py",
  "generator": "python",
  "template_id": "sensitivity_tornado_template",
  "chart_family": "tornado",
  "question": "Q2",
  "exports": ["Q2/figures/q2_sensitivity.svg", "Q2/figures/q2_sensitivity.pdf", "Q2/figures/q2_sensitivity.png"],
  "paper_ready": true,
  "qa": {"label_text_ok": true, "export_ok": true, "editable_text_ok": true, "profile": "competition_en"}
}
```

- `chart_family` 必填，且必须与所用模板的家族一致。
- `question` 必填或从 `Qn/` 路径可推断；不写会被多样性检查判为无法归属。
- 热力图家族的 `qa` 建议附 `top_journal_3d_recommended` 之外的多样性说明；柱状图家族必须附完整 `bar_exception`。
- 同一小问内重复家族必须附 `repeat_exception`。

## 4. 多面板布局

`compose_multi_panel` 提供 `hero_top_support_bottom`、`right_hero_stack`、`single_row_with_legend`、`single_column_stack`、`network_hero_curve_stack`、`map_network_summary` 与默认 2x2。panel 标号统一用 `add_panel_label`，图例优先独立 panel，不给每个 panel 加装饰边框，同一方法在不同 panel 不换色。
