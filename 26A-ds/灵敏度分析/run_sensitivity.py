"""灵敏度分析：切分粒度与单核兜底阈值的参数扫描。

对一组代表性用例（规模覆盖中小图），逐一改变切分粒度 `blocks_per_core` 与单核
兜底阈值 `safety_margin`，用赛题官方评估程序实测 Makespan，量化这两个算法参数
对结果的影响，并输出结构化结果供绘图与论文引用。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from eval_runner import case_path, run_evaluator, run_singlecore  # noqa: E402
from graph_utils import load_graph  # noqa: E402
from partition import build_plan  # noqa: E402

WORK = ROOT / "灵敏度分析" / "evaluation"
PLANS = ROOT / "灵敏度分析" / "plans"
OUT = ROOT / "灵敏度分析" / "sensitivity_results.json"
CORES = 4
BANDS = [1, 2, 4, 8]
MARGINS = [0.75, 0.85, 0.95, 1.00]


def representative_cases(limit=12):
    import csv

    rows = list(csv.DictReader((ROOT / "data" / "case_profile.csv").open(encoding="utf-8")))
    rows = [r for r in rows if int(r["ops_core"]) <= 6000]
    rows.sort(key=lambda r: int(r["ops_core"]))
    step = max(1, len(rows) // limit)
    picked = [rows[i]["case"] for i in range(0, len(rows), step)][:limit]
    return picked


def job_bands(args):
    case, band = args
    out = WORK / f"{case}_band{band}_res.json"
    if out.exists():
        return "level_band", case, band, json.loads(out.read_text(encoding="utf-8"))
    graph = load_graph(case_path(case))
    plan = build_plan(graph, CORES, cross_wait=1000.0, level_bands=(band,))
    PLANS.mkdir(parents=True, exist_ok=True)
    plan_path = PLANS / f"{case}_band{band}_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    WORK.mkdir(parents=True, exist_ok=True)
    result = run_evaluator(1, case_path(case), plan_path, out)
    return "level_band", case, band, result


def job_margin(args):
    case, margin = args
    out = WORK / f"{case}_margin{margin}_res.json"
    if out.exists():
        return "margin", case, margin, json.loads(out.read_text(encoding="utf-8"))
    graph = load_graph(case_path(case))
    plan = build_plan(graph, CORES, cross_wait=1000.0, safety_margin=margin)
    PLANS.mkdir(parents=True, exist_ok=True)
    plan_path = PLANS / f"{case}_margin{margin}_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    WORK.mkdir(parents=True, exist_ok=True)
    result = run_evaluator(1, case_path(case), plan_path, out)
    return "margin", case, margin, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--cases", default="")
    args = parser.parse_args()
    cases = args.cases.split(",") if args.cases else representative_cases()
    WORK.mkdir(parents=True, exist_ok=True)

    singles = {}
    for case in cases:
        path = WORK / f"{case}_single_res.json"
        if path.exists():
            singles[case] = json.loads(path.read_text(encoding="utf-8"))["makespan"]
        else:
            result = run_singlecore(case_path(case), path)
            singles[case] = result["makespan"]

    payload = {"cores": CORES, "cases": cases, "singlecore": singles,
               "level_band": {}, "safety_margin": {}}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for kind, case, value, result in pool.map(
            job_bands, [(c, b) for b in BANDS for c in cases], chunksize=1
        ):
            payload["level_band"].setdefault(str(value), {})[case] = {
                "makespan": result["makespan"],
                "added_bytes": result["data_movement_bytes"]["added_copy_bytes"],
                "speedup": round(singles[case] / result["makespan"], 6),
            }
        for kind, case, value, result in pool.map(
            job_margin, [(c, m) for m in MARGINS for c in cases], chunksize=1
        ):
            payload["safety_margin"].setdefault(str(value), {})[case] = {
                "makespan": result["makespan"],
                "added_bytes": result["data_movement_bytes"]["added_copy_bytes"],
                "speedup": round(singles[case] / result["makespan"], 6),
            }
    summary = {}
    for group in ("level_band", "safety_margin"):
        summary[group] = {}
        for value, entries in payload[group].items():
            speeds = [item["speedup"] for item in entries.values()]
            summary[group][value] = {
                "average_speedup": round(sum(speeds) / len(speeds), 4) if speeds else None,
                "min_speedup": round(min(speeds), 4) if speeds else None,
            }
    payload["summary"] = summary
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(cases), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
