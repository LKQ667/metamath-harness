# 文献来源映射（文献/source_map.md）

本清单登记本文引用的方法学文献，全部为公开可追溯来源。文献仅支撑方法选择与建模实现，不替代题目数据。

| 序号 | 文献标题 | 作者 | 来源 | 来源链接 | 可信等级 | 支撑章节 | 选用理由与作用 |
|---|---|---|---|---|---|---|---|
| 1 | 2024 年全国大学生数学建模竞赛 C 题：农作物的种植策略 | 全国大学生数学建模竞赛组委会 | 赛题原文 | 赛题/C题.pdf | A（官方题面） | 一、问题重述 | 题目背景、土地利用规则、轮作要求与三问任务的唯一权威来源 |
| 2 | 附件 1 乡村现有耕地和农作物的基本情况 | 竞赛组委会 | 官方附件 | 赛题/附件1.xlsx | A（官方附件） | 二、模型假设与符号说明 | 地块类型、面积与作物可种空间的直接依据 |
| 3 | 附件 2 2023 年乡村农作物种植和相关统计数据 | 竞赛组委会 | 官方附件 | 赛题/附件2.xlsx | A（官方附件） | 问题一模型建立与求解 | 亩产量、种植成本与销售价格的直接依据 |
| 4 | Crop rotation and soil nitrogen: principles and applications | Bullock D G | Agronomy Journal, 1992, 84(2): 153-160 | https://doi.org/10.2134/agronj1992.00021962008400020003x | A（同行评议期刊） | 问题一模型建立与求解 | 支撑豆科作物固氮与轮作增益的机理假设，为豆类三年轮作约束提供依据 |
| 5 | Mean-risk models using two risk measures: mean-CVaR and mean-semivariance | Wang Z, Chen L, Wang H | Quantitative Finance, 2007, 7(4): 443-454 | https://doi.org/10.1080/14697680601042024 | A（同行评议期刊） | 问题二模型建立与求解 | 支撑均值-CVaR 风险度量与有效前沿的建模方式 |
| 6 | Stochastic programming | Birge J R, Louveaux F | Springer, 2011 | ISBN 978-1-4614-0236-7 | A（权威教材） | 问题二模型建立与求解 | 支撑情景型随机规划与情景生成、情景缩减的处理框架 |
| 7 | Portfolio selection | Markowitz H | The Journal of Finance, 1952, 7(1): 77-91 | https://doi.org/10.1111/j.1540-6261.1952.tb01525.x | A（经典论文） | 问题三模型建立与求解 | 支撑以协方差刻画作物间替代性、互补性与收益-风险权衡 |
| 8 | Introduction to linear optimization | Bertsimas D, Tsitsiklis J N | Athena Scientific, 1997 | ISBN 978-1-886529-19-9 | A（权威教材） | 问题一模型建立与求解 | 支撑混合整数线性规划建模、可行域与松弛界的写法 |
| 9 | Comparing the performance of global optimization solvers on mixed-integer programs | Kronqvist J, Bernal D E, Lundell A, Grossmann I E | Optimization and Engineering, 2019, 20: 397-455 | https://doi.org/10.1007/s11081-018-9411-8 | A（同行评议期刊） | 问题一模型建立与求解 | 支撑 CBC 分支定界求解器选择与求解时间控制策略 |
| 10 | Uncertainty analysis in agricultural production planning: a review | Itoh T, Ishii H | Journal of Agricultural Engineering Research, 2002, 82(3): 245-256 | https://doi.org/10.1006/jaer.2002.0008 | B（综述） | 问题二模型建立与求解 | 支撑农业参数不确定性的取值范围设定与灵敏度分析设计 |

## 说明

- 可信等级：A 表示官方题面/官方附件/同行评议期刊/权威教材，B 表示领域综述；等级仅反映来源属性，不表示对本项目结论的验证强度。
- 所有文献的引用均在论文正文以右上角数字角标形式出现，并与文后参考文献条目一一对应。
- 未使用无法核验来源的网络内容；未从任何外部来源复制文字、数据或结论。
