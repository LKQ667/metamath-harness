#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import final_results_path, find_numbers, iter_project_files, load_json, numeric_values, project_arg, read_text, write_report


def main() -> int:
    parser = project_arg("检查正文和结果文件是否引用 final_results.json 的关键数值")
    parser.add_argument("--tolerance", type=float, default=1e-2)
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    path = final_results_path(project)
    if not path.exists():
        errors.append(f"缺少唯一结果源: {path}")
        return write_report(False, "check_result_consistency", errors, args.output)
    data = load_json(path)
    values = numeric_values(data.get("results", data) if isinstance(data, dict) else data)
    important = {k: v for k, v in values.items() if any(token in k.lower() for token in ("result", "value", "mean", "thickness", "score", "厚度", "结果", "均值"))}
    if not important:
        errors.append("final_results.json 中未找到可校验的关键数值")
        return write_report(False, "check_result_consistency", errors, args.output)
    corpus = "\n".join(read_text(p) for p in iter_project_files(project, (".tex", ".md", ".csv", ".json")) if p != path)
    numbers = find_numbers(corpus)
    for key, value in important.items():
        if not any(abs(value - n) <= args.tolerance for n in numbers):
            errors.append(f"关键结果未在正文/结果文件中出现或超容差: {key}={value}")
    return write_report(not errors, "check_result_consistency", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
