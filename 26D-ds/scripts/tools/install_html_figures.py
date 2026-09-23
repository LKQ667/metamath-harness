# -*- coding: utf-8 -*-
"""把经 QA 的 HTML 渲染结果安装为手绘图正式产物，并从 PDF 生成 2× 交付 PNG。

运行：python scripts/tools/install_html_figures.py
"""
from __future__ import annotations

import os
import shutil
import sys

import fitz  # PyMuPDF

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HAND = os.path.join(ROOT, "手绘图")
CHECK = os.path.join(HAND, "_render_check")
NAMES = ["技术路线图", "问题分析流程图", "运输中继协同调度框架图",
         "组批求解流程图", "任务分区评估流程图"]
SCALE = 192.0 / 72.0  # 规范要求的 ≈2× 交付倍率


def main() -> int:
    out = []
    for n in NAMES:
        src = os.path.join(CHECK, f"{n}.pdf")
        dst = os.path.join(HAND, f"{n}.pdf")
        if not os.path.isfile(src):
            print(f"跳过（无渲染结果）: {n}")
            continue
        shutil.copyfile(src, dst)
        doc = fitz.open(dst)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
        png = os.path.join(HAND, f"{n}.png")
        pix.save(png)
        doc.close()
        out.append({"name": n, "pdf": dst, "png": png,
                    "png_size": [pix.width, pix.height],
                    "pdf_bytes": os.path.getsize(dst)})
        print(f"{n}: PDF {os.path.getsize(dst)} B, PNG {pix.width}x{pix.height}")
    # 清理临时渲染目录
    shutil.rmtree(CHECK, ignore_errors=True)
    print("已清理临时渲染目录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())