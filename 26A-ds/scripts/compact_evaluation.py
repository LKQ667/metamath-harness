"""压缩评估输出，去掉体量大且与论文指标无关的明细字段。

只保留可复算的指标（Makespan、搬运量、Cache 统计、每核任务与子图区间摘要），
删除逐事件明细，避免仓库体量失控；指标字段一律不改写。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DROP = ("cache_events", "task_dependencies", "cross_core_transfers", "step3_by_core")


def compact(result: dict) -> dict:
    slim = dict(result)
    for key in DROP:
        value = slim.pop(key, None)
        if isinstance(value, list):
            slim[f"{key}_count"] = len(value)
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
    if log is not None:
        slim["ddr_contention_events"] = len(log)
    return slim


def main():
    targets = list((ROOT / "results" / "evaluation").glob("*.json"))
    targets += list((ROOT / "灵敏度分析" / "evaluation").glob("*.json"))
    saved = 0
    for path in targets:
        before = path.stat().st_size
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or "makespan" not in data:
            continue
        path.write_text(json.dumps(compact(data), ensure_ascii=False), encoding="utf-8")
        saved += before - path.stat().st_size
    print(json.dumps({"files": len(targets), "saved_mb": round(saved / 1024 / 1024, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
