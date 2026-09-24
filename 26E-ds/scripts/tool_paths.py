"""外部命令行工具的路径解析。

优先读取环境变量覆盖，其次在系统 PATH 中查找，最后在 Conda 根目录下的常见子目录中查找。
解析结果只在使用时确定，不在源码中写死任何盘符或绝对路径。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ENV_PREFIX = "MATHMODEL_TOOL_"


def find_tool(name: str) -> str:
    override = os.environ.get(f"{ENV_PREFIX}{name.upper()}")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return str(candidate)
        raise RuntimeError(
            f"环境变量 {ENV_PREFIX}{name.upper()} 指向的文件不存在: {candidate}"
        )
    found = shutil.which(name)
    if found:
        return found
    roots = [os.environ.get("CONDA_PREFIX"), os.environ.get("CONDA_ROOT")]
    suffixes = ("Library/bin", "bin", "Scripts")
    for root in roots:
        if not root:
            continue
        for suffix in suffixes:
            for extension in (".exe", ""):
                candidate = Path(root) / suffix / f"{name}{extension}"
                if candidate.is_file():
                    return str(candidate)
    raise RuntimeError(
        f"未找到可执行文件 {name}；请把所在目录加入 PATH，"
        f"或设置环境变量 {ENV_PREFIX}{name.upper()} 指向该文件"
    )
