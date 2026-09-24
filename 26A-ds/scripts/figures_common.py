"""论文数据图的共享绘图与质检工具。

统一封装内置顶刊绘图子系统的样式、导出与质检，保证每张入文图都满足：
中文可编辑文本、SVG/PDF/PNG 三格式齐全、导出预检通过。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "plotting"))

from py_nature_core import (  # noqa: E402
    PALETTE,
    add_panel_label,
    apply_py_nature_style,
    compose_multi_panel,
    mm_to_inch,
    run_py_nature_qa,
    save_py_nature_figure,
)

PROFILE = "competition_cn"

__all__ = [
    "PALETTE",
    "PROFILE",
    "ROOT",
    "add_panel_label",
    "apply_py_nature_style",
    "compose_multi_panel",
    "finalize",
    "load_results",
    "mm_to_inch",
    "save_py_nature_figure",
]


def load_results():
    """读取唯一结果源。"""
    path = ROOT / "results" / "final_results.json"
    if not path.exists():
        raise FileNotFoundError("缺少 results/final_results.json，请先运行 scripts/aggregate_results.py")
    return json.loads(path.read_text(encoding="utf-8"))


def load_profile():
    """读取用例结构画像。"""
    import csv

    path = ROOT / "data" / "case_profile.csv"
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def finalize(fig, out_base, qa_dir=None):
    """导出三格式并执行导出预检，返回 (导出路径列表, 质检字典)。"""
    out_base = Path(out_base)
    saved = save_py_nature_figure(fig, out_base, dpi=300, profile=PROFILE)
    qa = run_py_nature_qa(out_base, profile=PROFILE)
    record = {"target": str(out_base), "passed": qa.passed, "checks": qa.checks, "exports": [str(p) for p in saved]}
    if qa_dir is not None:
        qa_dir = Path(qa_dir)
        qa_dir.mkdir(parents=True, exist_ok=True)
        name = out_base.name + "_qa.json"
        (qa_dir / name).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    if not qa.passed:
        raise RuntimeError(f"绘图质检未通过: {out_base} -> {qa.checks.get('issues')}")
    return saved, record
