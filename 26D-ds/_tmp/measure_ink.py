# -*- coding: utf-8 -*-
"""测量每张 PDF 的墨迹包围盒占页面比例（用于核对"主体内容占页面高度 55%~80%，四周留白"）。"""
import sys

import fitz

sys.stdout.reconfigure(encoding="utf-8")

NAMES = ["技术路线图", "问题分析流程图", "运输中继协同调度框架图", "组批求解流程图", "任务分区评估流程图"]

for n in NAMES:
    d = fitz.open("手绘图/%s.pdf" % n)
    p = d[0]
    x0 = y0 = 1e9
    x1 = y1 = -1e9
    for b in p.get_text("blocks"):
        bx0, by0, bx1, by1 = b[:4]
        x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
    for dr in p.get_drawings():
        r = dr["rect"]
        x0, y0, x1, y1 = min(x0, r.x0), min(y0, r.y0), max(x1, r.x1), max(y1, r.y1)
    W, H = p.rect.width, p.rect.height
    print(
        "%-14s page=%6.1fx%6.1f  ink=%6.1fx%6.1f  W%%=%5.1f  H%%=%5.1f  aspect=%.2f"
        % (n, W, H, x1 - x0, y1 - y0, (x1 - x0) / W * 100, (y1 - y0) / H * 100, W / H)
    )
