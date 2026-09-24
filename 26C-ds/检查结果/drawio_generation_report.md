# Draw.io 非数据图生成报告（12 张）

- 项目：`F:\26华为杯\26C-ds`
- 绘图模式：`drawio`（`项目状态.json` 与 `figures/manifest.json` 顶层均已锁定）
- 生成链路：仅使用 `math-paper-huawei` 技能的 `scripts/drawing/drawio_pipeline.py` 与 `assets/drawio/template_library.json`，未读取任何外部绘图技能目录
- 生成方式：全部经 `build --brief <brief.json> --labels-json <labels.json> --output <.drawio>` 原子生成，随后 `validate <source> --template <id>`；**未手写任何 XML**，**未自造 template_id**，**未回退旧模板**

## 一、交付前自检退出码

| # | 命令 | 退出码 | 结论 |
|---|------|--------|------|
| 1 | `check_figures_manifest.py --project <项目>` | 0 | ok=true，0 条失败 |
| 2 | `check_flowchart_required.py --project <项目>` | 0 | ok=true，0 条失败 |
| 3 | `check_drawing_contract.py --project <项目> --stage step3` | 2 | **该脚本不存在 `--stage` 参数**，argparse 直接报错退出（非内容缺陷） |
| 3b | `check_drawing_contract.py --project <项目>`（去掉不存在的 `--stage`） | 0 | ok=true，0 条失败 |
| 4 | `check_roadmap_quality_notes.py --project <项目>` | 0 | ok=true，0 条失败 |

说明：`check_drawing_contract.py` 只接受 `--project` 与 `--output`。技能注册表 `scripts/checks/gate_registry.py` 把该检查登记在 **step4**（`GateSpec("check_drawing_contract.py", 4)`），而 `check_figures_manifest` / `check_flowchart_required` / `check_roadmap_quality_notes` 登记在 step3。去掉非法参数后，四条检查的命令**全部退出码 0**。

## 二、产物清单

每张图固定四件产物：`.drawio`（可编辑源）、`.svg`、`.pdf`、`.png`（2× 导出，manifest 记录 `export_scale: 2`）。字节数取自交付时刻实际文件。

| 图名 | template_id | PNG 像素 | 宽高比 | .png 字节 | .pdf 字节 | .svg 字节 | .drawio 字节 | 计划章节 |
|------|-------------|----------|--------|-----------|-----------|-----------|--------------|----------|
| `fig_roadmap` | `dual-panel-bilevel` | 1846x1312 | 1.41 | 617,897 | 171,981 | 867,048 | 35,728 | 一、问题重述 |
| `fig_problem_analysis` | `main-chain-support` | 1866x636 | 2.93 | 108,692 | 29,934 | 170,575 | 6,228 | 一、问题重述 |
| `fig_experiment_design` | `dual-swimlane` | 1886x696 | 2.71 | 148,774 | 37,287 | 223,095 | 6,637 | 二、模型假设与符号说明 |
| `fig_artifact_sources` | `main-chain-support` | 1866x636 | 2.93 | 121,791 | 36,874 | 199,961 | 6,425 | 问题一模型建立与求解 |
| `fig_q1_denoise_flow` | `branch-decision` | 1966x686 | 2.87 | 127,860 | 33,362 | 168,095 | 5,028 | 问题一模型建立与求解 |
| `fig_q1_response_flow` | `horizontal-stage-chain` | 2006x146 | 13.74 | 88,337 | 29,992 | 137,026 | 4,335 | 问题一模型建立与求解 |
| `fig_q2_multiscale_model` | `dual-swimlane` | 1886x696 | 2.71 | 202,211 | 39,733 | 341,419 | 6,715 | 问题二模型建立与求解 |
| `fig_q2_laterality_mechanism` | `main-chain-support` | 1866x636 | 2.93 | 114,271 | 32,316 | 169,865 | 6,206 | 问题二模型建立与求解 |
| `fig_q2_feature_flow` | `horizontal-stage-chain` | 2006x146 | 13.74 | 81,940 | 23,823 | 125,420 | 4,339 | 问题二模型建立与求解 |
| `fig_q3_model_framework` | `main-chain-support` | 1866x636 | 2.93 | 135,270 | 33,940 | 202,016 | 6,426 | 问题三模型建立与求解 |
| `fig_q3_estimation_flow` | `horizontal-stage-chain` | 2006x146 | 13.74 | 90,168 | 29,217 | 145,050 | 4,339 | 问题三模型建立与求解 |
| `fig_q3_application` | `main-chain-support` | 1866x636 | 2.93 | 122,968 | 33,003 | 180,007 | 6,399 | 模型总结与评价 |

## 三、问题二多尺度模型图的重绘记录（父 agent 补充要求）

父 agent 指出 `fig_q2_multiscale_model` 原用纵向分层链导出为 526×1346（宽高比 0.39），过于狭长，插入论文后近半页高。已按模板库横向模板重绘：

- 新 `template_id`：**`dual-swimlane`**（横向双泳道）
- 新 PNG 像素：**1886x696**，**宽高比 2.710**（要求 2.2–3.2，满足）
- 内容保持不变：五级串联 `LGN 时空滤波（毫秒级）` → `形状选择与除法归一化（十毫秒级）` → `Wilson–Cowan 介观集群（百毫秒级）` → `Kuramoto 同步与序参数（秒级）` → `头皮导联场观测`，各级时间尺度随节点标注；第 6 个内容框为「尺度跨度：毫秒 → 秒」汇总标注，不新增计算层级
- 仍经 `build --brief ... --labels-json ... --output ...` 原子生成并通过 `validate`；`figures/manifest.json` 中该条目的 `template_id` 已同步更新为 `dual-swimlane`
- 其余 11 张图未改动

候选模板实测宽高比（由模板库节点包围盒计算）：`main-chain-support` 2.95、`dual-swimlane` 2.72、`branch-decision` 2.88 落在 2.2–3.2 区间；`horizontal-stage-chain` 为 14.29（内容框 1000×70，五个节点同排，导出为极扁长条），`vertical-layer-chain` 为 0.39，`feedback-loop` 1.82，均不满足区间。`main-chain-support` 只有 4 个串联主节点、`branch-decision` 为分叉汇合结构，都无法承载「五级串联」；只有 `dual-swimlane` 同时满足宽高比与五级内容，故选用它。

## 四、概念类提示词（4 份，未调用任何付费生图接口）

- `手绘图/概念图_双源认知回路.md`（2,525 字节）
- `手绘图/概念图_多尺度耦合示意.md`（2,369 字节）
- `手绘图/概念图_容积传导观测示意.md`（2,431 字节）
- `手绘图/概念图_形状选择性神经元镜像偏好.md`（2,243 字节）

按 Draw.io 模式规定，原理图/模型图/概念图/示意图只生成提示词、不自动生图；项目 `confirm_paid_calls=false`，全程未调用 `image_generate` 等计费接口。

## 五、QA 记录

### 5.1 静态 QA（`validate` + 自建文本审计）

- XML 可解析、`mxCell` id 唯一、连接边端点存在且带显式箭头、CJK 节点均含 `fontFamily=Microsoft YaHei` 与 `whiteSpace=wrap`、实体内容盒无部分相交（容器完全嵌套合法）
- 模板结构指纹核对：12 张全部 `validate --template <id>` 通过（节点/边集合与端点关系与模板一致）
- 文本审计：163 个文本单元，**0 条问题**（无残留模板英文、无无中文文本单元、无节点汉字数 >16）

### 5.2 视觉 QA（`read_image` 逐张读 2× PNG）

12 张全部逐张读图确认：内容与提纲一致、文字全中文无乱码/无方框问号、无越界裁切、无节点重叠、箭头无穿模、文字适配盒宽、灰度与缩印可读。共两轮，第二轮修复的具体缺陷：

1. **文字与标签重叠**（`fig_roadmap`）：我在悬浮边上追加的 5 个边标签与模板已有的文字节点位置重合，渲染成 `数据交接分段交接`、`特征尺度递进`、`模型判别输出`。处置：清空这 5 个边标签（其信息已由相邻文字节点承载），重叠消除。
2. **边标签压住节点框**（`fig_q3_estimation_flow`）：`按应答正确性` 等边标签宽 90pt，超过横向阶段链 50pt 的节点间距，压到相邻节点框上。处置：清空三张横向阶段链图的冗余边标签，并把其余边标签字号从 15px 收到 12px。
3. **正文宽度下字号偏小**：六类原创模板固定 `fontSize=14`，而图宽约 1000pt，按 `0.98\textwidth` 插入后仅约 6pt。处置：用标签内联 HTML（raw 模板自身使用的写法）把节点字号提到 17px、边标签 12px，插入后约 7.5pt，双栏缩印仍可读。

重绘终止遵循「硬缺陷驱动、合格即冻结」：上述每轮重画均对应一个具体缺陷，同一根因未超过 3 轮；修复后未再以「更漂亮」为由整图重画。

### 5.3 论文回填状态

`qa.paper_insert_ok` 记录的是**入文适配性 QA**（宽高比、2× 分辨率、正文宽度与缩印可读性）已通过。已核实 `论文/main.tex` 用 `\includegraphics[width=0.98\textwidth]{<name>.pdf}` 引用了全部 12 张图的 PDF（其中 12 张 drawio 图均按 0.98\textwidth 插入），`check_drawing_contract` 的独立回填校验（`paper_has`）已通过，故该检查退出码为 0。各条目另记 `paper_insert_status: "backfilled_in_main_tex"`，用于区分「适配性 QA 通过」与「已回填」两件事，避免歧义。

## 六、与任务书字段的偏差说明

| 字段 | 任务书写法 | 实际写入 | 原因 |
|------|------------|----------|------|
| `export_status` | `"exported"` | `"cli_exported"` | `check_drawing_contract.py` 第 265 行硬性要求 Draw.io 条目必须为 `cli_exported`，`exported` 会导致门禁失败；`cli_exported` 同时准确表达「经 CLI 导出」 |
| `qa` 键集 | 13 个键 | 19 个键（并集） | 任务书键集与门禁 `DRAWIO_QA` 键集不同，取并集使两者同时满足 |

## 七、未证实内容与局限

- 图内所有数值（一致率 1.00 与 0.48、相关度 >0.6、幅度 >6 倍、10 倍稳健尺度、80–250 ms / 250–800 ms / 应答前约 100 ms）均取自赛题给定条件与项目已完成结果记录（`检查结果/denoise_final_decision.json`、`denoise_strength_sweep.json`、`laterality_feature_diagnosis.json`），未在图中新增任何未经验证的数值。
- `fig_artifact_sources` 只做定性表现描述：逐类伪迹的出现比例在已完成结果中未量化，故未标注任何比例数值。
- 多尺度模型各级时间尺度为定性量级标注，非拟合结果。
- `fig_q3_application` 的病程趋势为模型导出的定性关系，未在患者队列数据上验证，图内不做定量外推。
- 技术路线图使用 raw 通道的 `dual-panel-bilevel` 模板作为结构骨架：模板自带的装饰性容器、分区底色与悬浮箭头位置不可通过 labels 修改（管线只允许覆盖文字），但该模板不含内嵌位图与调色板色块，是四类技术路线图模板中残留装饰最少的一类。
- 三张横向阶段链图（`fig_q1_response_flow`、`fig_q2_feature_flow`、`fig_q3_estimation_flow`）导出为约 13.7:1 的扁长条，这是模板几何（五节点同排、内容框 1000×70）的固有属性；按 `0.98\textwidth` 插入后高约 1.1 cm，不占页高，但纵向信息密度低。

## 八、复现入口

- 图稿摘要与标签定义：`手绘图/_tools/build_figures.py`
- 构建/校验/导出汇总：`手绘图/_tools/build_summary.json`、`export_summary.json`
- 文本审计：`手绘图/_tools/audit_text.json`
- CLI 验证记录：`检查结果/drawio_cli_verification.json`（draw.io 31.4.5，PNG/SVG/PDF 导出与中文渲染四项全通过）
