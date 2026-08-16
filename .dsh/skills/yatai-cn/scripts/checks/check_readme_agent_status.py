#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from common import project_arg, read_text, write_report


REQUIRED_README = ["运行命令", "依赖环境", "最终结果", "复现步骤", "异常处理记录", "外部新增数据", "外部文献"]
REQUIRED_AGENT = ["阶段状态自动更新区", "禁止编造", "禁止篡改", "数据来源"]
BAD_STATUS = ["未开始", "正在进行", "[ ] Step", "[/] Step"]


def main() -> int:
    parser = project_arg("检查 README.md 和 AGENT.md 状态同步")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    errors: list[str] = []
    readme = project / "README.md"
    agent = project / "AGENT.md"
    if not readme.exists():
        errors.append("缺少 README.md")
    else:
        text = read_text(readme)
        for token in REQUIRED_README:
            if token not in text:
                errors.append(f"README.md 缺少栏目: {token}")
        for token in BAD_STATUS:
            if token in text:
                errors.append(f"README.md 仍含未完成状态: {token}")
    if not agent.exists():
        errors.append("缺少 AGENT.md")
    else:
        text = read_text(agent)
        for token in REQUIRED_AGENT:
            if token not in text:
                errors.append(f"AGENT.md 缺少要求: {token}")
        for token in BAD_STATUS:
            if token in text:
                errors.append(f"AGENT.md 仍含未完成状态: {token}")
    return write_report(not errors, "check_readme_agent_status", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
