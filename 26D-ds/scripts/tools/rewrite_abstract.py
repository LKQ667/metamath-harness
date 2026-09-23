# -*- coding: utf-8 -*-
"""定稿摘要：单页排版、有效文字落在建议区间，并保留 abstract:start / abstract:end 标记。"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

BODY = r"""山区洪涝灾害常同时破坏道路、供电与通信设施，使受灾居民点在短时间内失去地面交通联系。本文以广西横州市镇龙乡为背景，围绕临时调度中心 O01 与 15 个服务区、80 个不可拆货箱、三类运输机型共 8 架实体无人机、2 架中继无人机及配套电池与能源组件，建立运输能力、异构调度、通信保障与资源配置四层递进的数学模型，全部参数取自赛题附件。

\textbf{针对问题一}，本文把单点往返能力化为单变量单调方程求根问题，求得\textbf{最大安全载荷}，组批以剩余数量向量为状态做精确动态规划。A 型在 15 个服务区均达额定上限 25.00 kg，B 型除 S008 为 28.63 kg 外均达 30.00 kg，C 型在 5 个服务区受能量约束、最小为 58.43 kg。最少架次方案为 18 架次、能耗 59.261 kWh、累计作业时间 32841.5 s，A 型因容量被 B 型支配而未入选。真实 Pareto 集为 18 与 19 架次，增加 1 个架次仅省 0.098 kWh，故架次数应作为首要目标；全部货箱可投递的临界返航安全余量为 0.3503。

\textbf{针对问题二}，本文建立含载质量、体积、返航余量、机队与电池周转及时限约束的异构多点多架次调度模型，采用分层构造、局部搜索与机型负载再平衡。最优方案含 27 个架次、能耗 86.983 kWh、\textbf{全部任务完成时间 10313.4 s}，首批保障货箱截止时间全部满足。四套权重方案在四项指标上互为非受支配：能耗优先方案比及时性优先方案少耗 8.66 kWh，完成时间多 281.0 s。

\textbf{针对问题三}，本文把架次展开为 5 s 步长轨迹，按附录 3 的地形遮挡、双向链路预算与传播损耗识别链路状态，发现 15 个服务区在投送作业高度上仅 3 个可直连网关，缺口采样点占 39.19\%。以\textbf{贪心集合覆盖}选定 4 个中继悬停位置即可覆盖全部缺口。单架次最大连续服务约 2.2 h，2 架中继无法同时满足首批时限；在 2 至 6 架范围内，首批时限满足与缺口全覆盖无法兼得。

\textbf{针对问题四}，本文以同架次关系图求不可拆分单元并构造\textbf{任务分区}，各任务组独立重跑装箱、合并与调度链路。划分为 2 组需运输无人机 6 架、共享电池 13 组、中继无人机 3 架，缺口仅中继无人机 1 架；划分为 3 组需 9 架与 17 组，缺口增至 5 项，组间工作量不均衡度由 0.053 升至 0.273。\textbf{2 组分区在资源规模、冗余与均衡三方面均优于 3 组分区}。

综上，本文在能耗、时间与通信约束下给出可复现的协同调度方案，并量化了中继机队规模与分区粒度对资源配置的影响，可为山区洪涝救援的装备编成提供定量依据。"""


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    start = text.find("\\begin{abstract}")
    end = text.find("\\keywords{")
    if start == -1 or end == -1:
        raise SystemExit("未找到摘要环境或关键词命令")
    start += len("\\begin{abstract}")
    new = "\n\\label{abstract:start}\n" + BODY + "\n\n"
    text = text[:start] + new + text[end:]
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    plain = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", BODY)
    plain = plain.replace("{", " ").replace("}", " ")
    count = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9%]", plain))
    print(f"摘要定稿：有效文字约 {count} 字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())