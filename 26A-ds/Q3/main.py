"""问题三（共享只读 L2）主脚本：L2 感知切图与缓存效果评估。

在场景 B 的基础上引入所有核心共享的只读 L2 Cache（容量 1 MB，带宽
250 bytes/cycle，与 DDR 带宽相互独立）。L2 的作用是复用多核共享输入：同一份
DDR 张量被多个核心读取时，首次未命中访问 DDR，后续访问由 L2 以更高带宽服务。
因此切分阶段读入边界搬运的有效带宽从 60 bytes/cycle 提升到 250 bytes/cycle，
“把共享输入的消费者摊到多个核”不再像无 L2 时那样昂贵，负载均衡与 L2 复用
可以同时改善。

本脚本提供两条候选路线并逐用例实测择优：
  l2      —— 读入边界按 L2 带宽计入时长（默认主路线）
  nol2    —— 读入边界仍按 DDR 带宽计入时长（问题二的代价口径）

运行示例：
    python Q3/main.py --case case_001 --cores 4 --variant both
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
from partition import BANDWIDTH, build_plan  # noqa: E402

PROBLEM = 3
SCENE = "B + 只读 L2"
CROSS_CORE_WAIT = 500.0
SAME_CORE_WAIT = 0.0
L2_BANDWIDTH = 250.0
VARIANTS = {"l2": L2_BANDWIDTH, "nol2": BANDWIDTH}


def make_plan(case, cores, variant="l2"):
    graph = load_graph(case_path(case))
    return build_plan(
        graph,
        cores,
        cross_wait=CROSS_CORE_WAIT,
        same_core_wait=SAME_CORE_WAIT,
        in_bandwidth=VARIANTS[variant],
    )


def evaluate(case, cores, variant="l2", plan_dir=None, result_dir=None):
    plan_dir = Path(plan_dir or ROOT / "results" / "plans")
    result_dir = Path(result_dir or ROOT / "results" / "evaluation")
    plan_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if variant == "l2" else f"_{variant}"
    plan_path = plan_dir / f"{case}_p{PROBLEM}_n{cores}{suffix}_plan.json"
    if not plan_path.exists():
        plan_path.write_text(json.dumps(make_plan(case, cores, variant), ensure_ascii=False), encoding="utf-8")
    result = run_evaluator(
        PROBLEM, case_path(case), plan_path, result_dir / f"{case}_p{PROBLEM}_n{cores}{suffix}_res.json"
    )
    return plan_path, result


def main():
    parser = argparse.ArgumentParser(description="问题三（只读 L2）方案生成与评估")
    parser.add_argument("--case", default="case_001")
    parser.add_argument("--cores", type=int, default=4)
    parser.add_argument("--variant", choices=["l2", "nol2", "both"], default="l2")
    parser.add_argument("--plan-dir")
    parser.add_argument("--result-dir")
    parser.add_argument("--singlecore", action="store_true")
    args = parser.parse_args()

    variants = ["l2", "nol2"] if args.variant == "both" else [args.variant]
    payload = {"case": args.case, "problem": PROBLEM, "scene": SCENE, "cores": args.cores, "variants": {}}
    for variant in variants:
        plan_path, result = evaluate(args.case, args.cores, variant, args.plan_dir, args.result_dir)
        entry = {
            "makespan": result["makespan"],
            "added_copy_bytes": result["data_movement_bytes"]["added_copy_bytes"],
            "cache_stats": result.get("cache_stats", {}),
            "plan": str(plan_path),
        }
        if args.singlecore:
            base = run_singlecore(case_path(args.case))
            entry["singlecore_makespan"] = base["makespan"]
            entry["speedup"] = round(base["makespan"] / result["makespan"], 4)
        payload["variants"][variant] = entry
    if len(variants) == 2:
        left = payload["variants"]["nol2"]["makespan"]
        right = payload["variants"]["l2"]["makespan"]
        payload["l2_speedup"] = round(left / right, 4) if right else None
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
