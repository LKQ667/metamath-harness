# 24华为杯C-dsv.1 项目说明

## 任务范围

- 赛题：2024 年全国大学生数学建模竞赛 C 题「农作物的种植策略」，官方题面与附件位于 `赛题/`。
- 论文规范：按任务卡片锁定要求采用华为杯（中国研究生数学建模竞赛）GMCMthesis 模板与官方结构；正文、图题与图内文字统一使用中文。
- 交付目标：`论文/main.pdf` 最终论文，配套 `results/final_results.json` 唯一结果源、`figures/manifest.json` 图片清单与 `检查结果/` 全部门禁报告。

## 依赖环境

- Python 3.12，第三方库：`numpy`、`pandas`、`openpyxl`、`matplotlib`、`scipy`、`pulp`（CBC 求解器）。
- XeLaTeX + latexmk（宿主机 TeX Live 2025），LaTeX 论文编译走 `latexmk -xelatex`。
- 非数据流程类图使用技能内置 HTML 矢量成图引擎（Electron printToPDF），概念类图仅保留提示词。

## 目录结构

- `赛题/`：题目 PDF 与附件 1、附件 2、结果模板。
- `文献/`：文献清单与来源映射，记录来源链接、可信等级与支撑章节。
- `data/`：原始数据副本、派生数据与 `source_map.md` 数据来源登记。
- `数据预处理/`：EDA 脚本、清洗与派生说明。
- `Q1/`、`Q2/`、`Q3/`：逐问的 README、模型说明、主脚本、结果与图片。
- `results/`：`final_results.json` 唯一结果源。
- `灵敏度分析/`：参数扫描脚本与结果。
- `手绘图/`：HTML 矢量流程类图源与导出图，以及概念类图提示词。
- `论文/`：LaTeX 主稿、模板类文件、附录代码与最终 PDF。
- `检查结果/`：各阶段门禁报告、三轮自查与交付凭证。

## 运行命令与复现步骤

1. 安装依赖：`python -m pip install numpy pandas openpyxl matplotlib scipy pulp`。
2. 生成派生数据：
   `python 数据预处理/prepare_data.py`
3. 逐问求解与出图：
   `python Q1/solve_q1.py`、`python Q1/make_figs_q1.py`
   `python Q2/solve_q2.py`、`python Q2/make_figs_q2.py`
   `python Q3/solve_q3.py`、`python Q3/make_figs_q3.py`
4. 汇总唯一结果源：`python scripts/collect_final_results.py`
5. 灵敏度分析：`python 灵敏度分析/sensitivity.py`
6. 论文编译：`python 论文/compile.py`（内部调用 latexmk -xelatex）
7. 阶段门禁：
   `python scripts/checks/run_stage_gate.py --project . --stage stepN`
   最终只读校验：`python scripts/checks/verify_delivery.py --project . --verify-delivery`

## 最终结果

见 `results/final_results.json`。论文正文、摘要、各问 `result.md` 与本说明中的全部数值均引用该唯一结果源。

## 异常处理记录

- 附件 2「2023 年统计的相关数据」中销售价格为区间值，模型取区间中点作为名义价格，上下界用于问题二的区间抽样与问题三的相关性建模；该处理在正文假设中显式声明。
- 附件 1 与附件 2 无缺失值；地块「普通大棚」名称带尾随空格，已在派生阶段规范化。
- 智慧大棚第一季的亩产量、种植成本与销售价格按附件 2 注释与普通大棚一致处理。
- 2024~2030 共 7 年决策跨越 2023 年基期，重茬与豆类轮作约束需要 2023 年的作物归属作为初始条件。

## 外部新增数据与外部文献

- 未引入任何外部数据；全部数值来自 `赛题/附件1.xlsx` 与 `赛题/附件2.xlsx`。
- 外部文献仅用于方法学引用，清单与可信等级见 `文献/source_map.md`。
