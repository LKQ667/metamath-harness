# math-paper-huashu

面向华数杯大学生数学建模竞赛的全自动工作流，兼容 Codex、Claude Code、OpenCode、TRAE Work 等 AI 编程工具，覆盖从项目初始化、数据分析、建模推导、代码实现、顶刊级可视化到 LaTeX 论文交付的完整链路。内置华数杯官方 `JXUSTmodeling.cls` 模板，step0–step5 硬门禁驱动，确保每一阶段产物可审计、可复现。

> 💬 交流群：**635765940**（QQ），欢迎加入讨论数学建模、AI 编程与论文写作

## 定位

这是一个端到端华数杯数学建模竞赛技能，将 step0 到 step5 的核心流程整合为一条主线，按阶段推进到最终论文成稿。适用于华数杯全国大学生数学建模竞赛及同类赛事。

## 使用方式

### 快速启动（完整指令，直接复制粘贴）

在任意支持 AGENT.md / Skills 约定的 AI 编程工具（Claude Code、Codex、OpenCode、TRAE Work 等）中，将以下完整指令粘贴到对话框即可一键启动全流程：

```
/goal /math-paper-huashu  /vison
先把赛题看清楚，必须严格遵守skills，完成赛题 路径 ，选择draw.io绘图+中文顶刊一区top1 python绘图。

1.禁止中途询问、禁止中途输出、禁止中途中断，未完成赛题禁止停止。

2.指定正文页数 不少于22页（正文为除附录、代码部分）。

3.总图片数量不少于15张，多加python绘图，禁用一维柱状图。

4.最终调用截图视觉功能对论文图片进行审查。
```

各命令含义：

| 命令 | 作用 |
|------|------|
| `/goal` | 激活目标执行模式，持续自主运行直到赛题完成 |
| `/math-paper-huashu` | 加载华数杯数学建模工作流技能 |
| `/vison` | 加载视觉审查技能，最终对论文图片进行截图审查 |

> 不同 AI IDE 的命令触发方式略有差异：TRAE Work 原生支持 `/skill` 触发；Claude Code、Codex、OpenCode 通过读取项目根目录的 `AGENT.md` 自动加载工作流，也可在对话中直接引用本技能名称。

### 指令逐条说明

| 序号 | 指令内容 | 执行要求 |
|------|---------|---------|
| 前置 | 先把赛题看清楚 | 必须完整阅读赛题，理解每一问的目标、输入数据和约束条件 |
| 前置 | 必须严格遵守 skills | 按 step0–step5 阶段流程与硬门禁推进，不得跳过 |
| 前置 | 完成赛题路径 | 从建模推导到代码实现到论文交付，全链路完成 |
| 前置 | 选择 draw.io 绘图 + 中文顶刊一区 top1 Python 绘图 | 非数据图用 Draw.io，数据图用内置顶刊 Python 链路 |
| 1 | 禁止中途询问、禁止中途输出、禁止中途中断，未完成赛题禁止停止 | 全自动执行，不向用户提问，不输出中间进度，直到赛题完成 |
| 2 | 正文页数不少于 22 页 | 正文为除附录、代码部分的内容 |
| 3 | 总图片数量不少于 15 张 | 多加 Python 绘图，禁用一维普通柱状图 |
| 4 | 最终调用截图视觉功能对论文图片进行审查 | 通过 `/vison` 逐张审查论文图片质量 |

### 工作流程

```
先把赛题看清楚 → 严格遵守 skills → 完成赛题全路径 → draw.io 绘图 + 中文顶刊一区 top1 Python 绘图 → 视觉审查
```

### /vison 视觉审查技能

`/vison` 对应 [claude-vision-skill](https://github.com/asuojun/claude-vision-skill) 技能。在论文完成后，该技能通过调用阿里云百炼（DashScope）OpenAI 兼容接口的 vision 模型，把论文中的每张图片转为 base64 后发送，返回文字描述与质量评估，用于审查图片是否存在乱码、丢字、方框、问号替代字符等问题。

#### 第一步：下载技能

```bash
git clone https://github.com/asuojun/claude-vision-skill.git
```

根据所用 AI 编程工具，将技能放入对应目录：

| AI 编程工具 | 安装路径 |
|------------|---------|
| TRAE Work | `%USERPROFILE%\.trae-cn\skills\claude-vision-skill`（Windows）<br>`~/.trae-cn/skills/claude-vision-skill`（macOS） |
| Claude Code | 项目根目录或 `~/.claude/skills/claude-vision-skill`，自动发现 |
| Codex | 放入项目目录，通过 `AGENT.md` 引用 |
| OpenCode | 放入项目目录或用户级 skills 目录，通过 `AGENT.md` 引用 |

#### 第二步：获取百炼 API Key

1. 登录阿里云百炼平台：https://bailian.console.aliyun.com/us-east-1?tab=dashboard#/api-key
2. 在「API-KEY 管理」页面创建并复制你的 API Key（不要把真实值写入项目文件）

#### 第三步：配置模型与 API Key

技能核心脚本 `vision.js` 通过环境变量或同目录 `.env` 文件读取配置。可用的配置项：

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `DASHSCOPE_API_KEY` | 百炼平台 API Key（必填） | 无 |
| `VISION_MODEL` | 视觉模型名称（必填） | 无 |
| `DASHSCOPE_BASE_URL` | OpenAI 兼容接口地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

**推荐配置一：qwen3.7-plus（默认，质量优先）**

在 `vision.js` 同目录创建 `.env` 文件：

```bash
DASHSCOPE_API_KEY=你的百炼key
VISION_MODEL=qwen3.7-plus
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**推荐配置二：qwen3.7-flash-2026-07-15（速度优先，成本更低）**

```bash
DASHSCOPE_API_KEY=你的百炼key
VISION_MODEL=qwen3.7-flash-2026-07-15
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

> API Key 获取地址：https://bailian.console.aliyun.com/us-east-1?tab=dashboard#/api-key
> 两种模型任选其一，`qwen3.7-plus` 识别质量更高，`qwen3.7-flash-2026-07-15` 响应更快。如需切换，修改 `.env` 中的 `VISION_MODEL` 即可。

#### 第四步：安装依赖并验证

```bash
npm install dotenv
node vision.js <任意图片路径> "用中文描述这张图片"
```

返回图片文字描述即配置成功。配置完成后，AI 编程工具会自动识别图片并调用 `vision.js`，无需手动打命令。

#### 两种配置对比

| 配置 | 模型 | 特点 | 适用场景 |
|------|------|------|---------|
| 配置一 | `qwen3.7-plus` | 识别质量高，细节准确 | 论文图片最终审查（推荐） |
| 配置二 | `qwen3.7-flash-2026-07-15` | 响应快，成本更低 | 批量快速预审 |

详见：https://github.com/asuojun/claude-vision-skill

## 交付规格

| 指标 | 要求 |
|------|------|
| 正文页数 | 不少于 22 页（正文为除附录、代码部分） |
| 图片总数 | 不少于 15 张 |
| Python 绘图 | 多加顶刊级三维图与数据图 |
| 禁用图表 | 禁用一维普通柱状图 |
| 非数据绘图 | Draw.io 模式（保留 `.drawio` 源文件可编辑） |
| 数据绘图 | 中文顶刊一区 top1 风格（SVG + PDF + PNG 三格式导出） |
| 最终审查 | 调用截图视觉功能对论文图片逐一审查 |
| 执行模式 | 禁止中途询问、禁止中途输出、禁止中途中断，未完成赛题禁止停止 |

## 功能概览

| 阶段 | 核心任务 | 核心产物 |
|------|----------|----------|
| **step0** | 项目初始化与资料收集 | 文件夹结构、AGENT.md、README、权威文献清单、LaTeX 环境烟雾编译 |
| **step1** | 数据预处理与 EDA | 数据清洗、EDA 图表、问题重述、方法筛选 |
| **step2** | 单问分析建模 | 模型选择、数学推导、公式、结果分析、图表建议 |
| **step3** | 代码实现 | Python 算法、顶刊级图表、结果文件 |
| **step4** | 论文写作与内容组织 | 正文、摘要、图表入文、灵敏度分析、技术路线图 |
| **step5** | 排版编译与最终交付 | LaTeX 编译、PDF 导出、参考文献、附录、三轮自查、门禁检查；不主动生成 Word，已有 Word 不影响流程 |

## 目录结构

```
math-paper-huashu/
├── AGENT.md                    # 项目级规则
├── SKILL.md                    # 技能主文件
├── agents/
│   └── openai.yaml             # OpenAI 工具适配
├── assets/
│   ├── drawio/                 # Draw.io 绘图模板库
│   │   ├── UPSTREAM.md
│   │   └── template_library.json
│   ├── latex/                  # LaTeX 环境配置
│   │   ├── runtime-manifest.json
│   │   └── texlive.profile
│   ├── reference-pictures/     # 参考图片
│   └── templates/
│       ├── JXUSTmodeling.cls   # 华数杯官方模板类文件
│       ├── main.tex            # LaTeX 主模板
│       └── py-figures/         # 14 个顶刊级 Python 绘图模板
├── references/
│   ├── appendix-code-prose-style.md   # 附录代码文风规范
│   ├── auto-checklist.md              # 全自动执行清单
│   ├── drawing-pipeline.md            # 双绘图选路与 Draw.io 流水线
│   ├── latex-bootstrap.md             # Windows LaTeX 自动安装
│   ├── literature.md                  # 文献检索规范
│   ├── model-writing-b477.md          # 模型写作参考
│   ├── py-chart-selection.md          # Python 图型决策树
│   ├── py-palette-export.md           # 顶刊配色导出规范
│   ├── py-template-recipes.md         # Python 模板范式
│   ├── visual-style.md                # 视觉风格规范
│   └── workflow.md                    # 详细工作流
└── scripts/
    ├── checks/                 # 交付门禁检查脚本
    │   ├── run_stage_gate.py   # 阶段门禁入口
    │   ├── run_all_checks.py   # 全量检查入口
    │   ├── verify_delivery.py  # 最终交付验证
    │   ├── gate_registry.py    # 门禁注册表
    │   └── check_*.py          # 各类检查项
    ├── drawing/
    │   └── drawio_pipeline.py  # Draw.io 自动化流水线
    ├── latex/
    │   └── latex_runtime.py    # LaTeX 环境管理
    ├── plotting/
    │   ├── py_nature_core.py   # 顶刊绘图核心库
    │   ├── template_registry.py
    │   ├── render_template_demo.py
    │   └── run_py_nature_qa.py # 中文字体 QA
    └── prepare_appendix_code.py # 附录代码净化脚本
```

## 核心能力

### 1. 华数杯官方模板

内置 `JXUSTmodeling.cls` 华数杯官方模板类文件，保持 `\documentclass{JXUSTmodeling}` 排版规范，包含参赛类别、参赛编号、原生 `abstract` 环境、AI 工具使用声明与 `appendixx` 附录结构。

### 2. 顶刊级 Python 可视化

内置 14 个 Nature 系绘图模板，覆盖网络分析、灵敏度分析、优化、时空分析、统计等常见建模场景。强烈建议优先评估顶刊一区中文三维图（三维曲面、三维散点、三维轨迹、三维场、三维响应面），提升信息密度。所有图表自动导出 SVG + PDF + PNG 三种格式，经中文字体 QA 检查后方可入文。

**柱状图锁定策略**：`禁用` 为零例外并覆盖时间轴、甘特图和区间图的柱形实现；`少用` 只有在“类别很少、必须零基线、核心任务是绝对高度比较”同时成立且同源 manifest 条目具有完整 `bar_exception` 时允许；`正常` 仍按数据语义选图。

### 3. Draw.io 绘图

Draw.io 模式自动生成流程图、问题分析流程图和技术路线图，保留 `.drawio` 源文件、SVG、PDF、2× PNG 四种格式。概念类图保留 2–4 份提示词但不自动生图。所有非数据图必须完成内容、中文、符号、裁切、清晰度、路由/重叠和正文回填检查。

### 4. step0–step5 硬门禁

每个阶段完成后必须运行门禁检查，退出码非 0 时只允许修复失败项并重跑当前阶段，不得跳过：

```bash
# 初始化
python scripts/checks/run_stage_gate.py --project <项目根目录> --init

# 阶段检查
python scripts/checks/run_stage_gate.py --project <项目根目录> --stage stepN

# 最终交付验证
python scripts/checks/verify_delivery.py --project <项目根目录>
```

门禁覆盖：LaTeX 环境、阶段契约、唯一结果源、结果一致性、代码目录分区、摘要、图片、绘图模式、Python 数据图、技术路线图、Q 目录、模板、论文结构、页数、留白、附录代码、三轮自查、路径、数据来源和最终交付评分卡。

### 5. 三轮全链路自查

最终交付前必须完成三轮自查并写入 `检查结果/三轮自查.md`：

- 第一轮：内容与数据链（自然衔接、句式变化、括号密度、第一人称必要性）
- 第二轮：论文与版式链（模板摘要、文风门禁、图表入文）
- 第三轮：代码与复现链（源代码完整性、注释清理、原版与净化版一致性）

### 6. 视觉审查

论文完成后调用 `/vison`（[claude-vision-skill](https://github.com/asuojun/claude-vision-skill)）对全部论文图片进行截图审查，检查是否存在：
- 中文乱码、丢字、方框、问号替代字符
- 坐标轴、标题、图例显示异常
- 配色、分辨率、版式不达标

## 安装

将本仓库完整复制到本地：

```bash
git clone https://github.com/LKQ667/math-paper-huashu.git
```

根据所用 AI 编程工具，将本技能放入对应目录或通过 `AGENT.md` 加载：

| AI 编程工具 | 安装路径 / 加载方式 |
|------------|-------------------|
| TRAE Work | `%USERPROFILE%\.trae-cn\skills\math-paper-huashu`（Windows）<br>`~/.trae-cn/skills/math-paper-huashu`（macOS） |
| Claude Code | 项目根目录或 `~/.claude/skills/math-paper-huashu`，自动发现 |
| Codex | 项目根目录，通过 `AGENT.md` 加载 |
| OpenCode | 项目根目录或用户级 skills 目录，通过 `AGENT.md` 加载 |

本技能通过项目根目录的 `AGENT.md` 声明工作流规则，任何支持该约定的 AI 编程工具均可自动加载。无需额外配置，打开项目目录即可使用。

## 设计原则

- **全程中文**：代码关键字除外，图片、图注、流程图文字全部中文
- **数据可追溯**：所有数据、方法、结论必须有真实来源，严禁编造
- **证据驱动**：不臆造结果，所有结论基于可复查证据和门禁通过
- **顶刊标准**：图表默认达到顶刊科研绘图标准，优先三维可视化
- **硬门禁**：每阶段产物必须通过门禁检查才能继续，不可跳过
- **全自动交付**：从项目初始化到最终 PDF，一次运行即可完成

## 交流与反馈

- QQ 群：**635765940**
- 欢迎提 Issue 或 PR

## 许可

本工作流仅供学习与使用。
