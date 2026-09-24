"""问题二（场景 B）主脚本：同核子图合并为单一 Task 的切图与调度。

场景 B 存在核间同步机制：同一核心上的全部子图合并成一个 Task，前序子图的
数据可驻留 L1/UB 供后续子图直接使用；只有跨核数据边才插入 COPY_OUT/COPY_IN，
并支付 500 周期同步延迟。因此切分的评价重心从“同核换 Task 等待”转为
“跨核边界数据量 + L1/UB 容量压力”。本脚本沿用共享算法核心，仅替换等待参数
与边界搬运代价口径。

运行示例：
    python Q2/main.py --case case_001 --cores 4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from eval_runner import case_path, run_evaluator, run_singlecore  # noqa: E402
from graph_utils import load_graph  # noqa: E402
from partition import build_plan  # noqa: E402

PROBLEM = 2
SCENE = "B"
CROSS_CORE_WAIT = 500.0
SAME_CORE_WAIT = 0.0


def make_plan(case, cores):
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
    parser = argparse.ArgumentParser(description="问题二（场景 B）方案生成与评估")
    parser.add_argument("--case", default="case_001")
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--plan-dir")
    parser.add_argument("--result-dir")
    parser.add_argument("--singlecore", action="store_true")
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
