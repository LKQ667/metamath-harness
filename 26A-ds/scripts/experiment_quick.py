"""快速对比实验：不同切分策略在若干用例上的场景 A 表现。"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_runner import case_path, run_evaluator, run_singlecore, write_plan  # noqa: E402
from graph_utils import load_graph  # noqa: E402
from partition import build_plan  # noqa: E402

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp")


def main():
    os.makedirs(TMP, exist_ok=True)
    cases = sys.argv[1].split(",") if len(sys.argv) > 1 else ["case_001"]
    cores = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [4]
    per_core = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    cross_wait = float(sys.argv[4]) if len(sys.argv) > 4 else 1000.0
    for name in cases:
        graph_path = case_path(name)
        graph = load_graph(graph_path)
        t0 = time.time()
        base = run_singlecore(graph_path, os.path.join(TMP, f"{name}_single.json"))
        t_single = time.time() - t0
        for n in cores:
            t0 = time.time()
            plan = build_plan(graph, n, cross_wait=cross_wait)
            t_plan = time.time() - t0
            plan_path = write_plan(plan, os.path.join(TMP, f"{name}_n{n}_p{per_core}.json"))
            t0 = time.time()
            res = run_evaluator(1, graph_path, plan_path, os.path.join(TMP, f"{name}_n{n}_p{per_core}_res.json"))
            t_eval = time.time() - t0
            speedup = base["makespan"] / res["makespan"] if res["makespan"] else 0
            print(
                json.dumps(
                    {
                        "case": name,
                        "cores": n,
                        "per_core": per_core,
                        "single": base["makespan"],
                        "makespan": res["makespan"],
                        "speedup": round(speedup, 3),
                        "added_bytes": res["data_movement_bytes"]["added_copy_bytes"],
                        "plan_s": round(t_plan, 2),
                        "eval_s": round(t_eval, 2),
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    main()
