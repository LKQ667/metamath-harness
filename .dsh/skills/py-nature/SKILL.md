---
name: py-nature
description: 用 Python 绘制数学建模竞赛论文与科研论文配图的 Nature 风格技能。适用于趋势演化、敏感性分析、多目标优化、网络传播、空间分布、动力学机理、统计比较和多面板论文图；内置中文友好的顶刊风格样式、图型决策规则、导出规范与模板。默认避免非必要二维竖直柱状图，不适用于交互式可视化、网页仪表盘或 R/Prism/Illustrator-first 流程。
user-invocable: true
disable-model-invocation: true
---

# Py-Nature

## Overview

`Py-Nature` 是一个 **Python-only** 的数学建模论文绘图技能，目标是把“数据语义 -> 图型 -> 多面板布局 -> Nature 规范导出”做成稳定流程。

先判断任务类型，再选图，不先画柱状图再凑解释。

## DeepSeek Harness mathmodel 入口契约

本 Skill 只能由用户手动调用。若请求包含 `dsh.mathmodel.request/v1`，其 `skill` 必须为 `py-nature`，直接消费 `data_path`、`analysis_goal`、`chart_type`、`bar_policy`、`three_d_preference`、`figure_size`、`dpi`、`formats`、`output_dir` 和 `userNotes`，不得重复询问；输入与输出相对路径均以当前工作区解析，输出目录不得越出工作区。

`chart_type=由语义分析` 时按既有决策树选图，其他值只限定图型家族而不跳过语义检查。`bar_policy=禁用` 时禁止柱状图；`少用` 时仅保留既有三项例外；`正常` 时仍须证明柱图比点图、区间图或曲线更适合。`three_d_preference` 只控制评估优先级，三维图不能提升信息密度时不得强画。严格按 `figure_size`、`dpi` 和 `formats` 导出并完成 QA，保留可复现脚本，不修改源数据。

## 何时使用

- 用户要做数学建模竞赛论文、SCI 论文、研究报告的正式配图
- 用户明确提到 `Nature 风格`、`顶刊风格`、`中文科研绘图`、`Python 绘图模板`
- 任务属于以下之一：趋势演化、敏感性分析、优化过程、Pareto、多方案比较、复杂网络、渗流传播、相图、空间热力/等值线、置信区间比较、多面板组合
- 需要导出 `svg + pdf + png`，并要求文字可编辑、版式规范、色彩克制

## 不适用

- Plotly / Altair / Bokeh 等交互式图
- 只是探索性 EDA，没有论文交付目标
- 主要流程依赖 R、Origin、Prism、Illustrator 或 GIS 专用软件
- 用户要营销海报、网页大屏、信息图而不是科研论文图

## 固定工作流

1. **识别任务语义**
   - `comparison`：方案对比、排名比较、区间比较
   - `evolution`：时间序列、收敛过程、动态演化
   - `sensitivity`：敏感性、Sobol、局部扰动
   - `optimization`：Pareto、可行域、目标权衡
   - `network`：拓扑、节点角色、鲁棒性、传播
   - `spatial`：空间分布、流向、等值线、栅格
   - `dynamics`：相图、轨迹、向量场、状态跃迁
   - `mechanism`：流程机制图 + 定量支撑图

2. **按任务选图型**
   - 先读 [references/chart-selection.md](references/chart-selection.md)
   - 默认禁止把“比较”直接降级成二维竖直柱图

3. **应用统一样式**
   - 用 `scripts/py_nature_core.py` 中的：
     - `apply_py_nature_style(...)`
     - `save_py_nature_figure(...)`
     - `choose_chart_family(...)`
     - `compose_multi_panel(...)`
     - `run_py_nature_qa(...)`

4. **必要时做多面板**
   - 优先 `主结论 panel + 辅证据 panel`
   - 面板不要求等大
   - 先看 [references/layout-recipes.md](references/layout-recipes.md)

5. **导出前 QA**
   - 字体、字号、留白、对比度、彩色文字、可编辑文本、文件格式都按 [references/nature-rules.md](references/nature-rules.md) 过一遍

## 图型决策硬规则

- **非必要不用二维竖直柱状图**
- 类别排序：优先 `lollipop` / `dot plot`
- 区间、不确定性、置信区间：优先 `forest` / `interval plot`
- 过程变化：优先 `line + band`
- 敏感性：优先 `tornado` 或热图
- 多目标优化：优先 `Pareto scatter`
- 网络与传播：优先 `topology + curve`
- 动力学：优先 `phase portrait`、轨迹、向量场
- 空间场：优先 `contour + heat + quiver`
- 只有在“类别少、必须零基线、核心任务是绝对高度比较”时，才允许竖直柱图

## 颜色与版式

- 基础规范看 [references/palette-system.md](references/palette-system.md)
- Nature 官方尺寸、字体、导出规则看 [references/nature-rules.md](references/nature-rules.md)
- 10 篇参考论文与 10 轮截图蒸馏摘要看 [references/paper-digests.md](references/paper-digests.md)
- 运行时只读取本 Skill 随附的 `references/` 与 `assets/`，不依赖外部固定盘符学习目录

## 模板入口

模板位于 `assets/templates/`：

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

如需批量跑模板或做快速演示，使用：

- `scripts/render_template_demo.py`
- `scripts/run_py_nature_qa.py`

## 资源导航

| 文件 | 何时打开 |
|------|----------|
| [references/chart-selection.md](references/chart-selection.md) | 要根据任务语义选图型 |
| [references/palette-system.md](references/palette-system.md) | 要统一配色角色 |
| [references/layout-recipes.md](references/layout-recipes.md) | 要组织多面板布局 |
| [references/nature-rules.md](references/nature-rules.md) | 导出与期刊规范检查 |
| [references/paper-digests.md](references/paper-digests.md) | 需要借鉴 10 篇 Nature 系论文与 10 轮截图蒸馏的布局和组合方式 |
| [scripts/template_registry.py](scripts/template_registry.py) | 想查模板名、适用任务、推荐场景 |

## 使用边界

- 本技能强调**论文级**输出，不追求交互特效
- 可以用中文标签，但仍遵循 Nature 风格的克制排版
- 不复刻某一篇论文的具体视觉资产，只蒸馏配色、层级、布局和编码习惯
