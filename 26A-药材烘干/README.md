# 2026 高教社杯全国大学生数学建模竞赛 A 题：药材的烘干问题

本仓库为本题的完整数学建模工程：从赛题与附件出发，建立圆柱形药材在热风烘干过程中的
传热—传质耦合模型，逐问求解并输出规范 LaTeX/PDF 论文。

## 1. 题目与任务

药材形状近似为圆柱（长 25 cm，半径 2 cm）。烘干开始时药材温度 28 ℃、干基含水率
2.55 kg/kg，烘房温度与水分浓度随时间变化（见附件 1）。四问任务：

1. 建立预热平衡阶段药材温度与水分浓度的数学模型，给出 100/300/600/900/1200/1500/1800 s
   及到药材中心距离 0/0.5/1/1.5/2 cm 的结果，并把 1800 s 内每隔 1 s、径向每隔 0.1 cm
   的完整结果写入 result1.xlsx。
2. 建立整个烘干过程（预热平衡 + 恒温干燥）的模型，给出 3 h 内每隔 0.5 h 的结果，
   并把每隔 1 s、径向每隔 0.1 cm 的完整结果写入 result2.xlsx。
3. 以各处水分浓度低于 0.15 kg/kg 为烘干完成判据，确定烘干所需时间，输出 result3.xlsx。
4. 考虑药材因失水发生尺寸收缩，重新确定烘干时长，输出 result4.xlsx。

## 2. 目录分区

| 目录 | 内容 |
| --- | --- |
| 赛题/ | 题目原文与官方附件（附件 1、附件 2、附件 3 结果模板） |
| 文献/ | 文献来源映射与阅读要点 |
| data/ | 原始附件副本、清洗与派生数据、数据来源映射 |
| 数据预处理/ | 附件解析、EDA、预处理脚本与图 |
| Q1/ Q2/ Q3/ Q4/ | 各问模型说明、主脚本、结果说明与图 |
| 灵敏度分析/ | 参数扫描与敏感度图 |
| 手绘图/ | Draw.io 技术路线图源文件与导出图、概念示意图提示词 |
| 摘要/ | 摘要文本与落版素材 |
| 论文/ | LaTeX 主文件、参考文献、附录代码、PDF |
| results/ | 唯一最终结果源与四份结果工作簿 |
| 检查结果/ | 各阶段门禁报告、三轮自查、附录代码复核 |

## 3. 依赖环境

- Python 3.13（托管解释器），第三方库：numpy、scipy、pandas、matplotlib、openpyxl、
  pillow、drawsvg 等，见 `scripts/requirements.txt`。
- XeLaTeX（TeX Live 2025，含 ctex、unicode-math、booktabs、listings、algorithm 等宏包），
  本机已探测到 SimSun、SimHei、Times New Roman、Cambria Math 四种字体。
- Draw.io Desktop（用于技术路线图源文件与 PNG/SVG/PDF 导出）。
- 绘图字体统一使用 Microsoft YaHei / SimHei，保证中文标题、坐标轴与图例不乱码。

## 4. 运行命令

```bash
# 0) 附件解析与数据预处理
python 数据预处理/prepare_data.py

# 1) 逐问求解（会写出 results/final_results.json 与 result1..result4.xlsx）
python Q1/solve_q1.py
python Q2/solve_q2.py
python Q3/solve_q3.py
python Q4/solve_q4.py

# 2) 绘图（Python 数据图导出 svg + pdf + png）
python Q1/plot_q1.py
python Q2/plot_q2.py
python Q3/plot_q3.py
python Q4/plot_q4.py
python 灵敏度分析/plot_sensitivity.py

# 3) 技术路线图（Draw.io）与附录净化代码
python scripts/build_roadmap.py
python scripts/prepare_appendix_code.py --project .

# 4) 论文编译与门禁
python scripts/checks/run_stage_gate.py --project . --stage step4
python scripts/checks/run_stage_gate.py --project . --stage step5
python scripts/checks/verify_delivery.py --project .
```

## 5. 最终结果

最终数值结果统一写在 `results/final_results.json`，论文正文、摘要、各问 result.md 与
四份结果工作簿只能引用该唯一结果源。关键结论包括：预热平衡阶段 1800 s 内温度由
28 ℃ 向烘房温度趋近、水分浓度仅在表层 0.3 cm 内明显下降；整个烘干过程在恒温干燥
条件下约 2 天完成；考虑收缩后烘干时长相应缩短。

## 6. 复现步骤

1. 确认 `赛题/附件/` 下附件 1、附件 2、附件 3 未被改动。
2. 依次执行第 4 节命令；所有脚本以项目根目录为工作目录，内部只使用相对路径。
3. 校验 `results/final_results.json` 与 `result1..result4.xlsx` 的数值一致性。
4. 运行 step4、step5 门禁与 `verify_delivery.py`，退出码为 0 且输出 `ok: true` 即交付完成。

## 7. 异常处理记录

- 附件 1 只给出 0—14400 s 的烘房工况。问题 2、3 的恒温干燥阶段缺少 4 h 之后的实测工况，
  按题面“预热平衡与恒温干燥阶段参数有所不同”的说明，取附件 1 末值（50.165 ℃、
  0.04986 kg/kg）作为恒温干燥阶段的恒定工况，并在论文假设中显式标注。
- 附件 2 只给出每隔 1800 s 的药材半径。连续收缩曲线用单调保形插值重建，不使用外推。
- 绘图链路中 Draw.io CLI 在继承 Node 运行时环境变量时无法解析导出参数，运行时清除该
  环境变量并追加无沙箱、禁用 GPU 参数，导出结果与官方 CLI 一致。

## 8. 外部新增数据

无。全部数据来自赛题附件 1、附件 2 与附件 3，未引入任何外部数据。

## 9. 外部文献

见 `文献/source_map.md`。仅使用可核验的公开文献，用于支撑热湿耦合传递方程、圆柱
一维径向扩散解析解、收缩介质中的移动边界处理与模型参数辨识思路。
