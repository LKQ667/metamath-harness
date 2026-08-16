# 10 篇 Nature 系参考论文蒸馏

本文件服务于 `Py-Nature` 的风格蒸馏，不做逐图复刻，只提炼对数学建模绘图有价值的配色、布局与图型组合习惯。

原始论文只保存在维护者获授权的私有资料库中，不随 Skill 分发。
学习索引与截图蒸馏结论已经抽象到本目录的规则文件；运行时不依赖外部绝对路径。

## 1. Efficient and scalable reinforcement learning for large-scale network control

- 期刊：Nature Machine Intelligence
- 主题：大规模网络控制、强化学习、复杂系统
- 对 Py-Nature 的启发：
  - 网络拓扑图与性能曲线应成对出现
  - 结构图负责“系统场景”，曲线图负责“量化效果”
  - 适合沉淀为 `network_resilience_template.py` 与 `multi_panel_hero_support_template.py`

## 2. Deep learning of causal structures in high dimensions under data limitations

- 期刊：Nature Machine Intelligence
- 主题：高维因果结构、受限数据学习
- 对 Py-Nature 的启发：
  - 高维结构类任务更适合 `heatmap / network / interval` 组合
  - 避免用大堆柱图表达结构差异
  - 配色应冷静、层级清晰

## 3. Data-driven discovery of intrinsic dynamics

- 期刊：Nature Machine Intelligence
- 主题：动力学发现、数据驱动模型
- 对 Py-Nature 的启发：
  - 数学建模中的动力系统适合 `phase portrait + trajectory`
  - 机制解释图不应太装饰化，重点是状态空间关系
  - 可沉淀到 `dynamics_phase_portrait_template.py`

## 4. Learning dominant physical processes with data-driven balance models

- 期刊：Nature Communications
- 主题：物理过程学习、平衡模型、空间场
- 对 Py-Nature 的启发：
  - 空间连续场优先 `contour / heatmap / quiver`
  - 物理意义强的图要体现方向、梯度和区域差异
  - 可沉淀到 `spatial_contour_flow_template.py`

## 5. Bond percolation in coloured and multiplex networks

- 期刊：Nature Communications
- 主题：多层网络、渗流、鲁棒性
- 对 Py-Nature 的启发：
  - 网络模型常需要 `结构示意 + 渗流阈值曲线`
  - 图上应体现临界点，而不是只给最终结果
  - 适合用 `line + annotation` 强调突变点

## 6. Unfolding the multiscale structure of networks with dynamical Ollivier-Ricci curvature

- 期刊：Nature Communications
- 主题：网络几何、多尺度社区、曲率
- 对 Py-Nature 的启发：
  - 网络主图可用连续色带表现曲率或瓶颈程度
  - 主网络图旁边应配时间尺度或稳定性支撑曲线
  - 适合沉淀为 `network_curvature_multiscale_template.py`

## 7. Global labor flow network reveals the hierarchical organization and dynamics of geo-industrial clusters

- 期刊：Nature Communications
- 主题：劳动力流动网络、层级结构、地理产业簇
- 对 Py-Nature 的启发：
  - 地理图、网络图和排名图可以共用一套层级配色
  - hero panel 适合放地理网络全局视图
  - 支撑 panel 用排序和趋势，而不是多张柱图

## 8. Spatiotemporal data analysis with chronological networks

- 期刊：Nature Communications
- 主题：时空数据、Chronnet、网格时序网络
- 对 Py-Nature 的启发：
  - 时空建模图应把空间网格和时间先后关系放在同一模板里
  - 需要 `map/grid + network + summary` 的成套视图
  - 适合沉淀为 `spatiotemporal_chronological_network_template.py`

## 9. Robust dynamic community detection with applications to human brain functional networks

- 期刊：Nature Communications
- 主题：动态社区、脑功能网络、时序社群
- 对 Py-Nature 的启发：
  - 动态社区属于 `temporal network`，不应退化成普通静态网络
  - 群组颜色需沿时间窗保持一致
  - 结构图和热图/时间轴图适合并列出现

## 10. Constructing temporal networks with bursty activity patterns

- 期刊：Nature Communications
- 主题：时间网络、突发活动、重尾间隔
- 对 Py-Nature 的启发：
  - 时间网络优先 `timeline + distribution + summary`
  - 用折线、CCDF、事件列线表达突发性，比柱图更适合
  - 适合沉淀为 `temporal_bursty_activity_template.py`

## 综合结论

- 数学建模论文图最有价值的组合，不是“单一漂亮图”，而是：
  - `结构/机制 + 定量对比`
  - `过程变化 + 关键阈值`
  - `空间/网络结构 + 统计总结`
- 从 10 轮截图蒸馏得到的新增硬规则：
  - `network curvature`、`temporal burst`、`spatiotemporal network` 独立成图型分支
  - 同一方法跨 panel 不换色，同一色条在不同 panel 不改语义
  - 图例复杂时优先独立 panel，不把图例压在网络和空间主图上
- 因此 `Py-Nature` 的默认多面板逻辑是：
  - 一个 hero panel 交代对象或机制
  - 两到四个 supporting panels 给出趋势、区间、敏感性或优化证据
