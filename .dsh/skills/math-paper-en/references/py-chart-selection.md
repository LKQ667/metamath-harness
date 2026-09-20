# 逐问图型分配与多样性硬规则 (math-paper-en)

本文件定义美赛英语赛道的 Python 数据图决策流程。核心目标不是把每种图都画一遍，而是**让每一问的图型互不相同，并让每张图承担不可替代的论证职责**。

## 1. 硬规则 (门禁强制)

1. 全文每一问的数据图必须使用互不相同的 `chart_family`；同一家族不得跨问重复。
2. 同一个小问内默认也不允许重复同一 `chart_family`；确有需要时必须在同源 manifest 条目写明 `repeat_exception`。
3. 热力图家族 (`heatmap`、`sobol_heatmap`、`grid_heatmap`) 全文最多 1 张。
4. 柱状图家族 (`bar`、`barh`、`column`、`grouped_bar`、`stacked_bar`) 全文最多 1 张，且必须在同源 manifest 条目写明完整 `bar_exception`；`bar_policy=禁用` 时为零例外。
5. 每个小问至少 1 张数据图；确实不出图时，必须在 `Qn/result.md` 写明不出图理由与可复现结果来源。
6. 不重复图型数量不得少于小问数；`figure_total` 默认 15 张，图型池见 `py-template-recipes.md`，共 27 个数据图家族。
7. 禁止全篇热力图、全篇柱状图、全篇折线图，以及只换色改标题的换色变体。

以上规则由 `scripts/checks/check_figure_diversity.py` 在 step3 起逐步校验，step5 全量回归。

## 2. 分配协议 (step2 定计划，step3 才画图)

1. step2 结束时为 Q1 到 Qn 各选一个主图家族，先保证互不相同，再考虑是否增加支撑图。
2. 把计划写入 `figures/manifest.json`，每条至少包含：`chart_family`、`question`、`source`、`generator="python"`、`template_id`、`exports`、`paper_ready`、`qa`。
3. 选图统一调用 `scripts/plotting/py_nature_core.py` 的 `choose_chart_family(task_type, data_semantics, compare_goal, need_uncertainty, used_families=[...])`，其中 `used_families` 传入其它小问已占用的家族；函数保证返回不重复家族，并在首选家族被占用时按 `DIVERSITY_FALLBACK` 自动升级。
4. step3 按 manifest 逐图实现：从 `assets/templates/py-figures/` 取对应模板改写，导出 `svg + pdf + png`，先自检再入文。
5. 每张小问的主图必须与该问的核心结论绑定：主图回答"这一问的结论是什么"，支撑图回答"结论为什么可信"。
## 3. 任务语义到图型的映射

| 任务语义 | 首选家族 | 备选家族 | 明确避免 |
|---|---|---|---|
| 趋势与演化 | `line_band` | `multi_line`、`stacked_area` | 单点柱图 |
| 多方法对比 | `multi_line` | `interval_plot`、`slope_bump` | 竖直柱图 |
| 排名与打分 | `lollipop` | `slope_bump`、`radar_profile` | 从零基线的柱图 |
| 区间与不确定性 | `interval_plot` | `raincloud`、`hexbin_density` | 只有均值无区间的柱图 |
| 分布与离散度 | `raincloud` | `ridgeline`、`hexbin_density` | 只给均值 |
| 敏感性分析 | `tornado` | `heatmap` (全文最多 1 张) | 竖直柱状敏感性比较 |
| 多目标权衡 | `pareto` | `bubble_scatter` | 单目标排名柱图 |
| 优化收敛 | `convergence_line` | `line_band` | 表格堆数字 |
| 贡献分解 | `waterfall` | `sankey_alluvial` | 纯饼图 |
| 构成与流向 | `sankey_alluvial` | `stacked_area`、`waterfall` | 类别过多的饼图 |
| 层次聚类 | `dendrogram` | `radar_profile` | 只给聚类标签 |
| 排程与区间计划 | `timeline_gantt` | `slope_bump` | 柱形甘特 |
| 三变量关系 | `bubble_scatter` | `hexbin_density` | 三张单变量图拼贴 |
| 密集双变量 | `hexbin_density` | `bubble_scatter`、`contour_quiver` | 过密散点 |
| 分类判别能力 | `roc_curve` | `bubble_scatter` | 只报准确率 |
| 响应面与最优域 | `surface3d` | `contour_quiver`、`pareto` | 只给最优值 |
| 多准则评价 | `radar_profile` | `lollipop` | 加权总分柱图 |
| 动力学行为 | `phase_portrait` | `trajectory3d` | 只给一条时序线 |
| 空间场与流向 | `contour_quiver` | `heatmap`、`surface3d` | 离散柱高 |
| 网络结构与鲁棒性 | `resilience_curve` | `network_curvature_multiscale` | 只给节点数柱图 |
| 网络几何与多尺度 | `network_curvature_multiscale` | `dendrogram` | 压缩成单张柱图 |
| 时空网络 | `chronological_network` | `contour_quiver` | 空间与网络拆成无关小图 |
| 事件过程与突发 | `bursty_activity` | `timeline_gantt` | 只给事件频次柱图 |
| 机制与多面板主图 | `hero_support` | `multi_line` | 无主次的四宫格 |

## 4. 三维图评估

每轮图型决策都要判断能否用三维曲面、三维散点、三维轨迹、三维场或三维响应面提升信息密度，并在三轮自查中记录"顶刊一区三维图可行性评估"；不采用时必须写明原因 (例如二维剖面更清晰、读数更可靠)。

## 5. 反模式

- 所有小问都用热力图或都用柱状图，只换标题与配色。
- 类别超过 4 个仍用柱图；需要排序、误差区间、过程变化、目标权衡、网络或空间结构时仍用柱图。
- 同一方法在不同 panel 换色，或同一色条在不同 panel 改变端点语义。
- 用三维图做装饰，不给读数帮助；用饼图表达多于 5 个类别。
- 图注只写"如图 X 所示"，不在正文解释图形含义与结论。