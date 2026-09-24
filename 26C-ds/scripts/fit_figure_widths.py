"""按 手绘图/*.pdf 的真实长宽比规整论文中的插图宽度。

运行：python scripts/fit_figure_widths.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import re
import sys
from pathlib import Path

import fitz

PROJECT = Path(__file__).resolve().parents[1]
TEX = PROJECT / "论文" / "main.tex"
HAND = PROJECT / "手绘图"

TEXTWIDTH_MM = 160.0
TEXTHEIGHT_MM = 232.0
MAX_HEIGHT_MM = 78.0


def suggest(ratio: float) -> float:
    """返回 \textwidth 的倍数，使插图高度不超过上限且尽量占满宽度。"""
    width_mm = min(TEXTWIDTH_MM, MAX_HEIGHT_MM * ratio)
    factor = width_mm / TEXTWIDTH_MM
    for candidate in (0.98, 0.92, 0.86, 0.80, 0.74, 0.68, 0.62, 0.56, 0.50, 0.44):
        if candidate <= factor + 0.02:
            return candidate
    return 0.40


def main() -> int:
    text = TEX.read_text(encoding="utf-8")
    rows = []
    for pdf in sorted(HAND.glob("fig_*.pdf")):
        doc = fitz.open(pdf)
        rect = doc[0].rect
        doc.close()
        ratio = rect.width / rect.height
        factor = suggest(ratio)
        rows.append((pdf.stem, ratio, factor, rect.width, rect.height))
        pattern = re.compile(
            r"(\\includegraphics\[width=)[0-9.]+(\\textwidth\]\{" + re.escape(pdf.stem) + r"\.pdf\})")
        text, count = pattern.subn(lambda m: f"{m.group(1)}{factor:.2f}{m.group(2)}", text)
        if count == 0:
            print(f"未在论文中找到 {pdf.stem}.pdf 的插图命令")
    TEX.write_text(text, encoding="utf-8")
    print(f"{'图名':<34}{'宽高比':>8}{'宽度系数':>10}{'插入宽/mm':>11}{'插入高/mm':>11}")
    for name, ratio, factor, w, h in rows:
        print(f"{name:<34}{ratio:>8.2f}{factor:>10.2f}{factor * TEXTWIDTH_MM:>11.1f}"
              f"{factor * TEXTWIDTH_MM / ratio:>11.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
