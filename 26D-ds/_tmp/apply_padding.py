# -*- coding: utf-8 -*-
"""为五张图设置四周留白（使主体内容约占页面高度/宽度 80%）。"""
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")

MAP = {
    "技术路线图": (115, 54),
    "问题分析流程图": (155, 94),
    "运输中继协同调度框架图": (155, 54),
    "组批求解流程图": (155, 68),
    "任务分区评估流程图": (155, 91),
}
OLD = "padding:20px 24px;background:transparent"

for n, (px, py) in MAP.items():
    f = "手绘图/%s.html" % n
    t = io.open(f, encoding="utf-8").read()
    if OLD not in t:
        print("!! %s 未找到原 padding 片段" % n)
        continue
    new = "padding:%dpx %dpx;background:transparent" % (py, px)
    t = t.replace(OLD, new)
    io.open(f, "w", encoding="utf-8", newline="").write(t)
    print("%-14s -> padding:%dpx %dpx" % (n, py, px))
