# math-paper-cn

面向中文数学建模竞赛的全自动工作流，兼容 Codex、Claude Code、OpenCode、TRAE Work 等 AI 编程工具，覆盖从项目初始化、数据分析、建模推导、代码实现、顶刊级可视化到 LaTeX 论文交付的完整链路。

> 💬 交流群：**635765940**（QQ），欢迎加入讨论数学建模、AI 编程与论文写作

## 定位

这是一个端到端数学建模竞赛技能，将 step0 到 step5 的核心流程整合为一条主线，按阶段推进到最终论文成稿。适用于全国大学生数学建模竞赛、APMCM 等同类赛事。

## 功能概览

| 阶段 | 核心任务 | 核心产物 |
|------|----------|----------|
| **step0** | 项目初始化与资料收集 | 文件夹结构、AGENT.md、README、权威文献清单 |
| **step1** | 数据预处理与 EDA | 数据清洗、EDA 图表、问题重述、方法筛选 |
| **step2** | 单问分析建模 | 模型选择、数学推导、公式、结果分析、图表建议 |
| **step3** | 代码实现 | Python 算法、顶刊级图表、结果文件 |
| **step4** | 论文写作与内容组织 | 正文、摘要、图表入文、灵敏度分析 |
| **step5** | 排版编译与最终交付 | LaTeX 编译、PDF 导出、参考文献、附录、门禁检查；不主动生成 Word，已有 Word 不影响流程 |

## 目录结构

```
math-paper-cn/
├── AGENT.md                    # 项目级规则
├── SKILL.md                    # 技能主文件
├── assets/
│   ├── drawio/                 # Draw.io 绘图模板库
│   │   ├── UPSTREAM.md
│   │   └── template_library.json
│   ├── reference-pictures/     # 参考图片
│   └── templates/
│       ├── main.tex            # LaTeX 主模板
│       └── py-figures/         # 14 个顶刊级 Python 绘图模板
├── references/
│   ├── appendix-code-prose-style.md
│   ├── auto-checklist.md
│   ├── drawing-pipeline.md
│   ├── literature.md
│   ├── model-writing-b477.md
│   ├── py-chart-selection.md
│   ├── py-palette-export.md
│   ├── py-template-recipes.md
│   ├── visual-style.md
│   └── workflow.md
└── scripts/
    ├── checks/                 # 37 个交付门禁检查脚本
    │   ├── run_all_checks.py   # 全量检查入口
    │   ├── check_*.py          # 各类检查项
    │   └── common.py
    ├── drawing/
    │   └── drawio_pipeline.py  # Draw.io 自动化流水线
    ├── plotting/
    │   ├── py_nature_core.py
    │   ├── template_registry.py
    │   ├── render_template_demo.py
    │   └── run_py_nature_qa.py
    └── prepare_appendix_code.py # 附录代码净化脚本
```

## 演示图片

本技能内置 14 个 Nature 系绘图模板，可自动生成顶刊级科研图表。以下为部分示例：

### 三维曲面与优化分析

| 3D 响应曲面 | Pareto 前沿 |
|:---:|:---:|
| ![3D 响应曲面](./演示图片/3d_response_surface.png) | ![Pareto 前沿](./演示图片/pareto_front.png) |

### 机理模型与预测对比

| 机理模型三维曲面 | 预测实测对比 |
|:---:|:---:|
| ![机理模型三维曲面](./演示图片/fig_q1_1_机理模型三维曲面.png) | ![预测实测对比](./演示图片/fig_q2_1_预测实测对比.png) |

### 空间分析与灵敏度

| 偏好空间分区 | 灵敏度热力图 |
|:---:|:---:|
| ![偏好空间分区](./演示图片/fig_q4_1_偏好空间分区.png) | ![灵敏度热力图](./演示图片/fig_q5_1_灵敏度热力图.png) |

### Nature 级科研绘图

| 单细胞免疫微环境 | EEG 神经动力学 |
|:---:|:---:|
| ![单细胞免疫微环境](./演示图片/fig01_单细胞免疫微环境.png) | ![EEG 神经动力学](./演示图片/fig03_EEG神经动力学.png) |

| 材料三元性能优化 | 动态网络鲁棒性 |
|:---:|:---:|
| ![材料三元性能优化](./演示图片/fig06_材料三元性能优化.png) | ![动态网络鲁棒性](./演示图片/fig07_动态网络鲁棒性.png) |

| 统计分布分析 | 分组分析 |
|:---:|:---:|
| ![散点图矩阵](./演示图片/散点图矩阵.png) | ![针肋排数分组分析](./演示图片/针肋排数分组分析.png) |

## 核心能力

### 1. 顶刊级 Python 可视化

内置 14 个 Nature 系绘图模板，覆盖网络分析、灵敏度分析、优化、时空分析、统计等常见建模场景。所有图表自动导出 SVG + PDF + PNG 三种格式，经中文字体 QA 检查后方可入文。

### 2. 双模式绘图流程

- **Draw.io 模式**：自动生成流程图、问题分析图、技术路线图，保留 `.drawio` 源文件可编辑
- **AI 全自动绘图**：自动生成提示词并调用图像生成，产出概念图、模型图、原理图
- 项目首次启动时锁定模式，写入 `figures/manifest.json`

### 3. 交付门禁检查

37 个自动化检查脚本覆盖：
- 结果一致性（唯一数据源）
- 论文质量（页数、留白、强调、符号、引用）
- 图片合约（manifest、绘图模式锁定、QA 记录）
- 代码完整性（附录代码、路径清洁）
- 模板适配（主模板结构、章节白名单）

最终交付前运行 `python scripts/checks/run_all_checks.py --project <目录>`，所有检查通过后方可完成。

### 4. LaTeX 论文排版

- 内置 `assets/templates/main.tex` 主模板，符合国赛论文规范
- 自动处理摘要、关键词、参考文献、附录
- 支持 PDF 导出；不主动生成或转换 Word，已有 Word 文件不影响流程

## 使用方式

### 安装

将本仓库完整复制到本地：

```bash
git clone https://github.com/LKQ667/math-paper-cn.git
```

对于 TRAE Work 用户，可直接复制到技能目录：

- Windows：`%USERPROFILE%\.trae-cn\skills\math-paper-cn`
- macOS：`~/.trae-cn/skills/math-paper-cn`

### 触发

在支持 AGENT.md 的 AI 编程工具（Codex、Claude Code、OpenCode、TRAE Work 等）中打开项目目录，工具会自动加载本工作流。也可手动调用：

```
用 math-paper-cn 跑这个赛题
```

### 运行门禁检查

```bash
python scripts/checks/run_all_checks.py --project /path/to/project
```

## 设计原则

- **全程中文**：代码关键字除外，图片、图注、流程图文字全部中文
- **数据可追溯**：所有数据、方法、结论必须有真实来源，严禁编造
- **证据驱动**：不臆造结果，所有结论基于可复查证据和检查通过
- **顶刊标准**：图表默认达到顶刊科研绘图标准
- **全自动交付**：从项目初始化到最终 PDF，一次运行即可完成

## 交流与反馈

- QQ 群：**635765940**
- 欢迎提 Issue 或 PR

## 许可

本工作流仅供学习与使用。
