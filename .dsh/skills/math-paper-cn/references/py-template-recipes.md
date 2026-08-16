# Python 绘图模板与多面板范式

## 模板入口

内置模板目录：`assets/templates/py-figures/`

- `trend_confidence_template.py`
- `sensitivity_tornado_template.py`
- `sensitivity_sobol_heatmap_template.py`
- `optimization_pareto_template.py`
- `optimization_convergence_template.py`
- `network_resilience_template.py`
- `network_curvature_multiscale_template.py`
- `dynamics_phase_portrait_template.py`
- `spatial_contour_flow_template.py`
- `spatiotemporal_chronological_network_template.py`
- `stats_interval_lollipop_template.py`
- `temporal_bursty_activity_template.py`
- `multi_panel_hero_support_template.py`
- `causal_effects_line_template.py`

模板注册表：`scripts/plotting/template_registry.py`

## 1. hero_top_support_bottom

- 适用：机制说明、网络场景、流程 + 定量支撑
- 布局：上方 1 个大 panel，下方 2–4 个支撑 panel
- 原则：hero 占总高度 `50%~60%`

## 2. right_hero_stack

- 适用：一个核心图占主导，左侧放 2–3 个辅助图
- 布局：右侧纵向大 panel，左侧分层辅助
- 原则：强调“主结论先看什么”

## 3. single_row_with_legend

- 适用：多个并列小图，且图例较大
- 布局：最后一个 panel 专门放 legend
- 原则：图例不压在数据上

## 4. two_by_two

- 适用：四个同级证据图
- 布局：2x2
- 原则：仅在信息层级确实接近时用，不要滥用

## 5. single_column_stack

- 适用：单栏排版、空间窄、阅读顺序强
- 布局：自上而下堆叠
- 原则：各 panel 保持相同 x 逻辑或同一叙事轴

## 6. network_hero_curve_stack

- 适用：网络几何、网络鲁棒性、多尺度社区
- 布局：左侧或上方大网络主图，右侧或下方堆叠 2 张统计/阈值/时间尺度曲线
- 原则：结构图只负责“对象与局部高亮”，量化指标放支撑 panel

## 7. map_network_summary

- 适用：时空网络、地理网络、网格转网络
- 布局：空间主图 + 网络结构图 + 指标摘要图
- 原则：空间视图和网络视图共用颜色语义，摘要图不重新发明色板

## 8. flowchart_top_down

- 适用：技术路线图、问题分析流程图、模块求解链
- 布局：单主线自上而下，必要时左右分列承接分支
- 原则：每个节点一句中文短语，箭头短而清楚，标签不堆叠
- 入口：`scripts/plotting/python_flowchart.py` 仅保留旧项目兼容；新项目非数据流程图必须按项目锁定的 Draw.io / AI 链路生成

## 统一细节

- panel 标号统一左上
- 面板间距克制，不贴死
- 白底图和深底图相邻时增大间距
- 复杂图例优先独立 panel
- 不给每个 panel 加装饰边框
- 同一方法在不同 panel 不换色，同一色条在不同 panel 不改端点语义
