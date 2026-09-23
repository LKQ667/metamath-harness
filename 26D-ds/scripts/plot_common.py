# -*- coding: utf-8 -*-
"""绘图子系统定位与统一导出入口。

本技能的内置绘图子系统位于 Skill 目录下的 scripts/plotting/，本项目不复制其实现，
只在使用时把该目录加入 sys.path。定位顺序：
1. 环境变量 DSH_SKILL_HUAWEI（显式指定 Skill 根目录）；
2. 环境变量 DSH_HOME 下的 skills/math-paper-huawei；
3. 用户主目录下的 .dsh/skills/math-paper-huawei。

解析失败时抛出明确错误，不静默回退到其他绘图实现。
"""
from __future__ import annotations

import os
import sys

SKILL_NAME = "math-paper-huawei"


def _candidates():
    explicit = os.environ.get("DSH_SKILL_HUAWEI")
    if explicit:
        yield explicit
    home = os.environ.get("DSH_HOME")
    if home:
        yield os.path.join(home, "skills", SKILL_NAME)
    user = os.path.expanduser("~")
    yield os.path.join(user, ".dsh", "skills", SKILL_NAME)
    yield os.path.join(user, ".deepseek", "skills", SKILL_NAME)


def skill_root() -> str:
    for path in _candidates():
        if path and os.path.isdir(os.path.join(path, "scripts", "plotting")):
            return os.path.abspath(path)
    raise RuntimeError(
        "未能定位 math-paper-huawei Skill 目录；请设置环境变量 DSH_HOME 或 DSH_SKILL_HUAWEI。"
    )


def ensure_on_path() -> str:
    root = skill_root()
    for sub in ("scripts/plotting", "scripts"):
        target = os.path.join(root, *sub.split("/"))
        if os.path.isdir(target) and target not in sys.path:
            sys.path.insert(0, target)
    return root


ensure_on_path()

from py_nature_core import (  # noqa: E402,F401
    PALETTE,
    QAResult,
    apply_py_nature_style,
    choose_chart_family,
    mm_to_inch,
    run_py_nature_qa,
    save_py_nature_figure,
)
from template_registry import (  # noqa: E402,F401
    NON_DATA_CHART_TYPES,
    SUPPORTED_CHART_TYPES,
    TEMPLATE_REGISTRY,
    template_chart_types,
    template_panel_count,
)

PROFILE = "competition_cn"
DPI = 320