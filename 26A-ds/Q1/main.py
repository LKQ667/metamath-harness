"""问题一（场景 A）主脚本：多核切图与调度方案生成、评估与结果落盘。

场景 A 下每个子图独立构成一个 Task，所有跨子图数据必须经 DDR 中转，同核换
Task 支付 100 周期、跨核前驱支付 1000 周期等待。本脚本用共享算法核心
`scripts/partition.py` 生成“保持后代连续的拓扑序 + 连续段切分 + HEFT 分核”的
方案，再调用赛题官方评估程序得到 Makespan 与总额外搬运量。

运行示例：
    python Q1/main.py --case case_001 --cores 4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from eval_runner import case_path, run_evaluator, run_singlecore  # noqa: E402
from graph_utils import load_graph  # noqa: E402
from partition import build_plan  # noqa: E402

PROBLEM = 1
SCENE = "A"
CROSS_CORE_WAIT = 1000.0
SAME_CORE_WAIT = 100.0


def make_plan(case, cores):
    """为场景 A 生成切图与调度方案。"""
    graph = load_graph(case_path(case))
    return build_plan(
        graph,
        cores,
        cross_wait=CROSS_CORE_WAIT,
        same_core_wait=SAME_CORE_WAIT,
    )


def evaluate(case, cores, plan_dir=None, result_dir=None):
    plan_dir = Path(plan_dir or ROOT / "results" / "plans")
    result_dir = Path(result_dir or ROOT / "results" / "evaluation")
    plan_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / f"{case}_p{PROBLEM}_n{cores}_plan.json"
    if not plan_path.exists():
        plan_path.write_text(json.dumps(make_plan(case, cores), ensure_ascii=False), encoding="utf-8")
    result = run_evaluator(PROBLEM, case_path(case), plan_path, result_dir / f"{case}_p{PROBLEM}_n{cores}_res.json")
    return plan_path, result


def main():
    parser = argparse.ArgumentParser(description="问题一（场景 A）方案生成与评估")
    parser.add_argument("--case", default="case_001")
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--plan-dir")
    parser.add_argument("--result-dir")
    parser.add_argument("--singlecore", action="store_true", help="同时输出单核基线用于计算加速比")
    args = parser.parse_args()

    plan_path, result = evaluate(args.case, args.cores, args.plan_dir, args.result_dir)
    payload = {
        "case": args.case,
        "problem": PROBLEM,
        "scene": SCENE,
        "cores": args.cores,
        "makespan": result["makespan"],
        "added_copy_bytes": result["data_movement_bytes"]["added_copy_bytes"],
        "scheduled_copy_bytes": result["data_movement_bytes"]["scheduled_copy_bytes"],
        "plan": str(plan_path),
    }
    if args.singlecore:
        base = run_singlecore(case_path(args.case))
        payload["singlecore_makespan"] = base["makespan"]
        payload["speedup"] = round(base["makespan"] / result["makespan"], 4)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
