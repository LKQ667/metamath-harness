"""把各问关键数值聚合为唯一结果源 results/final_results.json。

论文、摘要、各问 result.md 与结果工作簿只允许引用本文件。
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"

RANGES = {
    "q1.result_surface_temperature_1800s_C": {"min": 28.0, "max": 60.0},
    "q1.result_center_temperature_1800s_C": {"min": 28.0, "max": 60.0},
    "q1.result_surface_moisture_1800s": {"min": 0.0, "max": 2.55},
    "q1.result_center_moisture_1800s": {"min": 0.0, "max": 2.55},
    "q2.result_surface_temperature_3h_C": {"min": 28.0, "max": 60.0},
    "q2.result_center_temperature_3h_C": {"min": 28.0, "max": 60.0},
    "q2.result_surface_moisture_3h": {"min": 0.0, "max": 2.55},
    "q2.result_center_moisture_3h": {"min": 0.0, "max": 2.55},
    "q3.result_drying_time_h": {"min": 24.0, "max": 240.0},
    "q3.result_surface_moisture_at_end": {"min": 0.0, "max": 0.15},
    "q3.result_center_moisture_at_end": {"min": 0.0, "max": 0.15},
    "q4.result_drying_time_h": {"min": 24.0, "max": 240.0},
    "q4.result_final_radius_cm": {"min": 1.0, "max": 2.0},
    "q4.result_shrinkage_ratio": {"min": 0.0, "max": 0.6},
}


def load(name: str) -> dict:
    return json.loads((RESULTS_DIR / name).read_text(encoding="utf-8"))


def main() -> None:
    q1 = load("q1_summary.json")
    q2 = load("q2_summary.json")
    q3 = load("q3_summary.json")
    q4 = load("q4_summary.json")

    payload = {
        "project": "2026 高教社杯全国大学生数学建模竞赛 A 题 药材的烘干问题",
        "language": "中文",
        "source": "results/final_results.json 为唯一最终结果源",
        "results": {
            "q1": q1,
            "q2": q2,
            "q3": q3,
            "q4": q4,
        },
        "ranges": RANGES,
        "headline": {
            "q1_surface_temperature_1800s_C": q1["result_surface_temperature_1800s_C"],
            "q1_center_temperature_1800s_C": q1["result_center_temperature_1800s_C"],
            "q1_surface_moisture_1800s": q1["result_surface_moisture_1800s"],
            "q1_penetration_depth_1800s_cm": q1["result_penetration_depth_1800s_cm"],
            "q2_surface_temperature_3h_C": q2["result_surface_temperature_3h_C"],
            "q2_center_temperature_3h_C": q2["result_center_temperature_3h_C"],
            "q2_surface_moisture_3h": q2["result_surface_moisture_3h"],
            "q2_center_moisture_3h": q2["result_center_moisture_3h"],
            "q3_drying_time_h": q3["result_drying_time_h"],
            "q3_drying_time_days": q3["result_drying_time_days"],
            "q3_center_moisture_at_end": q3["result_center_moisture_at_end"],
            "q4_drying_time_h": q4["result_drying_time_h"],
            "q4_drying_time_days": q4["result_drying_time_days"],
            "q4_final_radius_cm": q4["result_final_radius_cm"],
            "q4_shrinkage_ratio": q4["result_shrinkage_ratio"],
        },
    }
    (RESULTS_DIR / "final_results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "keys": list(payload["headline"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
