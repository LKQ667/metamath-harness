#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check compiled PDF pages do not contain a >1/3-page continuous blank band."""

from __future__ import annotations

from pathlib import Path

from common import project_arg, write_report


MAX_BLANK_RATIO = 1 / 3
WHITE_THRESHOLD = 245
INK_ROW_RATIO = 0.002


def load_fitz():
    try:
        import fitz  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local env
        raise RuntimeError(f"缺少 PyMuPDF/fitz，无法渲染 PDF 检查页面留白: {exc}") from exc
    return fitz


def pdf_path(project: Path) -> Path | None:
    candidates = [project / "论文" / "main.pdf", project / "论文" / "out" / "main.pdf"]
    for path in candidates:
        if path.exists():
            return path
    pdfs = sorted((project / "论文").glob("*.pdf")) if (project / "论文").exists() else []
    return pdfs[0] if pdfs else None


def page_is_appendix(page_text: str) -> bool:
    return "附录" in page_text or "支撑材料文件目录" in page_text or "附录代码文件" in page_text


def blank_runs_for_page(page) -> tuple[float, tuple[int, int], tuple[int, int]]:
    pix = page.get_pixmap(alpha=False)
    width, height = pix.width, pix.height
    samples = pix.samples
    x0, x1 = int(width * 0.08), int(width * 0.92)
    y0, y1 = int(height * 0.05), int(height * 0.95)
    row_width = max(1, x1 - x0)
    blank_rows: list[bool] = []
    for y in range(y0, y1):
        dark = 0
        base = y * width * 3
        for x in range(x0, x1):
            idx = base + x * 3
            if samples[idx] < WHITE_THRESHOLD or samples[idx + 1] < WHITE_THRESHOLD or samples[idx + 2] < WHITE_THRESHOLD:
                dark += 1
        blank_rows.append((dark / row_width) < INK_ROW_RATIO)

    best_start = best_end = 0
    start: int | None = None
    for i, is_blank in enumerate(blank_rows):
        if is_blank and start is None:
            start = i
        if (not is_blank or i == len(blank_rows) - 1) and start is not None:
            end = i if not is_blank else i + 1
            if end - start > best_end - best_start:
                best_start, best_end = start, end
            start = None
    ratio = (best_end - best_start) / height
    return ratio, (best_start + y0, best_end + y0), (width, height)


def main() -> int:
    parser = project_arg("检查 PDF 正文页连续空白带不得超过 1/3 页高。")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    path = pdf_path(project)
    if path is None:
        errors.append("缺少论文 PDF，无法检查实际页面留白。")
        return write_report(False, "check_pdf_page_blank_ratio", errors, args.output)

    try:
        fitz = load_fitz()
        doc = fitz.open(path)
    except Exception as exc:
        errors.append(str(exc))
        return write_report(False, "check_pdf_page_blank_ratio", errors, args.output)

    appendix_started = False
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1
        text = page.get_text("text")
        if page_no == 1:
            continue
        if page_is_appendix(text):
            appendix_started = True
        if appendix_started:
            continue
        ratio, (start_y, end_y), (width, height) = blank_runs_for_page(page)
        if ratio >= MAX_BLANK_RATIO:
            errors.append(
                f"PDF 第 {page_no} 页存在连续空白带 {ratio:.1%}（y={start_y}-{end_y}, page={width}x{height}），超过 1/3 页高。"
            )

    return write_report(not errors, "check_pdf_page_blank_ratio", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
