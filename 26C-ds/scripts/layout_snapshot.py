"""论文排版截图自查：渲染代表页 PNG，用于人工核对版式与图件占比。

运行：python scripts/layout_snapshot.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sys
from pathlib import Path

import fitz

PROJECT = Path(__file__).resolve().parents[1]
PDF = PROJECT / "论文" / "main.pdf"
OUT = PROJECT / "检查结果" / "排版截图"

# 需要人工核对的代表页：封面、摘要、目录、各问正文与含大图的页
TARGETS = [1, 2, 3, 5, 8, 12, 16, 20, 24, 28, 32, 36, 37, 38, 42, 50, 60, 70]


def main() -> int:
    if not PDF.exists():
        print("缺少论文 PDF")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF)
    total = doc.page_count
    made = 0
    for page_no in TARGETS:
        if page_no > total:
            continue
        page = doc[page_no - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        path = OUT / f"p{page_no:03d}.png"
        pix.save(path)
        made += 1
    doc.close()
    print(f"已渲染 {made} 张代表页到 检查结果/排版截图/，论文总页数 {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
