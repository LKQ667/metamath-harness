---
name: math-paper-cn-drawio
description: 为中文数学建模竞赛论文创建、修复和验收可编辑 draw.io 图，包括技术路线图、问题分析图、模型机制图、求解流程图、评价与因果结构图。用户提到数学建模论文、draw.io、流程图、技术路线、模型框架、论文配图、中文顶刊/国一风格，或要求避免中文乱码、重叠、箭头错位、逻辑错误、导出 PNG/SVG/PDF 时使用。
---

# 数学建模 draw.io 绘图

目标是交付可编辑、可复现、可缩印入文的中文论文图，而非仅产出“能打开的 XML”。默认输出 `.drawio` + SVG + PNG，并以可验证的逻辑、布局和渲染三重质量门禁阻止乱码、重叠、错连和箭头穿模。

## 先判图，再作图

1. 从题目/论文抽取 **对象—动作—产物—判据**；不确定的因果、数据来源或结论不能画成既定关系。
2. 每张图只回答一个问题：总体路线、单问求解、机制关系、评价闭环或跨角色协作。复杂内容拆成“主链 + 右侧/下方支撑块”，不要压成一张密集总图。
3. 选择阅读方向：阶段型默认左→右；层级/反馈型默认上→下；只有“阶段 × 执行主体”同时重要时才用泳道。
4. 先写 `references/diagram-brief.md` 的图稿摘要，再生成 XML。摘要必须列出：节点、边、边的含义、主阅读路径、分支条件、未证实内容，并量化结构特征（反馈、分支、主体、支撑块、阶段数与走向）以按优先级选定布局原型。

## 生成

- 技术路线图必须把 brief 的 `kind` 设为 `roadmap`，并使用 `scripts/drawing/drawio_pipeline.py build --brief ... --labels-json ... --output ...` 原子生成；它不属于可手写 XML 的非标准图。禁止因模板原型含英文、主题不同或审美判断而回退旧模板；只能用 labels 替换内容。manifest 的 `template_id` 必须取自命令输出，并通过 `validate <source> --template <id>` 的结构指纹检查。
- 优先使用 `scripts/build_drawio_diagram.py` 生成标准流程图；它会进行字符转义、唯一 ID、统一字体、网格布局、端口分配和安全间距。对于非标准图，也必须遵循其输出的 XML 约定。
- 样式使用 `styles/guoyi-cn.json`：白底、低饱和语义色、深色正文、统一圆角、无渐变/阴影/发光。视觉语义与顶刊规则见 `references/top-journal-drawio-style.md`。
- 中文字体使用 `Microsoft YaHei, SimSun, Arial Unicode MS`；每个有文字的节点都要带 `html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;`。标签短句化，通常 4–12 个汉字；严禁未转义的 `& < > "`。
- 边统一使用正交线与实心经典箭头。一个节点只有一条主入/出边时使用中心端口；多分支时显式分配不同的 `exitX/exitY/entryX/entryY`，分支标签只写在边上。
- 保持：节点之间至少 70 px、容器内边距至少 30 px、边标签与节点至少 20 px。禁止交叉箭头、边穿过无关节点、边标签覆盖节点、依赖仅靠颜色表达。

## 渲染与三重验收

1. 执行静态验收：`python scripts/validate_drawio_project.py --project <项目根目录> --strict`。修复所有错误；警告必须有明确理由才可保留。
2. 找到 draw.io Desktop 后导出无嵌入预览：`draw.io --export --format png --scale 2 --output <预览.png> <源.drawio>`。Windows 依次尝试 `drawio`、`draw.io`、`C:\Program Files\draw.io\draw.io.exe`。没有 CLI 时，绝不伪称已经渲染通过。
3. 对预览做视觉验收：中文是否显示正常、文字是否截断、节点/边/箭头是否重叠或穿模、阅读方向是否唯一、颜色在灰度下是否仍能区分。修复后重新静态验收和渲染；至少两轮，最多三轮。最终再导出 SVG 和 2× PNG；若需要嵌入可编辑 PNG，单独导出并用严格 PNG 解码器复验。

仅当 `.drawio` 源文件、至少一个有效 SVG/PNG、manifest、两轮验收均通过时，`paper_ready` 才能为 `true`。CLI 或字体不可用时，设 `paper_ready: false` 和 `needs_visual_review: true`。

## 项目接口

默认相对项目根目录输出：

- 源：`手绘图/<name>.drawio`
- 导出：`手绘图/<name>.svg` 与 `手绘图/<name>.png`
- 清单：`figures/manifest.json`

manifest 条目至少包含 `id`、`title`、`purpose`、`section`、`source`、`exports`、`paper_ready`、`checks`、`export_status`、`needs_visual_review`。完成时报告源文件、导出文件、校验命令及两轮结果。

## 资源导航

| 需要 | 读取/执行 |
|---|---|
| 图稿逻辑与提示词 | `references/diagram-brief.md` |
| 顶刊视觉与布局 | `references/top-journal-drawio-style.md` |
| XML、端口与路由 | `references/xml-guide.md` |
| 常用数模图型 | `references/modeling-templates.md` |
| 十类模板选路与流程 | `references/drawing-pipeline.md` |
| 十类模板生成/选路/校验 | `scripts/drawing/drawio_pipeline.py --help` |
| 生成标准流程图 | `scripts/build_drawio_diagram.py --help` |
| 静态/导出验收 | `scripts/validate_drawio_project.py --help` |
| 技能回归测试 | `scripts/run_smoke_tests.py` |
| 分支箭头视觉回归 | `scripts/create_branch_qa_project.py` |

## 失败处理

- 逻辑缺口：在图稿摘要中以“待确认”保留，不能凭空补箭头或结论。
- 校验错误：先改源 `.drawio`，再重新导出；不直接修图掩盖源文件错误。
- CLI 缺失：保留源文件、记录 `cli_missing`，交付时明确要求在 draw.io Desktop/diagrams.net 做视觉复验。
- 有乱码、重叠、错连、穿模、截断、缺失导出或 manifest 失配：不得入论文。
