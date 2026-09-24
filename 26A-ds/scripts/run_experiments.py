"""批量实验总控：为全部用例生成方案并调用官方评估程序。

本脚本是 step3 的总控入口，逐问链路仍在 Q1/Q2/Q3 各自的 main.py 中；这里
只负责按统一矩阵调度、缓存中间方案并把结果落到 results/ 下的结构化文件。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_runner import all_case_names, case_path, run_evaluator, run_singlecore  # noqa: E402
from graph_utils import load_graph  # noqa: E402
from partition import build_plan  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "results" / "plans"
WORK = ROOT / "results" / "evaluation"

CROSS_WAIT = {1: 1000.0, 2: 500.0, 3: 500.0}
IN_BANDWIDTH = {1: 60.0, 2: 60.0, 3: 250.0}
SUFFIX = {1: "", 2: "", 3: "_l2"}


def all_cases():
    return all_case_names()


def plan_path(case, problem, cores):
    return CACHE / f"{case}_p{problem}_n{cores}{SUFFIX[problem]}_plan.json"


def ensure_plan(case, problem, cores):
    path = plan_path(case, problem, cores)
    if path.exists():
        return path
    graph = load_graph(case_path(case))
    plan = build_plan(
        graph,
        cores,
        cross_wait=CROSS_WAIT[problem],
        in_bandwidth=IN_BANDWIDTH[problem],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return path


def compact_result(result):
    """去掉体量巨大且与论文指标无关的明细字段，保留可复算的评估结论。"""
    slim = dict(result)
    timeline = []
    for core in slim.get("per_core_timeline", []):
        timeline.append(
            {
                "core_id": core.get("core_id"),
                "tasks": core.get("tasks", []),
                "subgraphs": core.get("subgraphs", []),
                "op_count": len(core.get("ops", [])),
            }
        )
    slim["per_core_timeline"] = timeline
    log = slim.pop("ddr_contention_log", None)
    slim["ddr_contention_events"] = len(log) if log is not None else 0
    return slim


def job_singlecore(case):
    out = WORK / f"{case}_singlecore_res.json"
    if out.exists():
        return case, json.loads(out.read_text(encoding="utf-8"))
    WORK.mkdir(parents=True, exist_ok=True)
    result = run_singlecore(case_path(case), out)
    slim = compact_result(result)
    out.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
    return case, slim


def job_eval(args):
    case, problem, cores = args
    out = WORK / f"{case}_p{problem}_n{cores}{SUFFIX[problem]}_res.json"
    if out.exists():
        return case, problem, cores, json.loads(out.read_text(encoding="utf-8"))
    plan = ensure_plan(case, problem, cores)
    WORK.mkdir(parents=True, exist_ok=True)
    result = run_evaluator(problem, case_path(case), plan, out)
    slim = compact_result(result)
    out.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
    return case, problem, cores, slim


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--problems", default="1,2,3")
    parser.add_argument("--cores", default="1,2,3,4,5")
    parser.add_argument("--cases", default="")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--tag", default="main")
    args = parser.parse_args()

    problems = [int(x) for x in args.problems.split(",")]
    cores = [int(x) for x in args.cores.split(",")]
    cases = args.cases.split(",") if args.cases else all_cases()
    WORK.mkdir(parents=True, exist_ok=True)

    started = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        singles = {}
        for case, result in pool.map(job_singlecore, cases, chunksize=1):
            singles[case] = result["makespan"]
            print(f"[single] {case} makespan={result['makespan']}", flush=True)
        singles_path = ROOT / "results" / "singlecore_makespan.json"
        merged = {}
        if singles_path.exists():
            merged.update(json.loads(singles_path.read_text(encoding="utf-8")))
        merged.update(singles)
        singles_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        jobs = [(case, problem, n) for problem in problems for n in cores for case in cases]
        results = {}
        for case, problem, n, result in pool.map(job_eval, jobs, chunksize=1):
            key = f"{case}|{problem}|{n}"
            results[key] = result
            print(
                f"[eval] {case} p{problem} n{n} makespan={result['makespan']} "
                f"added={result['data_movement_bytes']['added_copy_bytes']}",
                flush=True,
            )
    out_path = ROOT / "results" / f"experiments_{args.tag}.json"
    slim_results = {
        key: {
            "makespan": value.get("makespan"),
            "added_bytes": (value.get("data_movement_bytes") or {}).get("added_copy_bytes"),
            "cache_stats": value.get("cache_stats"),
        }
        for key, value in results.items()
    }
    out_path.write_text(json.dumps(slim_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done in {time.time() - started:.1f}s -> {out_path}")


if __name__ == "__main__":
    main()
