# 文献来源映射

本文件逐条登记本项目使用的文献：bibkey、题目、来源链接、可信等级、支撑章节，以及它在论文中
具体支撑的事实、方法、参数或数据。未在本表登记且未在正文真实引用的条目不得进入文后参考文献。

## 分流规则

- **学术与技术证据**（领域论文、方法原始论文、与题目直接相关的技术标准、官方数据源）：可进入最终
  `thebibliography`，且必须被正文真实引用，引用处必须能指出它支撑的方法、参数或数据。
- **通用数学建模教材**（含“数学模型”“数学建模”等书名或“第 N 版”“教材”标识）：属于内部学习资料，
  不进入文后参考文献。
- **赛事论文格式规范、模板说明与参赛规则**：属于合规资料，不进入文后参考文献。

## 一、赛题直接引用文献（题面参考文献，必读）

题面第五节给出的参考文献是命题人指定的直接相关文献，构成本项目方法选择的第一层依据。
以下条目均直接抄录自赛题原文，未做改写。

| bibkey | 题目 | 来源链接 | 可信等级 | 支撑章节 |
|---|---|---|---|---|
| zhang2024multimodal | Deep learning-based multimodal emotion recognition from audio, visual, and text modalities: A systematic review of recent advancements and future prospects | Expert Systems with Applications, 2024, 237: 121692 | A（领域系统综述） | 问题重述（研究现状与挑战）、问题一（三模态特征提取方法比较） |
| qiu2026hypergraph | Beyond Missing Modalities: Hypergraph Conditioned Diffusion for Uncertainty-Aware Multimodal Emotion Recognition | CVPR 2026 | A（CVPR 会议论文） | 问题二（缺失模态建模候选方法比较） |
| yang2026factorize | Factorize, Reconstruct, Enhance: A Unified Framework for Multimodal Sentiment Analysis | CVPR 2026 | A（CVPR 会议论文） | 问题二（模态重建思路） |
| zhuang2025cmad | CMAD: Correlation-Aware and Modalities-Aware Distillation for Multimodal Sentiment Analysis with Missing Modalities | ICCV 2025 | A（ICCV 会议论文） | 问题二（缺失模态下知识蒸馏对比方法） |
| zhu2025proxy | Proxy-Driven Robust Multimodal Sentiment Analysis with Incomplete Data | ACL 2025 | A（ACL 会议论文） | 问题二（不完整数据下的鲁棒表示） |
| mai2026invariant | Learning Invariant Modality Representation for Robust Multimodal Learning from a Causal Inference Perspective | ACL 2026 | A（ACL 会议论文） | 问题二（不变表示与因果视角）、问题三（模态作用程度的因果解释） |
| fang2025emoe | EMOE: Modality-Specific Enhanced Dynamic Emotion Experts | CVPR 2025 | A（CVPR 会议论文） | 问题二（模态专家网络对比）、问题三（模态作用差异） |
| wan2026locate | Locate and Explain: Joint Multimodal Emotion Cause Extraction and Summarization in Conversation | ACL 2026 | A（ACL 会议论文） | 问题三（关键证据定位与解释产出） |
| mai2026careflow | CaReFlow: Cyclic Adaptive Rectified Flow for Multimodal Fusion | CVPR 2026 | A（CVPR 会议论文） | 问题二（融合机制对比） |
| wang2025distill | 基于知识蒸馏与动态调整机制的多模态情感分析模型 | 计算机学报, 2025, 48(8): 1923-1942 | A（中文核心期刊） | 问题重述（国内研究现状）、问题二（动态权重融合对比） |

## 二、方法原始论文与技术标准（本项目补充，已核验可追溯）

| bibkey | 题目 | 来源链接 | 可信等级 | 支撑章节 |
|---|---|---|---|---|
| zadeh2018mosei | Multimodal Language Analysis in the Wild: CMU-MOSEI Dataset and Interpretable Dynamic Fusion Graph | [aclanthology.org/P18-1208](https://aclanthology.org/P18-1208) | A（ACL 2018，数据集与标签定义原始论文） | 问题一、问题二、问题三（数据来源、标注定义与评价口径依据） |
| tsai2019mult | Multimodal Transformer for Unaligned Multimodal Language Sequences | [aclanthology.org/P19-1656](https://aclanthology.org/P19-1656) | A（ACL 2019，跨模态时序对齐原始论文） | 问题一（跨模态时序对齐规则的方法来源）、问题二（对齐版与未对齐版一致性讨论） |
| baltrusaitis2019multimodal | Multimodal Machine Learning: A Survey and Taxonomy | [doi:10.1109/TPAMI.2018.2798607](https://doi.org/10.1109/TPAMI.2018.2798607) | A（IEEE TPAMI 综述） | 问题重述（多模态挑战分类）、问题一（对齐策略分类依据） |
| lin2023missmodal | MissModal: Increasing Robustness to Missing Modality in Multimodal Sentiment Analysis | [doi:10.1162/tacl_a_00628](https://doi.org/10.1162/tacl_a_00628) | A（TACL 2023，缺失模态鲁棒性原始研究） | 问题二（缺失模态鲁棒建模的对照方法） |
| liang2021multibench | MultiBench: Multiscale Benchmarks for Multimodal Representation Learning | [NeurIPS 2021](https://neurips.cc/virtual/2021/22755) | A（NeurIPS 2021 基准论文） | 问题二（评测协议与鲁棒性评测设计依据） |
| zadeh2017tfn | Tensor Fusion Network for Multimodal Sentiment Analysis | [aclanthology.org/D17-1115](https://aclanthology.org/D17-1115) | A（EMNLP 2017，张量融合原始论文） | 问题二（张量融合对比基线） |
| liu2018efficient | Efficient Low-rank Multimodal Fusion with Modality-Specific Factors | [aclanthology.org/P18-1209](https://aclanthology.org/P18-1209) | A（ACL 2018，低秩多模态融合原始论文） | 问题二（低秩融合对比基线） |
| vaswani2017attention | Attention Is All You Need | [doi:10.48550/arXiv.1706.03762](https://doi.org/10.48550/arXiv.1706.03762) | A（NeurIPS 2017，注意力机制原始论文） | 问题二（跨模态注意力融合的结构来源） |
| devlin2019bert | BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding | [doi:10.48550/arXiv.1810.04805](https://doi.org/10.48550/arXiv.1810.04805) | A（NAACL 2019，文本表示原始论文） | 问题一（文本语义表示的定义来源） |
| hochreiter1997lstm | Long Short-Term Memory | [doi:10.1162/neco.1997.9.8.1735](https://doi.org/10.1162/neco.1997.9.8.1735) | A（Neural Computation，时序建模原始论文） | 问题二（时序编码器结构来源） |
| ba2016layer | Layer Normalization | [doi:10.48550/arXiv.1607.06450](https://doi.org/10.48550/arXiv.1607.06450) | A（层归一化原始论文） | 问题二（训练稳定性措施依据） |
| kingma2015adam | Adam: A Method for Stochastic Optimization | [doi:10.48550/arXiv.1412.6980](https://doi.org/10.48550/arXiv.1412.6980) | A（ICLR 2015，优化器原始论文） | 问题二、问题三（优化算法与学习率设置依据） |
| srivastava2014dropout | Dropout: A Simple Way to Prevent Neural Networks from Overfitting | [JMLR 15:1929-1958](https://jmlr.org/papers/v15/srivastava14a.html) | A（JMLR，正则化原始论文） | 问题二（过拟合抑制措施依据） |
| lin2017focal | Focal Loss for Dense Object Detection | [doi:10.48550/arXiv.1708.02002](https://doi.org/10.48550/arXiv.1708.02002) | A（ICCV 2017，类别不平衡损失原始论文） | 问题二（类别不平衡下的目标函数设计依据） |
| breiman2001random | Random Forests | [doi:10.1023/A:1010933404324](https://doi.org/10.1023/A:1010933404324) | A（Machine Learning 期刊，集成学习原始论文） | 问题二、问题三（基线模型之一） |
| lundberg2017shap | A Unified Approach to Interpreting Model Predictions | [doi:10.48550/arXiv.1705.07874](https://doi.org/10.48550/arXiv.1705.07874) | A（NeurIPS 2017，加性归因原始论文） | 问题三（模态作用程度与加性归因的定义来源） |
| selvaraju2017gradcam | Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization | [doi:10.1109/ICCV.2017.74](https://doi.org/10.1109/ICCV.2017.74) | A（ICCV 2017，梯度定位原始论文） | 问题三（时序证据定位的方法来源） |
| sobol2001global | Global sensitivity indices for nonlinear mathematical models and their Monte Carlo estimates | [doi:10.1016/S0378-4754(00)00270-6](https://doi.org/10.1016/S0378-4754(00)00270-6) | A（Mathematics and Computers in Simulation，Sobol 指数原始论文） | 灵敏度分析（方差分解指标定义） |
| saltelli2010variance | Variance based sensitivity analysis of model output. Design and estimator for the total sensitivity index | [doi:10.1016/j.cpc.2009.09.018](https://doi.org/10.1016/j.cpc.2009.09.018) | A（Computer Physics Communications，总敏感度指数估计） | 灵敏度分析（估计器与采样方案） |
| fleiss1971measuring | Measuring nominal scale agreement among many raters | [doi:10.1037/h0031619](https://doi.org/10.1037/h0031619) | A（Psychological Bulletin，多评分者一致性原始论文） | 问题二、问题三（一致性度量与误差归因的统计依据） |
| harris2020array | Array programming with NumPy | [doi:10.1038/s41586-020-2649-2](https://doi.org/10.1038/s41586-020-2649-2) | A（Nature，数值计算库原始论文） | 全部问题（数值计算实现依据） |
| mckinney2010pandas | Data Structures for Statistical Computing in Python | [doi:10.25080/Majora-92bf1922-00a](https://doi.org/10.25080/Majora-92bf1922-00a) | A（SciPy 会议论文，数据分析库原始文献） | 全部问题（数据处理实现依据） |
| pedregosa2011scikit | Scikit-learn: Machine Learning in Python | [JMLR 12:2825-2830](https://jmlr.org/papers/v12/pedregosa11a.html) | A（JMLR，机器学习库原始论文） | 全部问题（实现工具与版本登记） |
| hunter2007matplotlib | Matplotlib: A 2D Graphics Environment | [doi:10.1109/MCSE.2007.55](https://doi.org/10.1109/MCSE.2007.55) | A（Computing in Science & Engineering，绘图库原始论文） | 全部问题（绘图实现依据） |
| mcfee2015librosa | librosa: Audio and Music Signal Analysis in Python | [doi:10.25080/Majora-7b98e3ed-003](https://doi.org/10.25080/Majora-7b98e3ed-003) | A（SciPy 会议论文，音频分析库原始文献） | 问题一（语音特征提取工具依据） |

## 三、内部学习资料（不进入文后参考文献）

- 通用数学建模方法与教材类资料：仅用于建模思路梳理与写作规范自查，不进入 `thebibliography`。

## 四、合规资料（不进入文后参考文献）

- 中国研究生数学建模竞赛论文格式规范、GMCMthesis 模板说明与参赛规则：仅作为排版与合规依据。

## 五、核对说明

- 程序只能核对来源信号（DOI/URL/标准号/出版社）是否存在；条目与论文章节的对应关系以本表登记与人工复核为准。
- 每条最终参考文献都必须能在正文中找到真实引用位置，且该处能说明它支撑了什么。
- 本表第一部分的 10 条直接抄录自赛题原文（题面第五节参考文献），未逐条附加 DOI；正文引用时以
  题面给出的期刊/会议与年份卷期为准，属于命题人指定来源，可追溯至赛题文件本身。
- 本表第二部分全部条目的 DOI、URL 或 JMLR 卷页号均已通过公开检索核对存在。
