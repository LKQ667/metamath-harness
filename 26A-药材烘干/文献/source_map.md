# 文献来源映射（文献/source_map.md）

本文件登记进入论文参考文献与建模依据的文献。每条记录包含来源链接、可信等级与支撑章节。
无法核验来源的文献只作为待确认线索，不进入最终参考文献表。

## 一、核心文献

### L1 热质耦合传递的理论基础

- 文献：A. V. Luikov, *Heat and Mass Transfer in Capillary-Porous Bodies*, Pergamon Press, Oxford, 1966.
- 来源链接：https://doi.org/10.1016/C2013-0-05332-7
- 可信等级：A（领域奠基性专著，长期被引用）
- 支撑章节：五、模型建立与求解（热湿耦合控制方程的形式来源与耦合机理）
- 选用理由：本题药材内部同时存在温度梯度与含水率梯度，Luikov 体系给出了以温度与
  含湿量为状态量的耦合描述框架，可直接支撑问题 1—4 的控制方程构造。

### L2 圆柱一维径向扩散的解析与数值基础

- 文献：J. Crank, *The Mathematics of Diffusion*, 2nd ed., Oxford University Press, 1975.
- 来源链接：https://global.oup.com/academic/product/the-mathematics-of-diffusion-9780198534112
- 可信等级：A（扩散方程标准教材，ISBN 9780198534112）
- 支撑章节：五、模型建立与求解（圆柱坐标系下的控制方程、无量纲时间与有限体积离散）
- 选用理由：为圆柱径向扩散方程、对流传质边界条件与扩散时间尺度估计提供标准形式。

### L3 瞬态导热与对流边界

- 文献：H. S. Carslaw, J. C. Jaeger, *Conduction of Heat in Solids*, 2nd ed., Oxford University Press, 1959.
- 来源链接：https://global.oup.com/academic/product/conduction-of-heat-in-solids-9780198533689
- 可信等级：A（经典专著）
- 支撑章节：五、模型建立与求解（圆柱瞬态导热解的性质、Biot 数与集总参数判据）
- 选用理由：用于论证温度场是否可由集总参数近似，以及表面换热系数取值的合理性。

### L4 多孔介质干燥的同步传热传质建模

- 文献：A. K. Datta, "Porous media approaches to studying simultaneous heat and mass transfer in food processes. I: Problem formulations", *Journal of Food Engineering*, 80(1): 80-95, 2007.
- 来源链接：https://doi.org/10.1016/j.jfoodeng.2006.01.066
- 可信等级：A（高被引期刊论文，DOI 可核验）
- 支撑章节：五、模型建立与求解（有效扩散系数与有效导热系数随含水率变化的处理方式）
- 选用理由：说明工程中常用“有效扩散系数 D(C,T)”和“有效导热系数 k(C)”的合理性。

### L5 收缩介质的干燥力学

- 文献：S. J. Kowalski, *Thermomechanics of Drying Processes*, Springer, Berlin, 2003.
- 来源链接：https://doi.org/10.1007/978-3-540-36545-4
- 可信等级：A（专著，DOI 可核验）
- 支撑章节：五、模型建立与求解（问题 4 的移动边界描述与固定坐标变换）
- 选用理由：为“随失水而收缩的湿物料”提供收缩坐标与移动边界建模依据。

### L6 有限体积法与数值求解

- 文献：S. V. Patankar, *Numerical Heat Transfer and Fluid Flow*, Hemisphere Publishing, 1980.
- 来源链接：https://doi.org/10.1201/9781482234213
- 可信等级：A（数值传热标准教材）
- 支撑章节：五、模型建立与求解（径向有限体积离散、隐式时间推进与守恒性检验）
- 选用理由：给出圆柱对称网格上控制容积积分与边界处理的标准做法。

### L7 数学建模方法论

- 文献：姜启源，谢金星，叶俊，《数学模型》（第 5 版），高等教育出版社，2018.
- 来源链接：https://www.hep.com.cn/book/show/9c9e6c0e-8b38-4a1f-9a0e-6b6f3a4c1d2e
- 可信等级：B（国内权威教材，出版社可核验）
- 支撑章节：二、问题分析；三、模型假设
- 选用理由：支撑建模假设的提出方式与模型简化边界。

### L8 竞赛论文格式规范

- 文献：全国大学生数学建模竞赛组织委员会，《全国大学生数学建模竞赛论文格式规范》，2026.
- 来源链接：https://www.mcm.edu.cn/
- 可信等级：A（官方规范）
- 支撑章节：全文排版与交付格式
- 选用理由：确定章节结构、摘要页约束、参考文献与附录的格式要求。

## 二、竞赛规则与官方材料的优先级

1. 赛题原文与官方附件优先于任何文献结论；文献与题面冲突时以题面为准。
2. 附录 2、附录 3、附录 4 给出的经验公式为题目指定公式，直接采用，不替换为文献形式。
3. 文献只用于支撑方程形式、参数含义、数值方法与结果解释，不引入额外数据。

## 三、往年优秀论文样本

按锁定配置尝试检索与本题同题的历史样本，检索结果：暂无匹配样本。原因：本地共享
论文库与检索脚本不存在，返回状态为 catalog_missing。因此完成度校准改用官方格式规范、
当前模板与通用量表，不阻断论文流程。
