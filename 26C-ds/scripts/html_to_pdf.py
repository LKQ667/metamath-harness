"""把 手绘图/*.html 转为矢量 PDF 与 2× PNG，并跑结构检查与元素级几何自检。

运行：python scripts/html_to_pdf.py
"""

from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
HAND = PROJECT / "手绘图"


def locate_tools() -> Path:
    """定位 HTML 出图工具目录：优先环境变量，其次 DSH_HOME 下的技能安装位置。"""
    candidates = []
    env = os.environ.get("MATH_PAPER_HUAWEI_HTML_TOOLS")
    if env:
        candidates.append(Path(env))
    home = os.environ.get("DSH_HOME")
    if home:
        base = Path(home) / "skills"
        candidates.append(base / "math-paper-huawei" / "assets" / "html-figure" / "tools")
        candidates.append(base / "html-paper-figure" / "tools")
    candidates.append(PROJECT / "skills" / "html-paper-figure" / "tools")
    for candidate in candidates:
        if (candidate / "screenshot_capture.py").is_file():
            return candidate.resolve()
    return candidates[0].resolve()


SKILL = locate_tools()
CAPTURE = SKILL / "screenshot_capture.py"
CHECK = SKILL / "html_pdf_check.py"

NAMES = [
    "fig_roadmap", "fig_problem_analysis", "fig_experiment_design", "fig_artifact_sources",
    "fig_q1_denoise_flow", "fig_q1_response_flow", "fig_q2_multiscale_model",
    "fig_q2_laterality_mechanism", "fig_q2_feature_flow", "fig_q3_model_framework",
    "fig_q3_estimation_flow", "fig_q3_application",
]


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace",
                          capture_output=True, cwd=str(PROJECT))
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def render_png(pdf: Path, png: Path) -> bool:
    try:
        import fitz
    except ImportError:
        return False
    doc = fitz.open(pdf)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(192 / 72, 192 / 72))
    pix.save(png)
    doc.close()
    return True


def main() -> int:
    ok = fail = 0
    report = []
    for name in NAMES:
        html = HAND / f"{name}.html"
        pdf = HAND / f"{name}.pdf"
        png = HAND / f"{name}.png"
        if not html.exists():
            report.append(f"MISSING HTML {name}")
            fail += 1
            continue
        code, out = run([sys.executable, str(CAPTURE), "--file", str(html),
                         "--out", str(pdf), "--format", "pdf"])
        if code != 0 or not pdf.exists():
            report.append(f"PDF FAIL {name}: {out.strip()[-160:]}")
            fail += 1
            continue
        if not render_png(pdf, png):
            report.append(f"PNG FAIL {name}")
            fail += 1
            continue
        ccode, cout = run([sys.executable, str(CHECK), str(pdf)])
        gcode, gout = run([sys.executable, str(CAPTURE), "--geom-check", str(html)])
        status = "OK"
        if ccode == 1:
            status = "HTMLCHECK_FAIL"
        if gcode == 1:
            status = "GEOM_FAIL"
        if status != "OK":
            fail += 1
            detail = (cout if ccode == 1 else gout).strip().splitlines()
            report.append(f"{status} {name}: " + " | ".join(detail[-4:]))
        else:
            ok += 1
        size = pdf.stat().st_size
        report.append(f"{status} {name} pdf={size}B htmlcheck={ccode} geom={gcode}")
    print("\n".join(report))
    print(f"\n通过 {ok} 张，失败 {fail} 张")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
