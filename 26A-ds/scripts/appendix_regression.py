"""附录代码等价性回归入口。

本脚本在“原版项目副本”与“附录净化副本”中分别执行同一段确定性计算，覆盖
附录中收录的全部核心模块，并把结果写入一个 JSON 供逐字段比较。它不参与建模
链路，只用于证明附录净化副本与真实源码行为一致。当运行环境缺少赛题附件解压
目录时，涉及官方评估程序的部分会如实记录为不可用，其余部分仍照常比对。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import aggregate_results  # noqa: E402
import eval_runner  # noqa: E402
import graph_utils  # noqa: E402
import partition  # noqa: E402


def suite_available() -> bool:
    try:
        eval_runner.suite_dir()
        return True
    except FileNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--case", default="case_001")
    args = parser.parse_args()

    payload = {
        "case": args.case,
        "suite_available": suite_available(),
        "eval_runner": {
            "side_paths": [p.name for p in eval_runner._side_paths(ROOT / "results" / "x_res.json")],
            "evaluator_names": dict(eval_runner.EVALUATORS),
        },
        "aggregate": {
            "cores": aggregate_results.CORES,
            "speedup": aggregate_results.speedup(10, 4),
        },
    }

    if payload["suite_available"]:
        graph_path = eval_runner.case_path(args.case)
        graph = graph_utils.load_graph(graph_path)
        plan = partition.build_plan(graph, 3, cross_wait=1000.0)
        plan_text = json.dumps(plan, ensure_ascii=False, sort_keys=True)
        plan_path = ROOT / "results" / "_appendix_regression_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(plan_text, encoding="utf-8")
        result = eval_runner.run_evaluator(
            1, graph_path, plan_path, ROOT / "results" / "_appendix_regression_res.json"
        )
        index = partition.GraphIndex(graph)
        core_of = {int(key): value for key, value in plan["node_to_subgraph"].items()}
        state = partition.PartitionState(index, 3)
        for node in index.order:
            subgraph = core_of[node]
            state.add(node, 0, subgraph)
        payload["graph"] = {
            "eligible": len(index.eligible),
            "edges": sum(len(index.csuccs[node]) for node in index.eligible),
            "ddr_bytes": index.ddr_bytes,
        }
        payload["plan"] = {
            "subgraphs": len(set(plan["node_to_subgraph"].values())),
            "hash": hashlib.sha256(plan_text.encode("utf-8")).hexdigest(),
        }
        payload["estimate"] = round(state.task_objective(1000.0, 100.0), 6)
        payload["makespan"] = result["makespan"]
        payload["added_bytes"] = result["data_movement_bytes"]["added_copy_bytes"]
        plan_path.unlink(missing_ok=True)

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
