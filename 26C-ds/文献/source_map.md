# 文献来源映射（文献/source_map.md）

本文件登记本项目实际查阅并用于建模或写作的文献，逐条给出来源链接、可信等级与支撑章节。
文献按三类分流：

- 学术/技术证据：领域论文、方法原始论文、与题目直接相关的技术标准、官方数据源。可进入最终 `thebibliography`，且必须被正文真实引用。
- 内部学习资料：通用数学建模教材与一般性方法读物。只作内部参考，不进入 `thebibliography`。
- 合规资料：赛事论文格式规范、模板说明与参赛规则。只作格式依据，不进入 `thebibliography`。

## 一、赛题直接引用文献（学术证据）

### L1. Glomb K, Cabral J, Cattani A, Mazzoni A, Raj A, Franceschiello B. Computational models in electroencephalography. Brain Topography, 2022, 35: 142–161.

- 来源链接：https://doi.org/10.1007/s10548-021-00828-2
- 可信等级：高（同行评审综述，发表于 Brain Topography）
- 支撑内容：脑电计算模型的微观/介观/宏观尺度分类框架，以及从神经元活动到头皮观测的建模路线。
- 支撑章节：问题一模型假设与求解（去噪与响应提取的方法定位）、问题二模型建立与求解（多尺度机理链的层次划分）。
- 备注：该文献为赛题参考文献 [1]。

### L2. Steeghs-Turchina M, Srinivasan R, Nunez P L, Nunez M D. Slow wave dynamics of scalp EEG can be explained by simple statistical models of long-range connections. NeuroImage, 2025, 321: 121418.

- 来源链接：https://doi.org/10.1016/j.neuroimage.2025.121418
- 可信等级：高（同行评审研究论文，发表于 NeuroImage）
- 支撑内容：长程连接统计模型对头皮脑电慢波动力学的解释能力，用于支撑宏观层面连接结构的简化处理。
- 支撑章节：问题三模型建立与求解（宏观认知模型的连接结构设定与适用边界）。
- 备注：该文献为赛题参考文献 [2]。

### L3. Daume J, Kamiński J, Schjetnan A G P, et al. Control of working memory by phase–amplitude coupling of human hippocampal neurons. Nature, 2024, 629(8011): 393–401.

- 来源链接：https://doi.org/10.1038/s41586-024-07309-z
- 可信等级：高（同行评审研究论文，发表于 Nature）
- 支撑内容：人类海马神经元相位—幅度耦合对工作记忆的调控证据，为“记忆功能区向认知功能区提供对照信息”的建模假设提供神经生理学依据。
- 支撑章节：问题二模型建立与求解（皮层响应分布与特征表示的生理依据）、问题三模型建立与求解（海马体信号源项的引入依据）。
- 备注：该文献为赛题参考文献 [3]。

### L4. Acebrón J A, Bonilla L L, Pérez Vicente C J, Ritort F, Spigler R. The Kuramoto model: A simple paradigm for synchronization phenomena. Reviews of Modern Physics, 2005, 77(1): 137–185.

- 来源链接：https://doi.org/10.1103/RevModPhys.77.137
- 可信等级：高（同行评审综述，发表于 Reviews of Modern Physics）
- 支撑内容：藏本模型方程、序参数定义及其同步度量性质，是宏观尺度模型与序参数计算的原始方法来源。
- 支撑章节：问题二模型建立与求解（宏观序参数与同步度量）、问题三模型建立与求解（认知宏观模型的同步项构造）。
- 备注：该文献为赛题参考文献 [4]。

### L5. Azzopardi G, Petkov N. Ventral-stream-like shape representation: from pixel intensity values to trainable object-selective COSFIRE models. Frontiers in Computational Neuroscience, 2014, 8: 80.

- 来源链接：https://doi.org/10.3389/fncom.2014.00080
- 可信等级：高（同行评审研究论文，发表于 Frontiers in Computational Neuroscience）
- 支撑内容：形状选择性神经元响应的可训练计算模型，说明“特定空间排列的特征组合”如何决定神经元响应强度，是左右三角刺激差异特征表示的直接方法依据。
- 支撑章节：问题二模型建立与求解（形状特征表示与左右刺激区分特征）。
- 备注：该文献为赛题参考文献 [5]。

## 二、方法原始文献（学术证据）

### L6. Hodgkin A L, Huxley A F. A quantitative description of membrane current and its application to conduction and excitation in nerve. The Journal of Physiology, 1952, 117(4): 500–544.

- 来源链接：https://doi.org/10.1113/jphysiol.1952.sp004764
- 可信等级：高（方法原始论文，诺贝尔奖工作）
- 支撑内容：动作电位产生的定量模型，是微观尺度神经元电活动的原始理论来源。
- 支撑章节：问题二模型建立与求解（微观—介观跨尺度耦合的生理基础）。

### L7. Wilson H R, Cowan J D. Excitatory and inhibitory interactions in localized populations of model neurons. Biophysical Journal, 1972, 12(1): 1–24.

- 来源链接：https://doi.org/10.1016/S0006-3495(72)86068-5
- 可信等级：高（方法原始论文）
- 支撑内容：兴奋—抑制神经集群平均场方程与 sigmoid 传递函数，是介观尺度模型的原始方法来源。
- 支撑章节：问题二模型建立与求解（皮层响应神经元群的介观建模）。

### L8. Delorme A, Makeig S. EEGLAB: an open source toolbox for analysis of single-trial EEG dynamics including independent component analysis. Journal of Neuroscience Methods, 2004, 134(1): 9–21.

- 来源链接：https://doi.org/10.1016/j.jneumeth.2003.10.009
- 可信等级：高（方法原始论文，被广泛引用的脑电处理标准工具）
- 支撑内容：单试次脑电动力学分析与独立成分分析的标准处理流程，用于说明伪影分离与保留任务相关成分的处理口径。
- 支撑章节：问题一模型建立与求解（降噪方法设计与对照方案选择）。

### L9. Makeig S, Westerfield M, Jung T P, et al. Functionally independent components of the late positive event-related potential during visual spatial attention. The Journal of Neuroscience, 1999, 19(7): 2665–2680.

- 来源链接：https://doi.org/10.1523/JNEUROSCI.19-07-02665.1999
- 可信等级：高（同行评审研究论文）
- 支撑内容：视觉空间注意条件下晚期正向事件相关电位的功能独立成分分解，说明 P300 成分可由多个功能独立源叠加而成。
- 支撑章节：问题一模型建立与求解（P300 波形重构与成分保留依据）。

### L10. Polich J. Updating P300: an integrative theory of P3a and P3b. Clinical Neurophysiology, 2007, 118(10): 2128–2148.

- 来源链接：https://doi.org/10.1016/j.clinph.2007.04.019
- 可信等级：高（同行评审综述，P300 领域权威综述）
- 支撑内容：P300（P3a/P3b）的潜伏期范围、头皮分布与产生机制，为 250–500 ms 时间窗设定与中央—顶区正性成分的识别提供标准依据。
- 支撑章节：问题一模型建立与求解（有效视觉响应提取的时间窗与判据）。

### L11. Blankertz B, Lemm S, Treder M, Haufe S, Müller K R. Single-trial analysis and classification of ERP components — a tutorial. NeuroImage, 2011, 56(2): 814–825.

- 来源链接：https://doi.org/10.1016/j.neuroimage.2010.06.048
- 可信等级：高（同行评审教程论文）
- 支撑内容：单试次事件相关电位成分的分析与分类方法，包括判别式特征提取与交叉验证评估口径。
- 支撑章节：问题二模型建立与求解（左右刺激区分特征的可分性评估）。

### L12. Lopes da Silva F H. EEG and MEG: relevance to neuroscience. Neuron, 2013, 80(5): 1112–1128.

- 来源链接：https://doi.org/10.1016/j.neuron.2013.10.017
- 可信等级：高（同行评审综述，发表于 Neuron）
- 支撑内容：皮层偶极层与容积传导对头皮电位的影响，说明头皮观测是大量神经元群同步活动的宏观汇集。
- 支撑章节：问题二模型建立与求解（从皮层源到头皮观测的机理链）、问题三模型建立与求解（观测算子的物理含义）。

### L13. Nunez P L, Srinivasan R. Electric fields of the brain: the neurophysics of EEG. 2nd ed. Oxford University Press, 2006.

- 来源链接：https://doi.org/10.1093/acprof:oso/9780195050387.001.0001
- 可信等级：高（领域权威专著）
- 支撑内容：脑电正问题的物理基础、空间平均效应与参考电极影响，用于说明前额三导观测的空间低通性质。
- 支撑章节：问题二模型建立与求解（空间分布到头皮观测的映射）、模型总结与评价（观测受限带来的局限）。

### L14. Tibshirani R. Regression shrinkage and selection via the lasso. Journal of the Royal Statistical Society: Series B, 1996, 58(1): 267–288.

- 来源链接：https://doi.org/10.1111/j.2517-6161.1996.tb02080.x
- 可信等级：高（方法原始论文）
- 支撑内容：L1 正则化稀疏回归，用于在有限试次下选择少量稳定特征并抑制过拟合。
- 支撑章节：问题二模型建立与求解（左右差异特征筛选）、问题三模型建立与求解（认知模型参数估计的正则化）。

### L15. Efron B, Tibshirani R. An introduction to the bootstrap. Chapman & Hall/CRC, 1993.

- 来源链接：https://doi.org/10.1201/9780429246593
- 可信等级：高（方法经典专著）
- 支撑内容：自助重采样与置信区间构造，用于报告响应幅值、潜伏期与分类指标的区间估计。
- 支撑章节：问题一模型建立与求解（响应曲线与特征的不确定性量化）、问题三模型建立与求解（模型参数置信区间）。

### L16. Harris C R, Millman K J, van der Walt S J, et al. Array programming with NumPy. Nature, 2020, 585: 357–362.

- 来源链接：https://doi.org/10.1038/s41586-020-2649-2
- 可信等级：高（同行评审工具论文）
- 支撑内容：本项目数值计算的底层数组实现依据。
- 支撑章节：问题一至问题三模型建立与求解（计算实现口径）。

### L17. Virtanen P, Gommers R, Oliphant T E, et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. Nature Methods, 2020, 17: 261–272.

- 来源链接：https://doi.org/10.1038/s41592-019-0686-2
- 可信等级：高（同行评审工具论文）
- 支撑内容：本项目信号滤波、优化与统计检验所用算法的实现依据。
- 支撑章节：问题一至问题三模型建立与求解（信号处理与参数优化实现口径）。

### L18. Hunter J D. Matplotlib: a 2D graphics environment. Computing in Science & Engineering, 2007, 9(3): 90–95.

- 来源链接：https://doi.org/10.1109/MCSE.2007.55
- 可信等级：高（同行评审工具论文）
- 支撑内容：本项目论文图表的绘制环境依据。
- 支撑章节：问题一至问题三模型建立与求解（图表生成口径）。

### L19. Gramfort A, Luessi M, Larson E, et al. MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience, 2013, 7: 267.

- 来源链接：https://doi.org/10.3389/fnins.2013.00267
- 可信等级：高（同行评审工具论文）
- 支撑内容：脑电分段、基线校正与事件相关电位平均的标准实现口径。
- 支撑章节：问题一模型建立与求解（分段与基线校正流程）。

### L20. Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and powerful approach to multiple testing. Journal of the Royal Statistical Society: Series B, 1995, 57(1): 289–300.

- 来源链接：https://doi.org/10.1111/j.2517-6161.1995.tb02031.x
- 可信等级：高（方法原始论文）
- 支撑内容：多重比较的错误发现率控制，用于通道×时间点大量比较下筛选真实响应。
- 支撑章节：问题一模型建立与求解（有效响应显著性筛选）。

## 三、内部学习资料（不进入 thebibliography）

### I1. 通用数学建模方法与写作读物

- 用途：仅用于内部梳理建模流程与写作结构，不作为论文证据。
- 处理：不写入 `thebibliography`，正文不引用。

## 四、合规资料（不进入 thebibliography）

### C1. 2026 中国研究生数学建模竞赛论文格式规范与 GMCMthesis 模板说明

- 用途：论文格式、页数上限、摘要页数、章节结构、参考文献与附录排版的合规依据。
- 处理：不写入 `thebibliography`，正文不引用。

### C2. 2026 中国研究生数学建模竞赛 C 题题面与附录实验说明

- 用途：实验设计、通道语义、采集点位与建模问题的唯一题面依据。
- 处理：作为题面依据在正文中直接说明，不写入 `thebibliography`。

## 五、检索记录

- 赛题直接引用文献（L1–L5）由题面参考文献列表给定，已逐条核实标题、期刊、年份与 DOI。
- 方法原始文献（L6–L20）按“方法首次提出者优先、同行评审综述次之、工具论文补充实现口径”的原则选取，每条均对应本项目实际使用的方法或工具。
- 本项目未使用任何无法核验来源的文献，未编造引用。
