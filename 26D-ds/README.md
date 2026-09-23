# 2026 年中国研究生数学建模竞赛 D 题：山区洪涝灾害下无人机运输与通信协同优化

本项目为华为杯 D 题的全流程建模与论文工程，包含数据预处理、四问建模求解、顶刊级中文绘图、
HTML 矢量流程图与最终 LaTeX/PDF 论文交付。

## 运行命令

按以下顺序在项目根目录执行，即可从原始附件复现全部结果与论文：

```
python 数据预处理/eda.py
python Q1/solve_q1.py
python Q2/solve_q2.py
python Q3/solve_q3.py
python Q4/solve_q4.py
python 灵敏度分析/sensitivity.py
python scripts/build_final_results.py
python scripts/prepare_appendix_code.py
python 论文/build_paper.py
python scripts/checks/run_stage_gate.py --project . --stage step5
python scripts/checks/verify_delivery.py --project .
```

门禁入口固定为项目内 `scripts/checks/`，不要绕过或改写启动器。

## 依赖环境

- Python 3.12，依赖 numpy、pandas、scipy、matplotlib、openpyxl、rasterio、PyMuPDF
- 绘图子系统为技能内置的 `py_nature_core`，运行时由 `scripts/plot_common.py` 从
  `DSH_HOME` 解析技能目录，未复制到项目内
- HTML 矢量成图依赖 Electron（经 npx 调用）与技能内置 `assets/html-figure/`
- 论文编译依赖 TeX Live 2025 的 XeLaTeX，中文字体使用 SimSun、SimHei

## 最终结果

唯一结果源为 `results/final_results.json`。论文正文、摘要、各问 `result.md` 与结果提交文件
只引用该文件，不保留互相冲突的多套结果。四问的核心数值结论、资源使用与指标取值均在此汇总。

## 复现步骤

1. 确认 `赛题/` 下官方附件完整；
2. 依次运行上述 Python 命令，脚本会重建 `data/derived/`、各问 `figures/` 与 `results/final_results.json`；
3. 运行 `论文/build_paper.py` 生成 `论文/main.tex` 的附录代码块与结果表；
4. 运行阶段门禁与最终交付校验，二者退出码均为 0 时才视为完成。

## 异常处理记录

- 附件中返航电量下限以百分数给出，读取时统一折算为比例参与能量阈值比较；若按百分数直接参与
  计算会出现负的可用能量，属口径混用错误。
- 附件节点海拔与 30 米 DEM 采样海拔存在最大 16.2 m 的偏差。按题目口径，节点地面海拔以附件
  给定值为准，DEM 仅用于航段沿途地形净空、计划巡航海拔与通信视线遮挡判定。
- 逐箱货箱清单与需求汇总表经四个维度核对完全一致，未发生需要取舍的冲突。

## 外部新增数据

无。全部数据来自赛题官方附件及其派生产物，详见 `data/source_map.md`。

## 外部文献

见 `文献/source_map.md`。参考文献分三类分流：学术/技术证据进入最终 `thebibliography`，
通用数学建模教材与赛事格式规范只作内部学习与合规依据，不进入文后条目。

## 目录结构

- `赛题/`：题目、官方附件与原始数据
- `data/raw/`：官方附件副本；`data/derived/`：清洗与派生数据；`data/source_map.md`：数据来源映射
- `数据预处理/`：EDA 脚本、审计记录与预处理图
- `Q1/` 至 `Q4/`：各问的模型说明、主脚本、结果文件与图表
- `灵敏度分析/`：参数扫描与敏感度分析
- `手绘图/`：HTML 矢量流程图源与导出图，以及原理图提示词
- `figures/`：论文汇总图清单 `manifest.json`
- `results/`：唯一结果源 `final_results.json`
- `论文/`：LaTeX 源、附录代码与最终 PDF
- `检查结果/`：门禁报告、三轮自查与交付凭证