#!/usr/bin/env python3
"""校验 Long Goal 目录的结构、追踪关系与最终完成条件。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_HEADINGS = {
    "spec.md": ("目标", "范围", "非目标", "约束", "需求", "验收标准"),
    "design.md": ("现状", "方案", "关键决策", "兼容", "风险", "验证", "回滚"),
    "tasks.md": ("任务", "验证记录"),
    "state.md": ("状态",),
    "review.md": ("第一轮", "第二轮", "第三轮", "最终结论"),
}
REQUIRED_STATE_FIELDS = (
    "状态",
    "当前阶段",
    "当前任务",
    "最近完成",
    "最近验证",
    "下一步",
    "更新时间",
    "阻塞原因",
)
REQ_RE = re.compile(r"\bREQ-\d{3,}\b")
TASK_RE = re.compile(
    r"^- \[(?P<done>[ xX])\]\s+(?P<id>TASK-\d{3,})\s+"
    r"\[(?P<reqs>REQ-\d{3,}(?:\s*,\s*REQ-\d{3,})*)\]",
    re.MULTILINE,
)


def read_utf8(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        errors.append(f"缺少文件：{path.name}")
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"不是有效 UTF-8：{path.name}")
        return ""
    if not text.strip():
        errors.append(f"文件为空：{path.name}")
    return text


def has_heading(text: str, keyword: str) -> bool:
    return any(
        line.lstrip("# ").strip().startswith(keyword)
        for line in text.splitlines()
        if line.startswith("#")
    )


def field_value(text: str, field: str) -> str | None:
    match = re.search(
        rf"^\s*(?:[-*]\s*)?{re.escape(field)}\s*[：:]\s*(.*?)\s*$",
        text,
        re.MULTILINE,
    )
    return match.group(1) if match else None


def section_text(text: str, heading_keyword: str) -> str:
    lines = text.splitlines()
    start = None
    level = None
    for index, line in enumerate(lines):
        match = re.match(r"^(#+)\s*(.*)$", line)
        if match and match.group(2).strip().startswith(heading_keyword):
            start = index + 1
            level = len(match.group(1))
            break
    if start is None or level is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        match = re.match(r"^(#+)\s+", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def validate(goal_dir: Path, final: bool) -> list[str]:
    errors: list[str] = []
    if not goal_dir.is_dir():
        return [f"目标目录不存在：{goal_dir}"]

    texts = {name: read_utf8(goal_dir / name, errors) for name in (
        "input.md",
        "spec.md",
        "design.md",
        "tasks.md",
        "state.md",
        "review.md",
    )}
    if errors:
        return errors

    for filename, keywords in REQUIRED_HEADINGS.items():
        for keyword in keywords:
            if not has_heading(texts[filename], keyword):
                errors.append(f"{filename} 缺少包含“{keyword}”的标题")

    for field in REQUIRED_STATE_FIELDS:
        if field_value(texts["state.md"], field) is None:
            errors.append(f"state.md 缺少字段：{field}")

    spec_requirements = set(REQ_RE.findall(section_text(texts["spec.md"], "需求")))
    if not spec_requirements:
        errors.append("spec.md 的需求章节没有 REQ-NNN")

    task_matches = list(TASK_RE.finditer(texts["tasks.md"]))
    if not task_matches:
        errors.append("tasks.md 没有符合格式的 TASK-NNN [REQ-NNN] 复选任务")
    task_ids = [match.group("id") for match in task_matches]
    if len(task_ids) != len(set(task_ids)):
        errors.append("tasks.md 存在重复 TASK 编号")

    linked_requirements: set[str] = set()
    for match in task_matches:
        linked_requirements.update(REQ_RE.findall(match.group("reqs")))
    unknown = linked_requirements - spec_requirements
    uncovered = spec_requirements - linked_requirements
    if unknown:
        errors.append("任务引用未知需求：" + ", ".join(sorted(unknown)))
    if uncovered:
        errors.append("需求没有任务覆盖：" + ", ".join(sorted(uncovered)))

    if final:
        incomplete = [match.group("id") for match in task_matches if match.group("done") == " "]
        if incomplete:
            errors.append("仍有未完成任务：" + ", ".join(incomplete))
        if (field_value(texts["state.md"], "状态") or "").lower() != "complete":
            errors.append("最终校验要求 state.md 的状态为 complete")
        if (field_value(texts["state.md"], "当前阶段") or "").lower() != "completed":
            errors.append("最终校验要求 state.md 的当前阶段为 completed")
        for round_name in ("第一轮", "第二轮", "第三轮"):
            status = field_value(section_text(texts["review.md"], round_name), "状态")
            if (status or "").lower() != "pass":
                errors.append(f"最终校验要求 {round_name}审查状态为 pass")
        if not section_text(texts["review.md"], "最终结论").strip():
            errors.append("review.md 的最终结论为空")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goal_dir", type=Path, help="待校验的 Overall-goal/goal-N 目录")
    parser.add_argument("--final", action="store_true", help="同时校验最终完成条件")
    args = parser.parse_args()

    errors = validate(args.goal_dir.resolve(), args.final)
    if errors:
        print("Long Goal 校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Long Goal 校验通过：{args.goal_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
