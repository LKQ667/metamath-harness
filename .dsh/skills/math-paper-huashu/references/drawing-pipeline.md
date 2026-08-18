# 双绘图链路

## 做题前选路

每个项目在正式做题前必须询问一次并只接受以下两个选项：`Draw.io 绘图`、`AI 全自动绘图`。选择后立即写入项目根目录 `项目状态.json` 和 `figures/manifest.json` 顶层，至少包含：

```json
{
  "drawing_mode": "drawio",
  "drawing_mode_locked": true,
  "drawing_mode_confirmed": true
}
```

旧项目缺少记录时必须补问，不得根据现有文件推断。两处记录不一致、未确认、未锁定或非数据绘图混用模式时，停止执行。Python 数据图始终沿用既有链路，不参与选路。

## 统一 manifest

manifest 使用对象顶层和 `items` 列表。每个非数据绘图条目都显式提供 `generator`、`template_id`、`source`、`exports`、`prompt_source`、`paper_ready`、`export_status`、`needs_visual_review`、`qa`。数据图可继续保留既有字段。

## Draw.io 模式

1. 只自动生成流程图、问题分析流程图和技术路线图。原理图、模型图、概念图、示意图只生成 2–4 份提示词，不自动生图。
2. 先运行 `scripts/drawing/drawio_pipeline.py verify-cli`。CLI 缺失时，自动安装按官方 winget 包 `JGraph.Draw`、官方 `jgraph/drawio-desktop` 便携版的顺序执行；便携目录必须由项目明确提供。
3. 版本调用、最小 XML、PNG/SVG/PDF 导出和中文字体渲染必须全部通过，并将含版本文本与可执行文件 SHA-256 的 JSON 输出保存为 `检查结果/drawio_cli_verification.json`。交付检查只比对记录和文件哈希，不执行项目记录指定的任意程序；未通过不得开始正式做题或宣称可用。
4. 先写图稿摘要：对象、动作、产物、判据、节点、边、主路径、分支、反馈、阶段、主体和未证实内容。调用模板选择器后只替换内容与必要布局。
5. 固定产物为 `手绘图/<name>.drawio`、2× PNG、SVG、PDF。manifest 记录 `export_scale: 2`；正文插入导出图，保留可编辑源。
6. 静态检查覆盖 XML、唯一 ID、端点、中文字体、正交路由和节点重叠；视觉 QA 覆盖内容、中文、裁切、文字适配、箭头穿模、灰度、单栏/双栏缩印和论文回填。至少两轮，最多三轮。
7. 十类原创模板位于 `assets/drawio/template_library.json`：横向阶段链、纵向分层链、主链加支撑块、双泳道、分支决策、反馈闭环、双栏双层联动、三段环抱式、侧标步骤栏、纵向步骤带横幅。后四类引入 container（虚线容器）、zone（底色分区）、action（实色按钮条）、caption（无框标题）四种新角色，允许容器/分区嵌套内容节点（完全嵌套合法，部分相交仍报错）。选路优先级为反馈、分支、多主体、双面板（panels）、侧标步骤（side_head）、输出横幅（output_banner）、聚焦主阶段（focus_stage）、支撑块、纵向多阶段、默认横向阶段链。

## AI 全自动模式

1. 保留 2–4 份原理/模型/概念/示意图提示词，每份提示词立即调用当前环境可用的 `imagegen`/Image Gen 生成且只生成一张候选图，不等待二次同意。
2. 另生成至少一张流程图或技术路线图；其提示词和成图不占上述 2–4 张概念类配额。
3. 每份 `手绘图/*.md` 必须与 manifest 中一个且仅一个 AI 条目对应。生成器、提示词源、成图、文件尺寸和 QA 必须可追溯。
4. AI 图必须是可严格解码的 PNG，尺寸不低于 1200×800；内容一致性、中文文字、符号公式、裁切、清晰度、单/双栏缩印和正文回填全部通过。
5. 生图能力不可用或重试后仍不合格时硬阻断交付，不允许以“仅提示词”宣称完成。

## 内置与许可

运行时只读取当前技能自身的 `assets/drawio/`、`scripts/drawing/` 和本引用文件，不调用 `math-paper-cn-drawio`。第三方候选仓库的来源、SPDX 许可证和蒸馏边界见 `assets/drawio/UPSTREAM.md`；内置模板为原创结构，不复制第三方资产，也不虚称期刊官方模板。
