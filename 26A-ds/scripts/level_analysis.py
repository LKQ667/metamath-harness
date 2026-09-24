"""计算图分层结构分析：按最长路径分层，观察每层工作量与并行度。"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph_utils import build_op_dag, contract_copy, load_graph, op_cost, topological  # noqa: E402


def level_profile(graph):
    op_by_id, preds, succs, eligible = build_op_dag(graph)
    cpreds, csuccs = contract_copy(preds, succs, eligible)
    order = topological(eligible, cpreds, csuccs)
    level = {}
    for node in order:
        best = 0
        for pre in cpreds[node]:
            if pre in level and level[pre] + 1 > best:
                best = level[pre] + 1
        level[node] = best
    by_level = defaultdict(lambda: {"m": 0, "v": 0, "ops": 0})
    for node in eligible:
        bucket = by_level[level[node]]
        bucket["ops"] += 1
        bucket["m" if op_by_id[node]["pipe"] == "PIPE_M" else "v"] += op_cost(op_by_id[node])
    levels = sorted(by_level)
    return {
        "level_count": len(levels),
        "level_max": levels[-1] if levels else 0,
        "per_level": [(lv, by_level[lv]["ops"], by_level[lv]["m"], by_level[lv]["v"]) for lv in levels],
    }


if __name__ == "__main__":
    for name in sys.argv[1:]:
        graph = load_graph(name)
        prof = level_profile(graph)
        total = sum(m + v for _, _, m, v in prof["per_level"])
        top = sorted(prof["per_level"], key=lambda row: -(row[2] + row[3]))[:10]
        print(
            json.dumps(
                {
                    "case": os.path.basename(name),
                    "levels": prof["level_count"],
                    "level_max": prof["level_max"],
                    "total_cycles": total,
                    "heaviest_levels": top,
                },
                ensure_ascii=False,
            )
        )
