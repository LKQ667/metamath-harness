#!/usr/bin/env python3
"""按每张图的真实长宽比自动规整 latex_includes.tex 里的 include 尺寸 — MetaMath Harness（DSH）适配版。

用法:
    python fig_include_size.py --figdir figures --latex figures/latex_includes.tex

行为（与原 MH Agent 发行版 fig_include_size.py 同口径）:
    - 读 --figdir 下每个 PDF 的真实尺寸（PyMuPDF 优先；缺失时用标准库解析 /MediaBox 兜底）；
    - 按 高/宽 分档改写对应 \\includegraphics 的 width:
        ratio = h/w : ≤0.8 → 0.85\\textwidth / ≤1.2 → 0.7 / ≤1.6 → 0.5 / >1.6 → 0.42
    - height 一律封顶 ≤0.8\\textheight（只压小不放大）；
    - ⛔ 全软失败: 某图 PDF 读不到就保持原样，不破坏文件；
      只改 width/height，keepaspectratio/caption/label/路径都不动。

退出码: 0=完成(可能带 WARN) 1=latex 文件缺失等致命错误 2=没有任何图被规整(全软失败)
纯标准库 + 可选 PyMuPDF，无其他第三方依赖。Windows 控制台 GBK 已做 UTF-8 兜底。
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 高/宽 → width 档位（\textwidth 的倍数）
_WIDTH_BANDS = [(0.8, "0.85"), (1.2, "0.7"), (1.6, "0.5")]
_WIDTH_FALLBACK = "0.42"
_HEIGHT_CAP = "0.8"  # \textheight 的倍数上限

# 匹配 \includegraphics[<opts>]{<path>} 的选项括号
_INC_RE = re.compile(r"(\\includegraphics\s*\[)([^\]]*)(\]\s*\{\s*([^}\s]+)\s*\})")
# width/height 允许无数字系数（width=\textwidth 即 1.0）
_WIDTH_RE = re.compile(r"width\s*=\s*([\d.]*)\\textwidth")
_HEIGHT_RE = re.compile(r"height\s*=\s*([\d.]*)\\textheight")


def pdf_size(path: Path):
    """返回 (w_pt, h_pt)；读不到返回 None。PyMuPDF 优先，标准库 /MediaBox 兜底。"""
    try:
        import fitz  # type: ignore

        with fitz.open(path) as doc:
            r = doc[0].rect
            return abs(r.width), abs(r.height)
    except Exception:
        pass
    try:
        raw = path.read_bytes()
        best = None
        for m in re.finditer(
            rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]", raw
        ):
            x0, y0, x1, y1 = (float(v) for v in m.groups())
            w, h = abs(x1 - x0), abs(y1 - y0)
            if w > 1 and h > 1:
                best = (w, h)
                break
        return best
    except Exception:
        return None


def pick_width(ratio: float) -> str:
    for cap, w in _WIDTH_BANDS:
        if ratio <= cap:
            return w
    return _WIDTH_FALLBACK


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--figdir", default="figures", help="图片 PDF 目录（默认 figures）")
    ap.add_argument("--latex", default="figures/latex_includes.tex", help="要规整的 latex 文件")
    args = ap.parse_args()

    latex_path = Path(args.latex)
    if not latex_path.is_file():
        print(f"❌ latex 文件不存在: {latex_path}")
        return 1
    figdir = Path(args.figdir)

    text = latex_path.read_text(encoding="utf-8")
    adjusted = kept = 0
    out_lines = text

    def _repl(m: re.Match) -> str:
        nonlocal adjusted, kept
        head, opts, tail, target = m.group(1), m.group(2), m.group(3), m.group(4)
        # 只处理指向本 figdir 下 PDF 的 include（其他保持原样）
        pdf = figdir / Path(target).name
        if not target.lower().endswith(".pdf") or not pdf.is_file():
            kept += 1
            return m.group(0)
        size = pdf_size(pdf)
        if not size or size[0] <= 0:
            print(f"⚠ {Path(target).name}: PDF 尺寸读取失败，保持原样")
            kept += 1
            return m.group(0)
        w_pt, h_pt = size
        ratio = h_pt / w_pt
        new_w = pick_width(ratio)
        new_opts = opts
        changed = False
        wm = _WIDTH_RE.search(new_opts)
        if wm:
            cur_w = wm.group(1) or "1"  # width=\textwidth 视作 1.0
            if abs(float(cur_w) - float(new_w)) > 1e-9:
                # ⛔ 用 lambda 做替换：re.sub 的替换串会把 \t 解析成制表符，毁掉 \textwidth
                new_opts = _WIDTH_RE.sub(lambda _m: f"width={new_w}\\textwidth", new_opts, count=1)
                changed = True
        else:
            kept += 1
            return m.group(0)  # 无 width 选项的 include 不动（非本 skill 产物格式）
        hm = _HEIGHT_RE.search(new_opts)
        if hm:
            cur_h = hm.group(1) or "1"
            if float(cur_h) > float(_HEIGHT_CAP):
                new_opts = _HEIGHT_RE.sub(lambda _m: f"height={_HEIGHT_CAP}\\textheight", new_opts, count=1)
                changed = True
        if changed:
            adjusted += 1
            print(f"✅ {Path(target).name}: ratio={ratio:.2f} → width={new_w}\\textwidth")
        else:
            kept += 1
        return head + new_opts + tail

    out_lines = _INC_RE.sub(_repl, out_lines)

    if out_lines != text:
        latex_path.write_text(out_lines, encoding="utf-8")
    print(f"=== fig_include_size 完成: 规整 {adjusted} 条, 保持 {kept} 条 ===")
    return 0 if (adjusted + kept) > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
