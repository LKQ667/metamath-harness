# 文献来源映射（文献/source_map.md）

本文件按“学术/技术证据”“内部学习资料”“合规资料”三类分流登记文献，并写明来源链接、
可信等级、支撑内容与支撑章节。只有第一类可进入论文 `thebibliography`，且每条都必须被正文真实引用。

## 一、学术与技术证据（可进入最终参考文献）

| 编号 | 文献 | 来源链接 | 可信等级 | 支撑的事实、方法、参数或数据 | 支撑章节 |
|---|---|---|---|---|---|
| R1 | 新华社. 记者手记：抵近广西横州镇龙乡[EB/OL]. 2026-07-09 | https://www.xinhuanet.com/politics/20260709/acf8e4b353304bb78007d8224f1cd2ef/c.html | 官方媒体现场报道 | 洪水、山体落石与道路塌方从多个方向阻断通行，核心受灾区域一度交通中断、通信不畅 | 问题重述（灾情背景） |
| R2 | 新华每日电讯. 三进“孤岛乡”[EB/OL]. 2026-07-12 | https://www.news.cn/local/20260712/8bd1f64af3124569b5cf4415fc013acd/c.html | 官方媒体后续报道 | 镇龙乡曾出现断路、断电、断网，全乡约 8000 人受困；大型无人机承担电力抢修材料运输，临时通信与应急供电设备用于恢复联络 | 问题重述（灾情背景与任务必要性） |
| R3 | Copernicus Data Space Ecosystem. Copernicus DEM—Global and European Digital Elevation Model[DB/OL]. DOI: 10.5270/ESA-c5d3d65 | https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM | 官方数据源 | 30 米 DEM 的来源与栅格语义，支撑高程插值、地形净空与视线遮挡判定 | 数据预处理；问题一航段几何；问题三通信遮挡 |
| R4 | Dorling K, Heinrichs J, Messier G G, et al. Vehicle Routing Problems for Drone Delivery[J]. IEEE Transactions on Systems, Man, and Cybernetics: Systems, 2017, 47(1): 70-85. DOI: 10.1109/TSMC.2016.2582745 | https://ieeexplore.ieee.org/document/7513397 | SCI 期刊论文 | 多架次无人机配送的车辆路径建模框架；载荷与电池质量对能耗近似线性影响，支撑多点多架次调度的建模思路与载荷—能耗耦合关系 | 问题二模型建立与求解（调度模型结构） |
| R5 | Zhang J, Campbell J F, Sweeney D C, et al. Energy Consumption Models for Delivery Drones: A Comparison and Assessment[J]. Transportation Research Part D: Transport and Environment, 2021, 90: 102668. DOI: 10.1016/j.trd.2020.102668 | https://profiles.umsl.edu/en/publications/energy-consumption-models-for-delivery-drones-a-comparison-and-as | SCI 期刊论文 | 配送无人机能耗模型的统一比较框架，说明水平巡航能耗与爬升附加能耗分离计算的合理性，支撑航段能耗分解口径 | 问题一能耗模型；问题二能耗与返航余量约束 |
| R6 | International Telecommunication Union. Recommendation ITU-R P.525-5: Calculation of Free-Space Attenuation[S/OL]. 2024 | https://www.itu.int/rec/R-REC-P.525-5-202411-I/en | 国际标准建议书 | 自由空间基本传输损耗的计算式（含频率与距离的对数项），支撑链路预算与传播损耗计算 | 问题三通信链路判定 |
| R7 | Texas Instruments. Li-Ion Battery Charger Solution Using an MSP430 MCU[EB/OL] | https://www.ti.com/lit/an/slaa287b/slaa287b.pdf | 厂商技术应用报告 | 锂离子电池恒流—恒压两阶段充电规律，支撑快速阶段与慢速阶段按 SOC 增量线性折算的等效充电模型 | 问题二电池周转；问题三能源组件周转 |
| R8 | Zeng Y, Zhang R, Lim T J. Wireless Communications with Unmanned Aerial Vehicles: Opportunities and Challenges[J]. IEEE Communications Magazine, 2016, 54(5): 36-42. DOI: 10.1109/MCOM.2016.7470933 | https://ieeexplore.ieee.org/document/7470933 | SCI 期刊论文 | 无人机空中中继的链路结构与悬停位置对覆盖的影响，支撑“运输无人机—中继无人机—网关”两段链路与悬停位置优化 | 问题三中继位置与服务时段 |
| R9 | DJI Enterprise. Matrice 350 RTK Specifications[EB/OL] | https://enterprise.dji.com/matrice-350-rtk/specs | 厂商官方规格 | 多旋翼运输无人机的载质量、航时与爬升下降速度量级，支撑机型参数量级的合理性核对 | 数据预处理（参数量级核对） |
| R10 | Doodle Labs. Sense: Interference Avoidance[EB/OL] | https://doodlelabs.com/news/sense-interference-avoidance-release/ | 厂商技术资料 | 无线链路抗干扰与衰落裕量的工程取值背景，支撑接收门限中衰落裕量的设置依据 | 问题三接收门限 |

## 二、内部学习资料（不进入最终参考文献）

| 资料 | 用途 | 说明 |
|---|---|---|
| 数学建模常用优化与启发式方法教材内容 | 仅作为算法实现的内部参考，帮助确认禁忌搜索、局部搜索与装箱问题的标准处理方式 | 通用教材类内容，不作为文后条目，正文不引用 |

## 三、合规资料（不进入最终参考文献）

| 资料 | 用途 | 说明 |
|---|---|---|
| 中国研究生数学建模竞赛论文格式规范与 GMCMthesis 模板说明 | 论文排版、摘要页约束、参考文献样式与附录组织的合规依据 | 赛事规范类内容，不作为文后条目 |
| 赛题原文与附录 1 至附录 3 | 统一物理规则、单位、对象编号与计算口径的最高依据 | 赛题材料，不作为文后条目，正文以“题目附录”方式说明 |

## 四、参考文献使用纪律

- 每条最终参考文献都能指出其支撑的事实、方法、参数或数据及所在章节，不为凑数量增加条目。
- 正文引用一律使用与文后条目真实关联的引用命令，并在引用处显示为右上角数字角标。
- 未实际支撑正文论断的文献不得进入 `thebibliography`。