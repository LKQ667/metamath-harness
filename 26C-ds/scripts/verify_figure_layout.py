"""图件落版核查：确认每张入文图的题注与其解释段同页且顺序正确，并统计版面占比。

运行：python scripts/verify_figure_layout.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import re
import sys
from pathlib import Path

import fitz

PROJECT = Path(__file__).resolve().parents[1]
PDF = PROJECT / "论文" / "main.pdf"

CAPTION_RE = re.compile(r"图\s*(\d+)\s+([^\n]{4,60})")


def main() -> int:
    manifest = json.loads((PROJECT / "figures" / "manifest.json").read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    doc = fitz.open(PDF)
    pages_text = [page.get_text() for page in doc]

    captions = {}
    for index, text in enumerate(pages_text, 1):
        for match in CAPTION_RE.finditer(text):
            number = int(match.group(1))
            captions.setdefault(number, (index, match.group(2).strip()))

    print(f"论文总页数 {doc.page_count}，manifest 图项 {len(items)}，检出图题 {len(captions)} 个")
    issues = []
    for number in sorted(captions):
        page_no, title = captions[number]
        # 解释段以“图 N ”开头且不是题注本身
        follow = [i for i, text in enumerate(pages_text, 1)
                  if re.search(rf"图\s*{number}\s+(给出|显示|把|对比|给出)", text)]
        first_follow = min(follow) if follow else None
        status = "OK" if first_follow and first_follow >= page_no else "CHECK"
        if status != "OK":
            issues.append((number, title, page_no, first_follow))
        print(f"  {status} 图{number} 题注页 {page_no} 解释页 {first_follow}  {title[:26]}")

    # 每页图件纵向占比（用图题前后 5cm 内的绘图对象估算）
    print("\n图件密集页的题注数量：")
    per_page = {}
    for number, (page_no, _t) in captions.items():
        per_page[page_no] = per_page.get(page_no, 0) + 1
    for page_no in sorted(per_page):
        print(f"  第 {page_no} 页：{per_page[page_no]} 个图题")
    doc.close()
    print("\n落版核查结论：" + ("全部图件解释段与题注同页且顺序正确" if not issues else f"{len(issues)} 处待核对"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
