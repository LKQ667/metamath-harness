#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import final_results_path, load_json, numeric_values, project_arg, write_report


def main() -> int:
    parser = project_arg("检查 final_results.json 中声明的通用结果范围")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    path = final_results_path(project)
    if not path.exists():
        errors.append(f"缺少唯一结果源: {path}")
        return write_report(False, "check_result_ranges", errors, args.output)
    data = load_json(path)
    ranges = data.get("ranges", {}) if isinstance(data, dict) else {}
    values = numeric_values(data.get("results", data) if isinstance(data, dict) else data)
    for key, spec in ranges.items():
        if not isinstance(spec, dict) or "min" not in spec or "max" not in spec:
            errors.append(f"ranges.{key} 必须包含 min/max")
            continue
        matched = {k: v for k, v in values.items() if key in k}
        if not matched:
            errors.append(f"未找到范围约束对应结果: {key}")
            continue
        for name, value in matched.items():
            if not (float(spec["min"]) <= value <= float(spec["max"])):
                errors.append(f"{name}={value} 超出范围 [{spec['min']}, {spec['max']}]")
    return write_report(not errors, "check_result_ranges", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
