# -*- coding: utf-8 -*-
"""列出 main.tex 中全部表格的标题、列格式与浮动选项，用于排查超宽与错位。"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN = os.path.join(ROOT, "论文", "main.tex")

TABLE_RE = re.compile(r"\\begin\{table\}(\[[^\]]*\])?")
CAP_RE = re.compile(r"\\caption\{([^{}]*)\}")
SPEC_RE = re.compile(r"\\begin\{tabular\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}")


def main() -> int:
    with io.open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    for m in TABLE_RE.finditer(text):
        seg = text[m.start():m.start() + 1200]
        cap = CAP_RE.search(seg)
        spec = SPEC_RE.search(seg)
        cols = 0
        if spec:
            body = spec.group(1)
            cols = len(re.findall(r"[clr]|p\{[^{}]*\}|X", body))
        print(f"浮动选项={m.group(1) or '无'}  列数={cols}  标题={cap.group(1) if cap else '?'}")
        print(f"    列格式: {spec.group(1) if spec else '?'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())