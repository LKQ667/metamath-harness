"""项目内共享绘图与路径工具：定位 math-paper-cn 内置绘图链路并统一导出规范。"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def skill_root() -> Path:
    """定位 math-paper-cn 技能目录，避免在源码中硬编码绝对路径。"""
    candidates = [
        Path.home() / ".workbuddy-ai" / "skills" / "math-paper-cn",
        Path.home() / ".codex" / "skills" / "math-paper-cn",
        Path.home() / ".trae-cn" / "skills" / "math-paper-cn",
    ]
    for candidate in candidates:
        if (candidate / "scripts" / "plotting" / "py_nature_core.py").is_file():
            return candidate
    raise SystemExit("未找到 math-paper-cn 技能目录，无法加载内置绘图链路。")


def plotting_dir() -> Path:
    return skill_root() / "scripts" / "plotting"


def load_plotting():
    """导入内置绘图核心，返回模块对象。"""
    directory = str(plotting_dir())
    if directory not in sys.path:
        sys.path.insert(0, directory)
    import py_nature_core  # noqa: PLC0415

    return py_nature_core


def export(fig, out_base, dpi: int = 320) -> list[Path]:
    """按竞赛中文配置导出 svg + pdf + png。"""
    core = load_plotting()
    return core.save_py_nature_figure(fig, out_base, dpi=dpi, profile="competition_cn")


def qa(out_base) -> dict:
    """运行内置 QA，返回检查字典。"""
    core = load_plotting()
    result = core.run_py_nature_qa(Path(out_base).with_suffix(""), profile="competition_cn")
    return {"passed": bool(result.passed), **result.checks}


def prepare_style(font_size: float = 8.0) -> None:
    core = load_plotting()
    core.apply_py_nature_style(font_size=font_size, profile="competition_cn")


def palette() -> dict:
    return dict(load_plotting().PALETTE)
