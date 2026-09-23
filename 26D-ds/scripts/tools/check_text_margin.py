# -*- coding: utf-8 -*-
"""逐行检查正文文本是否越出右文本边界，并列出越界行。

用法：python scripts/tools/check_text_margin.py
"""
import os

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF = os.path.join(ROOT, "论文", "main.pdf")


def main() -> int:
    doc = fitz.open(PDF)
    # 以全文所有行右端点的 98 分位作为正常右边界
    rights = []
    lines_by_page = {}
    for pno in range(1, doc.page_count + 1):
        page = doc[pno - 1]
        rows = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                txt = "".join(s["text"] for s in line["spans"]).strip()
                if txt:
                    rows.append((line["bbox"][2], txt))
        lines_by_page[pno] = rows
        rights.extend(r[0] for r in rows)
    rights.sort()
    normal = rights[int(len(rights) * 0.98)]
    limit = normal + 2.0
    print(f"正常右边界（98 分位） {normal:.1f} pt，判定阈值 {limit:.1f} pt")
    bad = 0
    for pno, rows in lines_by_page.items():
        for x1, txt in rows:
            if x1 > limit:
                bad += 1
                print(f"  第 {pno} 页 x1={x1:.1f} | {txt[:66]}")
    if not bad:
        print("未发现越出右文本边界的行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())