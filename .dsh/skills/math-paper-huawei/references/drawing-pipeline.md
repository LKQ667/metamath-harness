# 三绘图链路

## 重画终止条件（全链路统一）

所有绘图链路共用同一停止判据，避免“图已合格仍被反复重画”：

1. 硬 QA 全部通过且没有明确事实错误时，立即标记 `paper_ready=true` 并冻结，不得因为“也许还能更漂亮”再次整图重画。
2. 只有存在明确缺陷才进入修复，每次修复必须对应一个具体缺陷（重叠、文字过小、越界裁切、坐标或题意错误、数据不一致等）。
3. 同一根因最多 3 轮，每轮必须产生针对该缺陷的状态变化；无状态变化立即停止重复并切换策略或模式。
4. 纯审美型改进只允许一次局部调整，不得触发无界“再高级一点”循环。
5. 新候选只有在硬 QA 不低于当前已合格版本时才替换正式产物；禁止把已合格图覆盖成更差版本。
6. AI 付费生图同样遵守合格即停：已合格时不得重复调用计费接口。

## 做题前选路

每个项目在正式做题前必须询问一次并只接受以下三个选项：`Draw.io 绘图`、`HTML 矢量成图`、`AI 全自动绘图`（卡片 `drawing_mode` 选项 `Draw.io成图+AI概念提示词`/`Draw.io成图` 对应 `drawio`，`HTML矢量成图` 对应 `html`，`AI全自动绘图` 对应 `ai`）。选择后立即写入项目根目录 `项目状态.json` 和 `figures/manifest.json` 顶层，至少包含：

```json
{
  "drawing_mode": "drawio",
  "drawing_mode_locked": true,
  "drawing_mode_confirmed": true
}
```

`drawing_mode` 取值只能是 `drawio`、`html`、`ai` 之一。旧项目缺少记录时必须补问，不得根据现有文件推断。两处记录不一致、未确认、未锁定或非数据绘图混用模式时，停止执行。Python 数据图始终沿用既有链路，不参与选路。

## 统一 manifest

manifest 使用对象顶层和 `items` 列表。每个非数据绘图条目都显式提供 `generator`、`template_id`、`source`、`exports`、`prompt_source`、`paper_ready`、`export_status`、`needs_visual_review`、`qa`。数据图可继续保留既有字段。

## Draw.io 模式

1. 只自动生成流程图、问题分析流程图和技术路线图。原理图、模型图、概念图、示意图只生成 2–4 份提示词，不自动生图。
2. 先运行 `scripts/drawing/drawio_pipeline.py verify-cli`。CLI 缺失时，自动安装按官方 winget 包 `JGraph.Draw`、官方 `jgraph/drawio-desktop` 便携版的顺序执行；便携目录必须由项目明确提供。
3. 版本调用、最小 XML、PNG/SVG/PDF 导出和中文字体渲染必须全部通过，并将含版本文本与可执行文件 SHA-256 的 JSON 输出保存为 `检查结果/drawio_cli_verification.json`。交付检查只比对记录和文件哈希，不执行项目记录指定的任意程序；未通过不得开始正式做题或宣称可用。
4. 先写图稿摘要：对象、动作、产物、判据、节点、边、主路径和未证实内容，并量化结构特征供选择器读取：图型 `kind`（技术路线图必须填 `roadmap`）、反馈回路数 `feedback`、分支数 `branches`、主体数 `actors`、面板数 `panels`、侧标步骤栏 `side_head`、输出横幅 `output_banner`、聚焦主阶段 `focus_stage`、支撑块数 `support_blocks`、阶段数 `stages` 与走向 `direction`。`kind=roadmap` 时只在新四类模板中选路：双面板→双栏双层联动、侧标→侧标步骤栏、横幅→纵向步骤带横幅、默认→三段环抱式，并必须原子执行 `build --brief <brief.json> --labels-json <labels.json> --output <.drawio>`。命令返回的 `template_id` 直接写入 manifest，再执行 `validate <source> --template <id>`；禁止手写 XML、自行命名模板或因英文原型不适配而回退旧模板，内容差异只能用 labels 覆盖，结构指纹或 manifest 不一致时必须重新构建。
5. 固定产物为 `手绘图/<name>.drawio`、2× PNG、SVG、PDF。manifest 记录 `export_scale: 2`；正文插入导出图，保留可编辑源。
6. 静态检查覆盖 XML、唯一 ID、端点、中文字体、正交路由和节点重叠；视觉 QA 覆盖内容、中文、裁切、文字适配、箭头穿模、灰度、单栏/双栏缩印和论文回填。至少两轮，最多三轮。
7. 十类原创模板位于 `assets/drawio/template_library.json`：横向阶段链、纵向分层链、主链加支撑块、双泳道、分支决策、反馈闭环、双栏双层联动、三段环抱式、侧标步骤栏、纵向步骤带横幅。后四类为用户原版直录（raw 通道）：样式、坐标、悬浮边与航点逐点取自原图并保留英文原文；`labels` 键即节点/边 id（建议覆盖全部文字节点），中文值自动补 Microsoft YaHei；侧标步骤栏与纵向步骤带横幅为纵向构图，适合整页/单栏；允许容器/分区嵌套内容节点（完全嵌套合法，部分相交仍报错）。选路优先级为双面板（panels）、侧标步骤（side_head）、输出横幅（output_banner）、聚焦主阶段（focus_stage）、反馈、分支、多主体、支撑块、纵向多阶段、默认横向阶段链。

## AI 全自动模式

1. 保留 2–4 份原理/模型/概念/示意图提示词，每份提示词立即调用当前环境可用的 `imagegen`/Image Gen 生成且只生成一张候选图，不等待二次同意。
2. 另生成至少一张流程图或技术路线图；其提示词和成图不占上述 2–4 张概念类配额。
3. 每份 `手绘图/*.md` 必须与 manifest 中一个且仅一个 AI 条目对应。生成器、提示词源、成图、文件尺寸和 QA 必须可追溯。
4. AI 图必须是可严格解码的 PNG，尺寸不低于 1200×800；内容一致性、中文文字、符号公式、裁切、清晰度、单/双栏缩印和正文回填全部通过。
5. 生图能力不可用或重试后仍不合格时硬阻断交付，不允许以“仅提示词”宣称完成。

## HTML 矢量成图模式

1. 自动生成范围与 Draw.io 模式一致：只自动生成流程图、问题分析流程图和技术路线图；原理图、模型图、概念图、示意图只生成 2–4 份提示词，不自动生图。概念类提示词目录与口径与 Draw.io 模式相同（`手绘图/*.md`）。
2. 出图前先探测 Electron：`python "<技能目录>/assets/html-figure/tools/screenshot_capture.py" --check`（退出码 0=可用，2=不可用）。Electron/node 不可用时自动退回 Draw.io 模式并在 manifest 记录 `html_engine_unavailable` 原因，不重复追问、不伪造产物。
3. 引擎与手册整体内置在本技能 `assets/html-figure/`（`tools/` 出图与质检脚本、`tools/katex-assets/` 公式渲染素材、`templates/` 兜底模板），运行时只读取本技能内置资源，禁止读取外部 `html-paper-figure` 目录。完整工作流与设计规范见 `references/html-figure-engine.md`。
4. 固定产物为 `手绘图/<name>.html`（可追溯源，flex/grid 相对布局单文件）、`手绘图/<name>.pdf`（Electron printToPDF 矢量单页无白边，正文 `\includegraphics` 引用）、`手绘图/<name>.png`（以 192/72 倍率≈2× 从 PDF 渲染的交付 PNG）。不产出 SVG；`.drawio` 源不得出现在 HTML 模式的 `手绘图/` 中。
5. 技术路线图不使用 Draw.io 模板库，改用引擎骨架池按项目根目录名哈希出的 `SKELETON` 种子确定性选择，`template_id` 必须记录为 `skeleton_swimlane`/`skeleton_spine`/`skeleton_twocolumn`/`skeleton_layered` 之一；其余图 `template_id` 记录所用骨架/范式且非空。禁止手写绝对坐标布局。
6. manifest 条目九字段与 Draw.io 模式同构：`generator: "html"`、`source` 指向 `手绘图/<name>.html`、`exports` 必须包含 `.pdf` 与 `.png`、`export_status: "electron_printed"`、`prompt_source` 指向该图图稿摘要、`paper_ready: true`、`needs_visual_review: false`（复核后）、`qa` 键集为 `html_pdf_check_ok`、`geom_check_ok`、`content_ok`、`cn_text_ok`、`layout_ok`、`text_fit_ok`、`grayscale_ok`、`single_column_ok`、`double_column_ok`、`paper_insert_ok`。
7. QA 链：逐张 `html_pdf_check.py`（单页/矢量/裁切/宽高比，FAIL 必修）→ `--geom-check` 元素级几何自检（溢出/越界/重叠/对齐偏差，必修，最多 3 轮）→ 运行时原生视觉复核（不阻塞，须留 passed/unresolved/skipped 记账）→ 单/双栏缩印与论文回填检查。图内不放标题，标题由 LaTeX `\caption{}` 管理；含公式的图节点内写 `\(...\)`/`\[...\]` 并以 `--render-math` 渲染。
8. 每张 PDF 必须在 `论文/main.tex` 用 `\includegraphics{手绘图/<name>.pdf}` 正式入文，回填后运行 `fig_include_size.py --figdir 手绘图 --latex 论文/main.tex` 按真实长宽比规整宽度。

## 内置与许可

运行时只读取当前技能自身的 `assets/drawio/`、`assets/html-figure/`、`scripts/drawing/` 和本引用文件，不调用 `math-paper-cn-drawio`，也不调用外部 `html-paper-figure` 目录（HTML 引擎已整体并入 `assets/html-figure/`）。第三方候选仓库的来源、SPDX 许可证和蒸馏边界见 `assets/drawio/UPSTREAM.md`；内置模板为原创结构，不复制第三方资产，也不虚称期刊官方模板。
