# 全自动执行清单 (math-paper-en)

## step0 初始化

1. 确认 output_dir 与 problem_path，建立 赛题/、文献/、数据预处理/、Q1..Qn/、论文/、摘要/、灵敏度分析/、手绘图/、figures/、results/、检查结果/。
2. 写 README.md、AGENT.md、data/source_map.md、文献/source_map.md、figures/manifest.json 与 项目状态.json。
3. 运行 `python "<技能目录>/scripts/checks/run_stage_gate.py" --project "<项目>" --init`，再运行 `--stage step0`。
4. 只做无网络 LaTeX 快速探测，缺 XeLaTeX 记录为延后安装。

## step1 数据与引入

1. 真实数据优先；无数据型赛题写明无数据依据。
2. 完成 EDA、清洗规则、派生数据与问题重述，写入 数据预处理/README.md。
3. 运行 `--stage step1`。

## step2 逐问建模

1. 每问写 Qn/README.md，覆盖目标、输入、假设、变量、公式、约束、方法、验证。
2. 输出模型骨架与详细推导，明确目标函数与约束来源。
3. 完成逐问图型分配并写入 figures/manifest.json，确保家族互不相同。
4. 运行 `--stage step2`。

## step3 代码与绘图

1. 每问保留主脚本、result.md 与本问 figures/。
2. 先按 manifest 分配调用 `choose_chart_family(..., used_families=...)`，再从 assets/templates/py-figures/ 取模板；禁止同家族跨问重复，热图与柱图最多各 1 张。
3. 每图导出 svg、pdf、png，补齐 qa 字段与 paper_ready。
4. 生成技术路线图或问题分析流程图，写入 手绘图/。
5. 数值结果统一写入 results/final_results.json。
6. 运行 `--stage step3`。

## step4 论文写作

1. Summary Sheet 独占第 1 页，不少于 320 词，For Problem N 与 Keywords 逐个加粗。
2. 正文只保留 7 个白名单主章节，图表入文并逐张解释。
3. 完成灵敏度分析、模型评价与引用角标；全文英文，无中文残留。
4. 运行 `--stage step4`。

## step5 排版交付

1. 编译 LaTeX，核对正文页数下限与 COMAP 25 页上限、附录另起页。
2. 附录为 Supporting Material Catalog 与 Appendix: Code，代码为净化副本且无注释。
3. 完成三轮自查并写入 检查结果/三轮自查.md。
4. 运行 `--stage step5`，再运行 `verify_delivery.py --project "<项目>"`，仅当 ok 为 true 才交付。