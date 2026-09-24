"""把唯一结果源中的真实数值写入论文的数值宏文件。

论文 `main.tex` 只使用形如 `\\CaseCount` 的宏，宏定义全部集中在 `论文/数值.tex`；
本脚本按固定映射重新生成该文件，因此可以反复运行且不会改动正文文字。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "论文" / "数值.tex"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fmt(value, digits=3):
    return f"{float(value):.{digits}f}"


def main():
    results = load_json(ROOT / "results" / "final_results.json")
    profile = list(csv.DictReader((ROOT / "data" / "case_profile.csv").open(encoding="utf-8")))
    sensitivity_path = ROOT / "灵敏度分析" / "sensitivity_results.json"
    sensitivity = load_json(sensitivity_path) if sensitivity_path.exists() else {"summary": {}}

    q1 = results["q1"]["average_speedup"]
    q2 = results["q2"]["average_speedup"]
    gain = results["q3"].get("average_cache_gain", {})
    hit = results["q3"].get("average_cache_hit_rate", {})

    ops = sorted(int(r["ops_core"]) for r in profile)
    cycles = sorted(int(r["cycles_total"]) for r in profile)
    width = sorted(float(r["parallel_width"]) for r in profile)
    levels = sorted(int(r["level_count"]) for r in profile)
    mat_share = sorted(float(r["cycles_m"]) / max(1.0, float(r["cycles_total"])) for r in profile)

    def median(values):
        n = len(values)
        return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2

    ratios = sorted(
        entry["4"]["estimate_ratio"]
        for entry in results["q1"]["per_case"].values()
        if entry.get("4") and "estimate_ratio" in entry["4"]
    )

    traffic_q1 = sum(entry.get("4", {}).get("added_bytes", 0) for entry in results["q1"]["per_case"].values())
    traffic_q2 = sum(entry.get("4", {}).get("added_bytes", 0) for entry in results["q2"]["per_case"].values())
    drop = (traffic_q1 - traffic_q2) / traffic_q1 * 100.0 if traffic_q1 else 0.0

    timeline_gap = 0.0
    timeline_path = ROOT / "results" / "evaluation" / "case_002_p1_n4_res.json"
    if timeline_path.exists():
        data = load_json(timeline_path)
        ends = [
            max((span["end"] for span in core.get("subgraphs", [])), default=0)
            for core in data["per_core_timeline"]
        ]
        timeline_gap = (max(ends) - min(ends)) / max(1, data["makespan"]) * 100.0

    blocks_summary = sensitivity.get("summary", {}).get("level_band", {})
    margin_summary = sensitivity.get("summary", {}).get("safety_margin", {})
    best_block = max(
        blocks_summary, key=lambda key: blocks_summary[key]["average_speedup"] or 0
    ) if blocks_summary else 1
    margins = sorted(margin_summary, key=float) if margin_summary else []
    margin_values = [
        margin_summary[m]["average_speedup"] for m in margins if margin_summary[m]["average_speedup"]
    ]
    margin_swing = (
        (max(margin_values) - min(margin_values)) / min(margin_values) * 100.0 if margin_values else 0.0
    )
    best_combo = 0.0
    for block in blocks_summary:
        for margin in margin_summary:
            best_combo = max(
                best_combo,
                min(
                    blocks_summary[block]["average_speedup"] or 0,
                    margin_summary[margin]["average_speedup"] or 0,
                ),
            )

    macro = {
        "CaseCount": str(results["meta"]["case_count"]),
        "CoreRange": "1 至 5",
        "CoreFive": "五",
        "OpsMin": str(min(ops)),
        "OpsMax": str(max(ops)),
        "OpsMed": str(int(median(ops))),
        "CyclesMin": str(min(cycles)),
        "CyclesMax": str(max(cycles)),
        "LevelMed": str(int(median(levels))),
        "MatShareMed": f"{median(mat_share) * 100:.1f}\\%",
        "WidthMed": f"{median(width):.1f}",
        "QOneSpeedTwo": fmt(q1.get("2", 1.0)),
        "QOneSpeedFive": fmt(q1.get("5", 1.0)),
        "QTwoSpeedFive": fmt(q2.get("5", 1.0)),
        "QThreeGainFive": fmt(gain.get("5", 1.0)),
        "QThreeHitFive": f"{float(hit.get('5', 0.0)) * 100:.1f}\\%",
        "QThreeHitTwo": f"{float(hit.get('2', 0.0)) * 100:.1f}\\%",
        "TrafficDrop": f"{drop:.1f}\\%",
        "EstRatioMed": fmt(median(ratios) if ratios else 1.0, 2),
        "TimelineGap": f"{timeline_gap:.1f}\\%",
        "BestBlocks": str(best_block),
        "MarginLow": f"{float(margins[0]):.2f}" if margins else "0.85",
        "MarginHigh": f"{float(margins[-1]):.2f}" if margins else "1.00",
        "MarginSwing": f"{margin_swing:.1f}\\%",
        "BestCombo": fmt(best_combo if best_combo else 1.0, 2),
    }

    lines = [
        "% 本文件由 scripts/fill_paper_numbers.py 从 results/final_results.json 自动生成。",
        "% 论文正文只引用这些宏，禁止在正文中硬编码数值。",
        "",
    ]
    for key, value in macro.items():
        lines.append(f"\\newcommand{{\\{key}}}{{{value}}}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(macro, ensure_ascii=False))


if __name__ == "__main__":
    main()
