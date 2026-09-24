# AGENT.md：项目规则与阶段状态

本文件是项目的规则与进度真相源，供后续任何一次接手（人或程序）快速恢复上下文。

## 一、铁规

- **禁止编造**：不得编造、估计、外推任何未真实计算出的数据、指标、图表与结论；
  论文中出现的每个数值都必须能追溯到 `results/final_results.json` 或对应脚本的真实输出文件。
- **禁止篡改**：不得修改、替换、增删赛题提供的样本与标签；不得为了好看而改写计算结果、
  图像数据或实验记录；不得伪造门禁报告、交付凭证与自查结论。
- **数据来源**：所有数据必须登记在 `data/source_map.md`，所有文献必须登记在 `文献/source_map.md`；
  未登记来源的数据不得进入建模、图表或正文。赛题明确规定以 CMU-MOSEI 系列数据为唯一数据来源，
  本项目不引入任何外部数据集与外部预训练模型权重。
- **唯一结果源**：`results/final_results.json` 是全文唯一最终数值结果源，禁止保留互相冲突的多套结果。
- **图像冻结**：图片硬 QA 全部通过且无事实错误时立即标记 `paper_ready=true` 并冻结；
  重画必须对应一个具体缺陷，同一根因最多 3 轮，无状态变化立即切换策略。
- **柱状图零例外**：`bar_policy=禁用`，源码中不得出现 bar / barh / broken_barh / barplot /
  mark_bar / vbar / hbar 及 `kind="bar"`；区间与时间信息用线段与端点标记表达。

## 二、锁定配置

| 配置项 | 值 | 来源 |
|---|---|---|
| drawing_mode | ai | 卡片 |
| bar_policy | 禁用 | 卡片 |
| subplot_policy | 少用子图 | 卡片 |
| python_chart_repeat_policy | 默认（少重复） | 卡片（冲突已记录，见 `项目状态.json`） |
| three_d_preference | 优先考虑 | 卡片 |
| figure_total | 20 | 卡片 |
| body_pages | 29 | 卡片 |
| competition_language | 中文 | 卡片 |
| reference_excellent_papers | true | 卡片 |
| ai_image_limit | 4 | 卡片 |

## 三、阶段状态自动更新区

| 阶段 | 状态 | 产物 | 门禁报告 |
|---|---|---|---|
| step0 项目初始化与资料收集 | 已通过 | README.md、AGENT.md、data/source_map.md、文献/source_map.md、figures/manifest.json、项目状态.json | 检查结果/step0/step0_gate.json |
| step1 引入与数据预处理 | 已通过 | 数据预处理/README.md、data/processed/*、EDA 图 | 检查结果/step1/step1_gate.json |
| step2 单问分析建模 | 已通过 | Q1/Q2/Q3 的 README.md 与模型说明 | 检查结果/step2/step2_gate.json |
| step3 代码实现 | 已通过 | Qn/*.py、Qn/result.md、Qn/figures/*、results/final_results.json | 检查结果/step3/step3_gate.json |
| step4 论文写作与内容组织 | 已通过 | 论文/main.tex、灵敏度分析/、手绘图/ | 检查结果/step4/step4_gate.json |
| step5 排版编译与最终交付 | 已通过 | 论文/main.pdf、检查结果/三轮自查.md | 检查结果/check_report.json |

（本表在每次门禁通过后同步更新为“已通过”，不留任何未完成状态残留到交付时。）

## 三之二、关键交付指标

| 指标 | 实测值 |
|---|---|
| 论文总页数 | 62 页（正文 33 页 + 附录 29 页） |
| 正文页数 | 33 页（正文起始页 1、结束页 33） |
| 摘要页跨度 | 2 页（abstract:start 第 1 页、abstract:end 第 2 页） |
| 入文图片总数 | 20 张（16 张 Python 数据图 + 4 张 AI 非数据图） |
| 多面板 Python 图 | 4 张（符合少用子图上限） |
| 参考文献条目 | 26 条，全部带 DOI 或 URL |
| 附录代码文件 | 4 个核心脚本的等价净化副本 |
| 最终交付凭证 | 检查结果/delivery_attestation.json |

## 四、目录职责

- `赛题/`：题目文档与四个官方附件（只读，不得修改）
- `文献/`：文献清单、阅读笔记与来源映射
- `data/`：原始数据副本、派生数据与 `source_map.md`
- `数据预处理/`：EDA 脚本、清洗规则与预处理说明
- `Q1/` `Q2/` `Q3/`：逐问模型说明、主脚本、结果与图片
- `灵敏度分析/`：参数扫描与敏感度分析脚本与图
- `手绘图/`：AI 概念提示词与成图（非数据绘图链路）
- `摘要/`：摘要与摘要素材
- `论文/`：LaTeX 源码、附录净化代码、最终 PDF
- `results/`：唯一结果源
- `figures/`：论文汇总图清单与统一 manifest
- `检查结果/`：各阶段门禁报告与三轮自查
- `截图/`：优秀论文视觉校准证据（绝不入文，也不进参考文献）
- `scripts/`：共享工具、总控脚本与门禁入口

## 五、写作与排版约束摘要

- 正文主结构固定为：一、问题重述；二、模型假设与符号说明（依次为模型假设、符号说明）；
  随后按实际问数依次为“问题一至问题 N 模型建立与求解”；末尾为模型总结与评价；参考文献用
  `thebibliography`；正文禁止新增主章节。
- 符号说明：模型假设 → 符号说明标题 → 符号表 → 问题一主章节，符号表用非浮动 tabularx/longtable，
  不加 caption、不占正式表格编号。
- 摘要与关键词合计不超过两页，摘要有效文字不少于 800 字（建议 850–1050 字），
  `\label{abstract:start}` 紧跟 `\begin{abstract}`，`\label{abstract:end}` 位于 `\keywords{}` 之后。
- 正文禁止 `•`、`☐` 与原始中点 `·`；数学乘法用 `\cdot`；禁止机械连接词“首先、其次、然后、接着”；
  括号密度每千字不超过 4 组；引用使用右上角数字角标。
- 图表全篇连续编号（图1、图2…；表1、表2…），图题在下、表题在上，解释段落紧跟对象之后。
- 附录另起一页，先数据附录后代码附录；附录代码为等价净化副本（无注释、无 docstring、无格式符号）。
