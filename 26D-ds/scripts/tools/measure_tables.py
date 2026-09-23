# -*- coding: utf-8 -*-
"""逐页测量表格边框的横向范围，找出超出页面可用宽度的表格。

用法：python scripts/tools/measure_tables.py
"""
import os
import sys

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF = os.path.join(ROOT, "论文", "main.pdf")


def main() -> int:
    doc = fitz.open(PDF)
    page_w = doc[0].rect.width
    # 正文文本块左右边界（取全篇最常见范围作为可用宽度参考）
    print(f"页面宽度 {page_w:.1f} pt")
    bad = []
    for pno in range(1, doc.page_count + 1):
        page = doc[pno - 1]
        rects = [d["rect"] for d in page.get_drawings()]
        if not rects:
            continue
        # 只看明显的表格框：宽度大于 200pt 的矩形
        wide = [r for r in rects if (r.x1 - r.x0) > 200]
        if not wide:
            continue
        x1 = max(r.x1 for r in wide)
        if x1 > page_w - 20:
            text = page.get_text().strip().splitlines()
            head = next((ln for ln in text if "表" in ln and len(ln) < 60), "")
            bad.append((pno, round(x1, 1), head))
    if not bad:
        print("未发现超出页面的表格")
    for pno, x1, head in bad:
        print(f"  第 {pno} 页：表格右边界 {x1} pt（超出安全边距）  {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())