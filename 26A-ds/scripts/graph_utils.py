"""问题一/二/三共用的计算图读取与结构分析工具。

本模块只依赖标准库，负责把赛题给出的 Op-Tensor 二部图转换成操作级 DAG，
并给出建模与算法设计所需的确定性结构统计量。
"""

from __future__ import annotations

import json
from collections import defaultdict, deque

COPY_TYPES = {"COPY_IN", "COPY_OUT"}


def load_graph(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_op_dag(graph):
    """把二部图收缩为操作级 DAG，返回前驱、后继与非 COPY 操作集合。"""
    op_ids = {op["id"] for op in graph["ops"]}
    op_by_id = {op["id"]: op for op in graph["ops"]}
    producers = defaultdict(set)
    consumers = defaultdict(set)
    preds = {op_id: set() for op_id in op_ids}
    succs = {op_id: set() for op_id in op_ids}
    for edge in graph["edges"]:
        src, dst = edge["source"], edge["target"]
        src_op, dst_op = src in op_ids, dst in op_ids
        if src_op and dst_op:
            if src != dst:
                succs[src].add(dst)
                preds[dst].add(src)
        elif src_op:
            producers[dst].add(src)
        elif dst_op:
            consumers[src].add(dst)
    for tensor_id, producer_ids in producers.items():
        for src in producer_ids:
            for dst in consumers.get(tensor_id, ()):
                if src != dst:
                    succs[src].add(dst)
                    preds[dst].add(src)
    eligible = {op_id for op_id in op_ids if op_by_id[op_id]["op"] not in COPY_TYPES}
    return op_by_id, preds, succs, eligible


def contract_copy(preds, succs, eligible):
    """跳过 COPY 节点，得到仅含核内操作的前驱/后继关系。"""
    ordered = sorted(eligible)
    cpreds = {op_id: set() for op_id in ordered}
    csuccs = {op_id: set() for op_id in ordered}
    for src in ordered:
        stack = list(succs[src])
        seen = set()
        while stack:
            dst = stack.pop()
            if dst in eligible:
                if dst != src:
                    csuccs[src].add(dst)
                    cpreds[dst].add(src)
                continue
            if dst in seen:
                continue
            seen.add(dst)
            stack.extend(succs.get(dst, ()))
    return cpreds, csuccs


def op_cost(op):
    return max(1, int(op.get("cycles", 1)))


def longest_path(op_by_id, preds, nodes):
    """按给定顺序计算各节点以自身结尾的最长加权路径。"""
    best = {}
    for node in nodes:
        weight = op_cost(op_by_id[node])
        parent = 0
        for pre in preds.get(node, ()):
            if pre in best and best[pre] > parent:
                parent = best[pre]
        best[node] = parent + weight
    return best


def topological(nodes, preds, succs):
    node_set = set(nodes)
    nodes = sorted(node_set)
    indeg = {node: sum(1 for p in preds[node] if p in node_set) for node in nodes}
    ready = deque(sorted(n for n in nodes if indeg[n] == 0))
    order = []
    while ready:
        node = ready.popleft()
        order.append(node)
        for nxt in sorted(succs[node]):
            if nxt not in indeg:
                continue
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
    return order


def profile_case(graph):
    """返回单个用例的结构统计，供 EDA 与算法选参使用。"""
    op_by_id, preds, succs, eligible = build_op_dag(graph)
    cpreds, csuccs = contract_copy(preds, succs, eligible)
    order = topological(eligible, cpreds, csuccs)
    finish = longest_path(op_by_id, cpreds, order)
    total_m = sum(op_cost(op_by_id[n]) for n in eligible if op_by_id[n]["pipe"] == "PIPE_M")
    total_v = sum(op_cost(op_by_id[n]) for n in eligible if op_by_id[n]["pipe"] == "PIPE_V")
    total_work = total_m + total_v
    crit = max(finish.values()) if finish else 0
    width = total_work / crit if crit else 0.0
    edges = sum(len(csuccs[n]) for n in eligible)
    ddr_bytes = sum(t["size"] for t in graph["tensors"] if t["pos"] == "DDR")
    src_ops = sum(1 for n in eligible if not cpreds[n])
    snk_ops = sum(1 for n in eligible if not csuccs[n])
    return {
        "tensors": len(graph["tensors"]),
        "ops_total": len(graph["ops"]),
        "ops_copy": len(graph["ops"]) - len(eligible),
        "ops_core": len(eligible),
        "dag_edges": edges,
        "cycles_m": total_m,
        "cycles_v": total_v,
        "cycles_total": total_work,
        "critical_path": crit,
        "parallel_width": round(width, 3),
        "ddr_bytes": ddr_bytes,
        "source_ops": src_ops,
        "sink_ops": snk_ops,
        "max_degree": max((len(csuccs[n]) for n in eligible), default=0),
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(profile_case(load_graph(sys.argv[1])), ensure_ascii=False, indent=2))
