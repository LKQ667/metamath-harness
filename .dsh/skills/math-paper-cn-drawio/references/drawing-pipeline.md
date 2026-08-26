# 十类模板链路

## 适用范围

十类模板链路适用于流程图、问题分析流程图和技术路线图；原理图、模型图、概念图、示意图仍按 `diagram-brief.md` + `build_drawio_diagram.py`/手写 XML 既有链路。两条链路并存，manifest 的 `generator` 字段记录实际生成器。

## 使用流程

1. 先写图稿摘要：对象、动作、产物、判据、节点、边、主路径和未证实内容，并量化结构特征供选择器读取：图型 `kind`（技术路线图必须填 `roadmap`）、反馈回路数 `feedback`、分支数 `branches`、主体数 `actors`、面板数 `panels`、侧标步骤栏 `side_head`、输出横幅 `output_banner`、聚焦主阶段 `focus_stage`、支撑块数 `support_blocks`、阶段数 `stages` 与走向 `direction`。`kind=roadmap` 时只在新四类模板中选路，默认三段环抱式。
2. 技术路线图必须原子执行 `python scripts/drawing/drawio_pipeline.py build --brief <brief.json> --labels-json <labels.json> --output <.drawio>`，由程序完成选择与构建；其他图型可继续使用 `select` 和 `build --template`。
3. 生成后用命令返回的 `template_id` 写入 manifest，并执行 `validate <source> --template <id>`。技术路线图不得手写 XML、不得自行命名模板，也不得因原型英文或主题差异回退旧模板；内容差异只能通过 `labels-json` 覆盖。模板结构或 manifest 不一致时必须重新构建。
4. 渲染验收沿用本技能三重验收：静态验收 + CLI 导出 + 视觉验收，至少两轮。

## 十类模板与选路

十类原创模板位于 `assets/drawio/template_library.json`：横向阶段链、纵向分层链、主链加支撑块、双泳道、分支决策、反馈闭环、双栏双层联动、三段环抱式、侧标步骤栏、纵向步骤带横幅。后四类为用户原版直录（raw 通道）：样式、坐标、悬浮边与航点逐点取自原图并保留英文原文；`labels` 键即节点/边 id（建议覆盖全部文字节点），中文值自动补 Microsoft YaHei；侧标步骤栏与纵向步骤带横幅为纵向构图，适合整页/单栏；允许容器/分区嵌套内容节点（完全嵌套合法，部分相交仍报错）。选路优先级为双面板（panels）、侧标步骤（side_head）、输出横幅（output_banner）、聚焦主阶段（focus_stage）、反馈、分支、多主体、支撑块、纵向多阶段、默认横向阶段链。
