# 数学建模图型决策树

## 核心原则

先选配置：中文赛用 competition_cn（默认），英文赛用 competition_en；只有明确要求科研投稿图时用 research。赛事官方规范优先于期刊风格偏好。

先执行锁定策略，再判断数据语义。`bar_policy=禁用` 时零例外禁止所有柱形 API，时间轴、甘特图和区间图也改用线段与端点标记；`bar_policy=少用` 只有“类别很少、必须零基线、核心任务是绝对高度比较”同时成立，且在同源 manifest 条目写明完整 `bar_exception` 时才允许；`bar_policy=正常` 仍按信息表达需要选图。

强烈建议优先评估顶刊一区中文三维图：对空间场、响应面、多参数敏感性、优化曲面、动态轨迹和多变量耦合结果，优先考虑三维曲面、三维散点、三维轨迹、三维场或三维响应面；若最终不采用三维图，必须在三轮自查中记录“三维图可行性评估”和放弃理由。

## 决策映射

### 1. 排名 / 方案高低

- 默认：`lollipop`
- 备选：`dot plot`
- 允许柱图：仅在类别很少、必须从零基线比较绝对高度时，并记录 `bar_exception`

### 2. 区间 / 误差 / 置信区间

- 默认：`forest`
- 备选：`interval plot`
- 不推荐：只有均值、没有区间表达的普通柱图

### 3. 时间过程 / 收敛过程 / 动态演化

- 默认：`line + confidence band`
- 备选：多线趋势图、累计面积图

### 4. 敏感性分析

- 默认：`tornado`
- 备选：Sobol 热图、局部扰动响应曲线
- 禁止默认：竖直柱状敏感性比较

### 5. 多目标优化 / 权衡

- 默认：`Pareto scatter`
- 备选：可行域 + 前沿线

### 6. 网络 / 复杂系统 / 传播

- 默认：`拓扑结构 + 指标曲线`
- 备选：节点角色图、渗流曲线、级联失效曲线

### 6a. 网络几何 / 曲率 / 多尺度社区

- 默认：`network curvature + scale curve`
- 备选：网络几何主图 + 社区稳定性支撑图
- 禁止默认：把多尺度结构压扁成单张柱图

### 6b. 时序网络 / 突发活动

- 默认：`timeline / burst curve + distribution summary`
- 备选：事件列线、CCDF、滚动强度曲线
- 禁止默认：只给事件频次柱图

### 6c. 时空网络 / Chronnet / 网格转网络

- 默认：`map/grid + chronological network + summary`
- 备选：空间热图 + 网络拓扑 + 指标曲线
- 禁止默认：空间和网络拆成互不关联的独立小图

### 7. 动力学 / 微分方程 / 状态转移

- 默认：`phase portrait`
- 备选：轨迹图、向量场、状态转移示意

### 8. 空间场 / 区域分布

- 默认：`contour / heatmap / quiver`
- 备选：区域填色、剖面曲线

### 9. 多面板论文图

- 默认：单图；只有多个视图共同回答同一研究问题、需要共享坐标或共享图例、或必须直接并列比较时，才用 `hero panel + supporting panels`。
- 原则：主结论占更大版面，支撑图减少视觉噪声；互相独立的结论拆为多张单图，不用 hero/support 强行合并。

## 子图策略（`subplot_policy`）

“子图”按语义面板计数：`panel_count=1` 表示一张成图只有一个独立数据视图，colorbar、legend 不计入；双 Y 轴若仍表达同一坐标域中的一个联合视图可保持 `panel_count=1`；`panel_count>1` 表示 (a)(b)(c)、hero/support、并排、网格面板或 inset 等两个以上独立数据视图。

- `默认（模型自行判断）`：单图优先，不为了“高级感”拼多面板；多面板必须写明语义理由，互相独立的结论拆图。
- `少用子图`：最终入文多面板 Python 图最多 4 张，其余必须单 panel；原模板天然多面板时优先换等价单图，没有等价单图就拆为多张顺序编号的独立图，不允许为了 `figure_total` 硬拼。只有 `项目状态.json` 同时存在 `subplot_sparse_max`（非负整数）与 `subplot_sparse_override_request`（用户原话）两字段时才按该整数放宽；自然语言子串（含否定句“不允许放宽”）不构成授权，`user_notes` 不再被检查器推断。
- `禁用子图`
- 图型重复策略按 `python_chart_repeat_policy` 执行：先依据数据与问题语义选图，再考虑已用图型，不得画完后大批无理由重画。归并口径：折线族（multi_line/line_band/收敛折线/带点折线+置信带）= `line_2d`；一行列与矩阵热图同族 = `heatmap_2d`；棒棒糖/tornado 长度编码 = `bar_2d`；区间点图带误差线 = `scatter_2d`；CCDF/分布曲线 = `distribution_2d`；等值线填充 = `contour_2d`；quiver/streamplot = `vector_2d`；网络结构 = `network_2d`。manifest 图项用 `panel_chart_types` 二维数组登记（外层=panel_count，图例/装饰轴为空列表），未改绘模板可用注册表默认推导；同图多格式导出与重复引用只算一张；同 source 多图分别计数；流程图与非数据图不参与统计。换颜色、标题或模板名不算新类型。
：所有最终入文 Python 图 `panel_count=1`；禁止 hero/support、多行多列 panel、inset 与 `compose_multi_panel`；需要展示多种结果时拆为 `图N`、`图N+1` 独立输出；colorbar 与 legend 保留。

拆分多面板时不得改变数据、结论与同一方法的颜色语义；manifest 条目必须记录真实 `panel_count`。

## 快速否决规则

遇到以下情况，先排除普通一维、二维柱状图：

- 类别超过 4 个
- 需要展示排序而不是绝对高度
- 需要表现误差区间
- 需要表达过程变化
- 需要表达两目标权衡
- 需要表达网络或空间结构
- 需要表达网络几何、多尺度社区或时序网络
- 需要同时保留空间位置和网络关系
