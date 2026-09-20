# COMAP 论文结构与交付契约（美赛英语赛道）

本文件是 math-paper-en 的论文交付契约，论文内容组织、页数、Summary Sheet、章节、引用与附录都必须符合这里的规定；门禁检查 `scripts/checks/` 与之一一对应。

## 1. 交付物与语言

- 交付物为 `论文/main.tex` 编译出的 `论文/main.pdf`，语言为规范学术英文。
- `main.tex`、图表内文字、图注、坐标轴、图例、表格与附录全部英文；`main.tex` 不得出现中文字符，禁止加载 ctex、CJK、xeCJK、zhnumber 等中文宏包，必须使用 fontspec 显式设置英文主字体。
- 项目过程材料（README.md、Q*/result.md、项目状态.json、检查结果/、手绘图/ 提示词）允许中文，但不得混入论文正文。

## 2. 页数契约

| 项目 | 规则 |
|---|---|
| 第 1 页 | Summary Sheet 独占：标题、Summary 段落、Keywords 全部落在第 1 页 |
| 第 2 页 | 允许放 Table of Contents，目录必须与最终章节一致且不得为空 |
| 正文 | `\label{body:start}` 到 `\label{body:end}`，默认不少于 12 页，可用 `body_pages` 提高 |
| 全文 | 含 Summary Sheet、目录、参考文献与附录，不得超过 COMAP 25 页硬上限 |
| 附录 | `\label{appendix:start}` 必须另起一页，即 `appendix:start` 等于 `body:end` 加 1 |
| 总页数标记 | 模板在文末放置 `\label{paper:end}`，门禁据此核对 25 页上限 |

页数不足时只允许深化 Model Design and Solution：补变量定义、约束来源、推导链、适用条件、边界讨论、求解细节与结果解释。禁止新增主章节、堆砌套话、重复图表或扩写参考文献凑页数。页数超限时优先压缩重复解释、冗余表格与低价值图，不得删掉关键推导与验证。

## 3. Summary Sheet 规则

- 有效英文不少于 320 词，建议 400 到 520 词并尽量铺满第一页；不足时继续补信息密度，不得用空话填充。
- Summary 不出现公式、不出现引用角标、不出现未替换的占位文本。
- 每一问使用 `\paperstrong{For Problem N}` 只加粗标签短语，标签后的标点与正文不得进入同一粗体命令。
- Keywords 行使用 `{\keywordfont \paperstrong{Keywords:}}`，每个关键词分别加粗。
- `\label{abstract:end}` 必须放在 Keywords 之后，且编译后页码为 1。
- Summary 区禁止 `\newpage`、`\clearpage`、大段 `\vspace`、缩小字号、压缩行距或负间距。
## 4. 正文主章节白名单

模板内置且只允许以下主章节，禁止新增：

1. Introduction
2. Assumptions and Justifications
3. Notations
4. Model Design and Solution（允许派生小节：Model Design and Solution: Problem 2）
5. Sensitivity Analysis
6. Model Evaluation
7. Conclusions

参考文献与 Appendix: Code 不计入主章节白名单，但必须保留。禁止把候选方法比较、最终选择、体系结构、AI 痕迹检测、边界讨论、可复现性、运行顺序、方法论、整体发现、数据-结果回扣等作为独立 section；相关内容并入 Model Design and Solution、Conclusions 或放入 README、检查结果与附录说明。
## 5. 图表、公式与引用

- 每张入文图必须在 `figures/manifest.json` 中有条目，声明 `chart_family`、`question`、`source`、`exports`（svg、pdf、png）、`paper_ready` 与 `qa`。
- 图必须在正文中被引用和解释，禁止出现无解释的孤立图片；图注写在图下方，表注写在表上方。
- 图表文字、单位、图例全部英文；坐标轴必须有量与单位。
- 公式只给承担主链的少数关键式编号。同一逻辑单元的多行公式整组只保留一个编号，编号唯一、连续并位于右侧。
- 引用必须使用与文后条目真实关联的 `\cite` 系列命令，显示为右上角数字角标；禁止手写 `[1]`、手工编号或与文后条目失联的角标。
- 正文禁止出现内部文件路径与绝对路径；唯一例外是概念图提示词的相对路径，写作 `手绘图/*.md`。
## 6. 附录结构

- `\label{body:end}` 之后必须用 `\newpage` 或 `\clearpage` 另起一页，再放 `\label{appendix:start}` 与 `\begin{appendices}`。
- Supporting Material Catalog: 只列代码名称与重要 Excel 结果名称，允许 `.py` 与 `.xlsx` 后缀；禁止路径、目录写法与"见某文件夹"写法，且必须英文。
- Appendix: Code: 完整收录真实代码的净化副本，禁止代码围栏、标题符号、装饰分隔线、注释与连续大量空行。
## 7. 与门禁的对应关系

| 契约 | 对应检查 |
|---|---|
| Summary Sheet 独占第 1 页与词数 | `check_abstract_one_page.py` |
| 页数下限与 25 页上限 | `check_body_page_count_minimum.py` |
| 章节白名单 | `check_paper_section_whitelist.py` |
| 模板结构与英文全文 | `check_template_adherence.py` |
| Summary 与正文加粗 | `check_paper_emphasis.py` |
| 英文文风与括号密度 | `check_paper_prose_style.py` |
| Catalog 禁止路径 | `check_support_material_catalog.py` |
| 图型多样性与热力图、柱状图上限 | `check_figure_diversity.py` |