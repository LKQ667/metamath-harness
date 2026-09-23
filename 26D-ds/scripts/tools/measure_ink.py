# -*- coding: utf-8 -*-
"""用光栅化后的非白像素范围测量每页实际内容的左右边界，找出越界页。

用法：python scripts/tools/measure_ink.py
"""
import os

import fitz
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF = os.path.join(ROOT, "论文", "main.pdf")
DPI = 100


def main() -> int:
    doc = fitz.open(PDF)
    page_w = doc[0].rect.width
    scale = DPI / 72.0
    limit_right = page_w - 18  # 安全右边界（约 6 mm）
    print(f"页面宽度 {page_w:.1f} pt，安全右边界 {limit_right:.1f} pt")
    bad = []
    for pno in range(1, doc.page_count + 1):
        page = doc[pno - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        cols = np.where((arr < 235).any(axis=0))[0]
        if len(cols) == 0:
            continue
        right_pt = cols[-1] / scale
        if right_pt > limit_right:
            lines = [ln for ln in page.get_text().strip().splitlines() if ln.strip()]
            head = " / ".join(lines[:2])[:70]
            bad.append((pno, round(right_pt, 1), head))
    if not bad:
        print("所有页面内容均在安全边距内")
    for pno, right, head in bad:
        over = right - limit_right
        print(f"  第 {pno} 页：内容右边界 {right} pt，超出 {over:.1f} pt  | {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())