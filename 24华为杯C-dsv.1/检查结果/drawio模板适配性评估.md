# Draw.io 内置模板适配性评估（用于说明未自动切换绘图模式的原因）

本文件记录对「自动退回 Draw.io 成图」这一备选通道的实测评估结论，供授权决策参考。

## 一、评估对象

依据 `references/drawing-pipeline.md`，技术路线图在 Draw.io 模式下只能从内置四类 raw 模板中选择：
`stage-blocks-l`、`stepwise-sidehead`、`steps-stacked-banner`、`dual-panel-bilevel`。
`choose_template()` 对 `kind="roadmap"` 强制走这四类，其余六类模板（如 `horizontal-stage-chain`、`feedback-loop`）不可用于技术路线图；`check_drawing_contract` 会校验技术路线图的 `template_id` 属于这四类并比对结构指纹。

## 二、四个模板的实际内容（读自 `assets/drawio/template_library.json`）

| 模板 | 节点数 | 文本节点特征 | 与本题的语义匹配 |
|---|---|---|---|
| `stage-blocks-l` | 60+ | 含 2 处 base64 内嵌照片（风电场）、"L2O Learning Framework"、负荷列点阵 | 电力系统图，结构不可改动 |
| `stepwise-sidehead` | 70 | "Meteorology/Topography/…"、"5m×5m…1000m×1000m" 的 5×5 空格网格、kWh/m² 图例 | GIS 适宜性评价图 |
| `steps-stacked-banner` | 101 | eQUEST/SAM 标志、"PV/WT/Battery/Inverter" 能源系统拓扑、☀ 图标 | 综合能源系统图 |
| `dual-panel-bilevel` | 74 | "ISO"、"Day-ahead Scale"、风电/光伏预测、产消者双层优化 | 电力市场双层优化图 |

## 三、结论

1. 结构指纹门禁只允许替换文字（`labels`），不允许增删节点、改坐标或改样式；因此上述电力/GIS 语义的几何结构会被原样保留。
2. 四个模板均含大量与本题无关的可见元素：内嵌照片、能源设备拓扑、5×5 空格网格、外部软件标志、kWh/m² 数值图例。仅替换文字无法消除这些元素。
3. 若只替换部分文字，未覆盖节点会保留英文原文，论文将出现中英混排且语义错位的技术路线图；若逐一替换全部文字节点，图的视觉结构仍与"数据解析—模型构建—求解验证—结果决策"的种植规划路线不符。
4. 因此本通道虽能通过 `check_roadmap_quality_notes`，但会显著降低论文图件的科学可用性，属于以形式合规换取内容失真，故未在未获授权的情况下自动切换。

## 四、现有 HTML 矢量流程类图的实际质量证据

`手绘图/fig03_analysis.pdf`、`fig04_roadmap.pdf`、`fig05_framework.pdf` 三张图均已通过：
单页矢量检查（`html_pdf_check`，宽高比 2.47:1—3.44:1）、元素级几何自检（溢出/越界/重叠/对齐偏差均为 0）、中文渲染检查、2× PNG 交付与论文回填检查；其内容为本题特有的阶段、方法与判据实体，无英文混排与无关元素。
