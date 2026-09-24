"""对最终 PDF 做排版自查：图表是否越界、是否存在整页流程图、正文是否含超长表格。"""
from __future__ import annotations

import json
from pathlib import Path

import fitz

PROJECT = Path(__file__).resolve().parents[1]
PDF = PROJECT / "论文" / "main.pdf"
OUT = PROJECT / "检查结果"
SHOTS = PROJECT / "截图" / "排版自查"

MARGIN_TOLERANCE_PT = 2.0


def main() -> int:
    doc = fitz.open(PDF)
    SHOTS.mkdir(parents=True, exist_ok=True)
    report = {"pages": len(doc), "overflow": [], "full_page_images": [], "long_tables": [],
              "rendered": []}
    for page_index, page in enumerate(doc, 1):
        width, height = page.rect.width, page.rect.height
        images = page.get_images(full=True)
        for image in images:
            for rect in page.get_image_rects(image[0]):
                if (rect.x0 < -MARGIN_TOLERANCE_PT or rect.y0 < -MARGIN_TOLERANCE_PT
                        or rect.x1 > width + MARGIN_TOLERANCE_PT
                        or rect.y1 > height + MARGIN_TOLERANCE_PT):
                    report["overflow"].append({
                        "page": page_index,
                        "rect": [round(rect.x0, 1), round(rect.y0, 1),
                                 round(rect.x1, 1), round(rect.y1, 1)],
                        "page_size": [round(width, 1), round(height, 1)],
                    })
                area_ratio = (rect.width * rect.height) / (width * height)
                if area_ratio > 0.80:
                    report["full_page_images"].append({"page": page_index,
                                                       "area_ratio": round(area_ratio, 3)})
    # 正文范围内的长表格检查
    aux = (PROJECT / "论文" / "main.aux").read_text(encoding="utf-8", errors="replace")
    body_end = None
    for line in aux.splitlines():
        if "newlabel{body:end}" in line:
            parts = line.split("}{")
            for part in parts:
                if part.strip().isdigit():
                    body_end = int(part.strip())
                    break
    report["body_end_page"] = body_end
    for page_index, page in enumerate(doc, 1):
        if body_end is not None and page_index > body_end:
            continue
        tables = page.find_tables()
        for table in tables:
            rows = len(table.rows)
            if rows >= 25:
                report["long_tables"].append({"page": page_index, "rows": rows})
    # 渲染代表页供视觉复核
    targets = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 33, 34, 40]
    for page_index in targets:
        if page_index > len(doc):
            continue
        page = doc[page_index - 1]
        pix = page.get_pixmap(dpi=110)
        target = SHOTS / f"p{page_index:03d}.png"
        pix.save(target)
        report["rendered"].append(str(target.relative_to(PROJECT)).replace("\\", "/"))
    doc.close()
    (OUT / "layout_selfcheck.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rendered"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
