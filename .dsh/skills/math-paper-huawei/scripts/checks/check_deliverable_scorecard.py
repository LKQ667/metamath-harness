#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import final_results_path, manifest_path, project_arg, write_report


REQUIRED_DIRS = ["赛题", "数据预处理", "论文", "手绘图", "文献", "results", "检查结果"]


def main() -> int:
    parser = project_arg("检查最终交付评分卡所需关键产物")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    for dirname in REQUIRED_DIRS:
        if not (project / dirname).exists():
            errors.append(f"缺少目录: {dirname}")
    for path in [final_results_path(project), manifest_path(project), project / "README.md", project / "AGENT.md"]:
        if not path.exists():
            errors.append(f"缺少关键文件: {path.relative_to(project)}")
    if not list((project / "论文").glob("*.pdf")) and not list((project / "论文").glob("out/*.pdf")):
        errors.append("缺少论文 PDF")
    if not any(path for pattern in ("*.drawio", "*.png", "*.jpg", "*.jpeg") for path in (project / "手绘图").glob(pattern)):
        errors.append("缺少所选非数据绘图模式的流程类图源")
    return write_report(not errors, "check_deliverable_scorecard", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
