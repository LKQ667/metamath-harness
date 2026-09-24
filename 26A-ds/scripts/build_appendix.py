"""生成论文附录中的逐用例结果表。

从唯一结果源 `results/final_results.json` 导出逐用例指标长表：每个问题拆成
“Makespan 表”和“加速比与搬运量表”两张，保证列宽不超过版心；表体放在附录中，
正文用“限于篇幅，完整结果见附录”引用。
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "论文"
CORES = [1, 2, 3, 4, 5]
PREAMBLE = "\\scriptsize\n\\setlength{\\tabcolsep}{2.5pt}\n\\renewcommand{\\arraystretch}{0.95}\n"


def load():
    return json.loads((ROOT / "results" / "final_results.json").read_text(encoding="utf-8"))


def longtable(caption, header, rows, column_spec, label):
    lines = [
        PREAMBLE.rstrip("\n"),
        "\\begin{longtable}{" + column_spec + "}",
        "\\caption{" + caption + "}\\label{" + label + "}\\\\",
        "\\hline",
        " & ".join(header) + " \\\\",
        "\\hline",
        "\\endfirsthead",
        "\\hline",
        " & ".join(header) + " \\\\",
        "\\hline",
        "\\endhead",
        "\\hline",
        "\\endfoot",
    ]
    for row in rows:
        lines.append(" & ".join(row) + " \\\\")
        lines.append("\\hline")
    lines.append("\\end{longtable}")
    lines.append("\\normalsize")
    lines.append("\\renewcommand{\\arraystretch}{1.2}")
    return "\n".join(lines) + "\n"


def case_name(case):
    return case.replace("case_", "")


def problem_tables(results, key, prefix, title):
    per_case = results[key]["per_case"]
    cases = sorted(per_case)
    makespan_rows = []
    speed_rows = []
    for case in cases:
        entry = per_case[case]
        row = [case_name(case)]
        for cores in CORES:
            item = entry.get(str(cores))
            row.append(str(item["makespan"]) if item else "--")
        makespan_rows.append(row)
        speed = [case_name(case)]
        for cores in CORES[1:]:
            item = entry.get(str(cores))
            speed.append(f"{item['speedup']:.3f}" if item else "--")
        item = entry.get("4")
        speed.append(str(item["added_bytes"]) if item else "--")
        speed_rows.append(speed)

    table_a = longtable(
        f"{title}逐用例 Makespan（单位：周期）",
        ["用例", "1 核", "2 核", "3 核", "4 核", "5 核"],
        makespan_rows,
        "|c|r|r|r|r|r|",
        f"tab:{prefix}_makespan",
    )
    table_b = longtable(
        f"{title}逐用例加速比与总额外数据搬运量（4 核，单位：字节）",
        ["用例", "2 核加速比", "3 核加速比", "4 核加速比", "5 核加速比", "额外搬运量"],
        speed_rows,
        "|c|r|r|r|r|r|",
        f"tab:{prefix}_speedup",
    )
    return table_a + "\n" + table_b


def problem3_tables(results):
    per_case = results["q3"]["per_case"]
    cases = sorted(per_case)
    time_rows = []
    traffic_rows = []
    for case in cases:
        entry = per_case[case]
        for cores in CORES[1:]:
            item = entry.get(str(cores))
            if not item or "l2_makespan" not in item:
                continue
            accesses = item.get("cache_accesses", 0)
            hit = item.get("cache_hits", 0) / accesses * 100.0 if accesses else 0.0
            time_rows.append([
                case_name(case), str(cores),
                str(item["nol2_makespan"]), str(item["l2_makespan"]),
                f"{item.get('cache_gain', 1.0):.3f}", f"{hit:.1f}",
            ])
            traffic_rows.append([
                case_name(case), str(cores),
                str(item["nol2_added_bytes"]), str(item["l2_added_bytes"]),
                str(item.get("cache_hits", 0)), str(item.get("cache_accesses", 0)),
            ])
    table_a = longtable(
        "问题三逐用例 Makespan 与只读 Cache 加速比（命中率单位：百分数）",
        ["用例", "核数", "无 L2", "只读 Cache", "加速比", "命中率"],
        time_rows,
        "|c|r|r|r|r|r|",
        "tab:q3_time",
    )
    table_b = longtable(
        "问题三逐用例总额外数据搬运量与 Cache 访问统计（单位：字节、次）",
        ["用例", "核数", "无 L2 搬运量", "只读 Cache 搬运量", "命中次数", "访问次数"],
        traffic_rows,
        "|c|r|r|r|r|r|",
        "tab:q3_traffic",
    )
    return table_a + "\n" + table_b


def main():
    results = load()
    (OUT / "附录_问题一结果.tex").write_text(
        problem_tables(results, "q1", "q1", "问题一"), encoding="utf-8"
    )
    (OUT / "附录_问题二结果.tex").write_text(
        problem_tables(results, "q2", "q2", "问题二"), encoding="utf-8"
    )
    (OUT / "附录_问题三结果.tex").write_text(problem3_tables(results), encoding="utf-8")
    print(json.dumps({"ok": True, "cases": results["meta"]["case_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
