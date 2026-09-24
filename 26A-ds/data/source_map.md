# 数据来源映射

本文件逐条登记项目内每一份数据的名称、用途、来源类型与具体依据。所有数据均来自
赛题官方材料包，未使用任何外部数据、模拟数据或虚构数据。

## 原始数据

赛题附件的原始压缩包与题目文档保存在 `赛题/` 下，保持原样未做任何修改。为便于调用
官方评估程序，附件解压出的工作副本放在项目同级的 `../_hw_suite/` 目录中（由
`赛题/通用神经网络处理器下的多核调度问题  附件.zip` 解压得到），项目内所有脚本
通过 `HUAWEI_SUITE_DIR` 环境变量或该默认位置定位它，不写入、不修改其中任何文件。

| 数据名称 | 用途 | 来源类型 | 具体依据 |
|---|---|---|---|
| `data/config.txt` | 固定评估配置（L1/UB 容量、DDR 带宽、场景 A/B 等待周期、问题三 Cache 参数） | 赛题官方附件副本 | 赛题附件压缩包内的 `data/config.txt`，解压工作副本位于 `../_hw_suite/data/config.txt` |
| 计算图测试用例 `case_001.json` ～ `case_100.json` | 三个问题的全部实验输入 | 赛题官方附件（只读引用，不复制进项目） | `../_hw_suite/data/case_001.json` ～ `case_100.json`，来源于 `赛题/通用神经网络处理器下的多核调度问题  附件.zip` |
| 核内调度与多核模拟算法说明 | 理解官方评估口径，支撑模型与算法设计 | 赛题官方附件 | `../_hw_suite/docs/核内调度算法.md`、`../_hw_suite/docs/多核并行模拟执行算法.md` |
| 官方评估程序 | 生成 Makespan、额外搬运量、Cache 命中率等全部指标 | 赛题官方附件（只读调用） | `../_hw_suite/code/multicore_cut_evaluate_problem_1.py`、`multicore_cut_evaluate_problem_2.py`、`multicore_cut_evaluate_problem_3.py`、`singlecore_evaluate.py` |
| 赛题原文 | 问题重述、约束与指标定义的唯一依据 | 赛题官方文件 | `赛题/通用神经网络处理器下的多核调度问题.docx`（提取文本见 `赛题/_题目原文.txt`） |

## 派生数据

| 数据名称 | 用途 | 来源类型 | 具体依据 |
|---|---|---|---|
| `data/case_profile.csv` | 100 个用例的结构画像（节点数、边数、各流水线周期、关键路径、并行宽度、DDR 字节数等），用于 EDA、算法选参与论文描述统计 | 派生数据 | 上游源文件为 `../_hw_suite/data/case_*.json`；生成脚本为 `数据预处理/build_dataset.py`，处理说明见 `数据预处理/README.md` |
| `results/plans/*.json` | 各用例、各核数、各问题下的切图与调度方案 | 派生数据 | 上游源文件为 `../_hw_suite/data/case_*.json`；生成脚本为 `scripts/partition.py` 与 `scripts/run_experiments.py` |
| `results/evaluation/*.json` | 官方评估程序对上述方案的原始输出 | 派生数据 | 由 `../_hw_suite/code/multicore_cut_evaluate_problem_{1,2,3}.py` 在固定 `data/config.txt` 下生成 |
| `results/final_results.json` | 全项目唯一最终结果源 | 派生数据 | 由 `scripts/aggregate_results.py` 从 `results/evaluation/` 与 `results/singlecore_makespan.json` 聚合得到 |

## 使用约束

1. `../_hw_suite/` 下的任何文件均为只读输入，本项目不修改、不覆盖、不新增文件；
   `赛题/` 下的原始压缩包与题目文档同样保持原样。
2. 论文、摘要、`result.md` 与 README 中的一切数值只能引用 `results/final_results.json`。
3. 若后续需要新增数据，必须在本文件登记数据名称、用途、来源类型与具体依据后才能进入建模链路。
