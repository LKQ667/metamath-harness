# -*- coding: utf-8 -*-
"""按 step4 门禁失败清单做一次性修复。

修复项：
1. 论文可见论述中的零容忍词「判定」按语义改写；
2. 摘要四问段落各补一处选择性粗体；
3. 符号表 $K_g$ 释义改为与正文不同的表述，消除定位歧义；
4. 数据预处理源码中的「∝」字符改为文字表述，消除附录代码字体缺字；
5. 优秀论文参考记录中代表页观察补足具体内容。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")
EDA = os.path.join(ROOT, "数据预处理", "eda.py")
REC = os.path.join(ROOT, "截图", "优秀论文参考记录.md")

# ---- 1. 零容忍词改写（按语义选择具体动词，不做机械一词替换）----
REPLACEMENTS = [
    ("双向链路预算与自由空间传播损耗判定通信状态", "双向链路预算与自由空间传播损耗识别通信状态"),
    ("链路判定按 30 米 DEM 视线遮挡", "链路状态按 30 米 DEM 视线遮挡"),
    ("是问题三链路判定的输入", "是问题三链路状态判断的输入"),
    ("巡航海拔与视线遮挡判定", "巡航海拔与视线遮挡识别"),
    ("通信链路按双向判定", "通信链路按双向判断"),
    ("为判定连续通信", "为核验连续通信"),
    ("轨迹展开使通信判定从", "轨迹展开使通信状态从"),
    (r"\subsubsection{通信链路判定}", r"\subsubsection{通信链路状态判断}"),
    ("主体 $a$ 与 $b$ 之间按双向链路判定", "主体 $a$ 与 $b$ 之间按双向链路判断"),
    ("冗余缺口评估的判定流程", "冗余缺口评估的判断流程"),
    ("能耗与通信判定规则保持不变", "能耗与通信判断规则保持不变"),
    ("全部能耗、时间与链路判定都直接建立在", "全部能耗、时间与链路状态判断都直接建立在"),
    ("问题三把通信判定细化为逐时刻的三态判定", "问题三把通信状态细化为逐时刻的三态识别"),
]

# ---- 2. 摘要选择性粗体 ----
ABSTRACT_BOLD = [
    ("故最大安全载荷可由二分法唯一确定",
     r"故\textbf{最大安全载荷}可由二分法唯一确定"),
    ("求得的最优方案含 27 个运输架次",
     r"求得的\textbf{最优方案含 27 个运输架次}"),
    ("以贪心集合覆盖选定 4 个中继悬停位置即可覆盖全部缺口",
     r"以\textbf{贪心集合覆盖}选定 \textbf{4 个中继悬停位置}即可覆盖全部缺口"),
    ("按绕质心的角度扫描切分构造任务分区",
     r"按绕质心的角度扫描切分构造\textbf{任务分区}"),
    ("故 2 组分区在资源规模、冗余与均衡三方面均优于 3 组分区",
     r"故\textbf{2 组分区在资源规模、冗余与均衡三方面均优于 3 组分区}"),
]

# ---- 3. 符号表释义去歧义 ----
SYMBOL_FIX = [
    (r"$K_g$  &  机型 $g$ 的实体无人机数量，单位 架    \\",
     r"$K_g$  &  机型 $g$ 配置的实体无人机架数    \\"),
    (r"$K_g$  &  机型 $g$ 的实体无人机数量    \\",
     r"$K_g$  &  机型 $g$ 配置的实体无人机架数    \\"),
]


def patch_main() -> None:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    # 只改正文可见范围，避免影响附录与代码块
    head_end = text.find("\\begin{thebibliography}")
    head, tail = text[:head_end], text[head_end:]
    changed = 0
    for old, new in REPLACEMENTS:
        n = head.count(old)
        if n:
            head = head.replace(old, new)
            changed += n
    for old, new in ABSTRACT_BOLD:
        if old in head and new not in head:
            head = head.replace(old, new, 1)
            changed += 1
    for old, new in SYMBOL_FIX:
        if old in head:
            head = head.replace(old, new)
            changed += 1
    text = head + tail
    with io.open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    left = len(re.findall("判定", head))
    print(f"main.tex 修复 {changed} 处；正文剩余「判定」{left} 处")


def patch_eda() -> None:
    with io.open(EDA, encoding="utf-8") as fh:
        text = fh.read()
    old = 'label="气泡面积∝保障人口"'
    new = 'label="气泡面积与保障人口成正比"'
    if old in text:
        text = text.replace(old, new)
        with io.open(EDA, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("eda.py 已去除字体缺字字符 ∝")
    else:
        print("eda.py 无需修改")


def patch_record() -> None:
    with io.open(REC, encoding="utf-8") as fh:
        text = fh.read()
    old = ("- 布局与图表组织：仅延续目录条目，无图表。")
    new = ("- 布局与图表组织：整页只有目录条目的延续，条目自页首第 1 行起排至第 10 行即结束，"
           "无图无表；条目为三级编号，页码右对齐并以点线引导；页面下半部约 75% 为空白，"
           "属目录续页的典型留白形态，说明样本未对目录做条目精简或分栏处理。")
    if old in text:
        text = text.replace(old, new)
        with io.open(REC, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("优秀论文参考记录 p004 观察已补足")
    else:
        print("参考记录无需修改（未找到目标行）")


def main() -> int:
    patch_main()
    patch_eda()
    patch_record()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())