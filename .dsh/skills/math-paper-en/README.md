# math-paper-en

美赛 MCM/ICM 英语赛道全自动数学建模技能，合并问题分析、建模、编程、对抗复核、英文论文写作与 COMAP 排版编译为一条 step0-step5 主线，项目契约与 math-paper-cn 一致。

## 与其他技能的关系

- 结构基座: math-paper-cn（阶段流程、目录契约、门禁机制）。
- 内容来源: 英语赛道本体技能，即 comp-prob-analysis、comp-modeling、comp-code、comp-review、comp-paper-en、comp-paper-en-docx、comp-compile-en 七个技能合并为一条主线。
- 与 math-paper-cn 的差异: 交付物全英文、COMAP 章节与页数契约、Summary Sheet 规则、逐问图型多样性硬规则。

## 目录

| 路径 | 说明 |
|---|---|
| `SKILL.md` | 主技能入口与总原则 |
| `references/comap-format.md` | COMAP 结构、页数、Summary、附录契约 |
| `references/prose-style-en.md` | 英文文风与加粗规则 |
| `references/py-chart-selection.md` | 逐问图型分配与多样性硬规则 |
| `references/py-template-recipes.md` | 28 个绘图模板清单与 manifest 范式 |
| `references/auto-checklist.md` | step0 到 step5 执行清单 |
| `references/py-palette-export.md`、`visual-style.md` | 配色、字号与导出规范 |
| `references/workflow.md`、`drawing-pipeline.md`、`latex-bootstrap.md` | 分阶段、绘图链路与 LaTeX 自举 |
| `assets/templates/main.tex` | COMAP 英文主模板 |
| `assets/templates/py-figures/` | 27 个数据图模板与 1 个流程图模板 |
| `scripts/checks/` | 阶段门禁与 39 项检查 |
| `scripts/plotting/` | 绘图核心与模板注册表 |

## 关键约束

1. 论文正文、Summary Sheet、图表、图注、附录全部英文，main.tex 不得出现中文字符。
2. Summary Sheet 独占第 1 页，不少于 320 词；正文不少于 12 页；全文不超过 25 页。
3. 每一问的 Python 图型必须互不相同，热力图与柱状图全文各最多 1 张。
4. 交付前必须通过 step0 到 step5 门禁与 `verify_delivery.py`。