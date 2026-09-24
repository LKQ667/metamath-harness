# 通用神经网络处理器下的多核调度问题（2026 华为杯 A 题）

本目录是完整的数学建模竞赛项目，围绕赛题《通用神经网络处理器下的多核调度问题》
建立多核切图与子图调度模型，设计求解算法，并用赛题提供的官方评估程序在全部
100 个测试用例上给出可复现的实验结果与论文。

## 题目与目标

给定一张有向无环计算图（Op-Tensor 二部图）与 N 个同构 NPU 核心，需要联合决定
三件事：每个核内操作属于哪个子图、每个子图分配到哪个核心、同一核心上子图的
执行顺序。评价指标以总体任务执行时间（Makespan）为主，兼顾总额外数据搬运量与
只读 Cache 命中率。赛题分三个问题：场景 A（无核间同步）、场景 B（有核间同步）、
共享只读 L2 的场景 B。

## 目录结构

| 目录 | 内容 |
|---|---|
| `赛题/` | 赛题原文与附件压缩包（保持原样，未做任何修改） |
| `文献/` | 参考文献清单、阅读笔记与文献筛选结果 |
| `data/` | 原始配置副本、派生数据（用例结构画像）与数据来源映射 |
| `数据预处理/` | 计算图结构解析、EDA、派生数据生成脚本与本阶段配图 |
| `Q1/` | 问题一（场景 A）模型、代码、结果与图表 |
| `Q2/` | 问题二（场景 B）模型、代码、结果与图表 |
| `Q3/` | 问题三（只读 L2）模型、代码、结果与图表 |
| `灵敏度分析/` | 算法参数扫描实验与图 |
| `手绘图/` | 技术路线图与各问流程图的 HTML 源、矢量 PDF、交付 PNG 与概念图提示词 |
| `摘要/` | 摘要草稿与素材 |
| `论文/` | GMCMthesis 模板、`main.tex`、数值宏、附录与最终 PDF |
| `results/` | 唯一最终结果源 `final_results.json`、方案缓存与评估原始输出 |
| `检查结果/` | 各阶段门禁报告、三轮自查与最终交付凭证 |
| `scripts/` | 共享算法工具、实验总控、文档生成与门禁启动器 |

## 依赖环境

- Python 3.12（标准库 + NumPy + Matplotlib），无需 GPU；
- XeLaTeX（TeX Live 2025）与 SimSun、SimHei、Times New Roman 字体；
- Node.js 与 Electron（仅用于 `手绘图/` 下 HTML 矢量成图，工具链随技能内置）；
- 赛题附件解压工作副本放在项目同级目录 `../_hw_suite/`，由
  `赛题/通用神经网络处理器下的多核调度问题  附件.zip` 解压得到；也可通过环境变量
  `HUAWEI_SUITE_DIR` 指定其他位置。该目录全程只读。

## 数据来源

全部输入数据来自赛题附件，未使用任何外部或虚构数据；逐条来源见
`data/source_map.md`。官方评估程序、固定配置与测试用例保持原样，本项目不修改
其中任何文件。外部文献仅用于方法溯源，清单见 `文献/source_map.md`。

## 运行命令

```powershell
python 数据预处理/build_dataset.py
python scripts/run_experiments.py --problems 1,2,3 --cores 2,3,4,5 --workers 9
python scripts/aggregate_results.py
python 数据预处理/fig_profile.py
python Q1/figures_q1.py
python Q2/figures_q2.py
python Q3/figures_q3.py
python 灵敏度分析/run_sensitivity.py --workers 4
python 灵敏度分析/fig_sensitivity.py
python scripts/build_appendix.py
python scripts/build_result_docs.py
python scripts/fill_paper_numbers.py
python scripts/checks/run_stage_gate.py --project . --stage step5
python scripts/checks/verify_delivery.py --project .
```

## 复现步骤

1. 解压赛题附件到 `../_hw_suite/`（或在 `HUAWEI_SUITE_DIR` 中指定其位置）；
2. 运行 `python 数据预处理/build_dataset.py` 生成用例结构画像；
3. 运行 `python scripts/run_experiments.py` 生成全部方案并调用官方评估程序；
4. 运行 `python scripts/aggregate_results.py` 聚合出唯一结果源；
5. 依次运行各配图脚本、附录与文档生成脚本；
6. 运行 `python scripts/checks/run_stage_gate.py --project . --stage step5` 完成
   排版编译与全量门禁，最后用 `verify_delivery.py` 只读校验交付凭证。

## 最终结果

全部数值以 `results/final_results.json` 为唯一来源，关键结论如下（100 个用例平均）：

- 问题一（场景 A）：5 核平均加速比 1.9197 倍，4 核 1.7282 倍；
- 问题二（场景 B）：5 核平均加速比 2.1405 倍，4 核 1.9854 倍；
- 问题三（只读 L2）：5 核下只读 Cache 相对无 L2 基线的平均加速比与平均命中率见
  `results/final_results.json` 的 `q3` 字段与论文正文。

逐用例的 Makespan、额外搬运量与 Cache 命中率见论文附录 A 至附录 C。

## 异常处理记录

| 时间 | 现象 | 处理 |
|---|---|---|
| 建模初期 | 按负载均衡任意分配操作会构造出子图级环，官方评估程序直接报错终止 | 把无环性提升为切分构造约束，改用三类可证明无环的切分构造，并在候选择优前逐一检查子图依赖图 |
| 算法调优 | 连续段切分在深层层状图上退化为链式依赖，估计完工时间接近单核基线 | 增加分层切分候选，并把全局主存带宽下界写入估算模型 |
| 算法调优 | 个别用例并行方案的实测结果略差于单核基线 | 引入单核兜底阈值，只有并行方案的估算值明显更优时才采用并行方案 |
| 排版阶段 | 附录长表列宽超过版心，出现 Overfull 警告 | 把每个问题的逐用例结果拆成两张六列长表并使用小字号与紧凑列间距 |

## 外部新增数据

本项目未引入任何外部新增数据。全部输入均来自赛题附件，派生数据由项目内脚本从
原始计算图生成，生成关系记录在 `data/source_map.md`。

## 外部文献

外部文献仅用于方法溯源与候选方法比选，清单与用途见 `文献/source_map.md` 与
`文献/阅读笔记.md`；进入论文文后参考文献的条目全部在正文中被真实引用。
