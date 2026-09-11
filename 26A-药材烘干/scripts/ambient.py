"""烘房边界工况读取与扩展。

附件 1 只给出 0—14400 s 的工况。题面说明烘干过程包含预热平衡与恒温干燥两个阶段，
且两阶段参数不同。据此约定：14400 s 之后进入恒温干燥，取附件 1 末值作为恒定工况。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = PROJECT_ROOT / "data" / "derived"


def load_ambient() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame = pd.read_csv(DERIVED_DIR / "ambient_conditions.csv")
    return (
        frame["时间"].to_numpy(dtype=float),
        frame["温度"].to_numpy(dtype=float),
        frame["水分浓度"].to_numpy(dtype=float),
    )


def hold_after_end(time: np.ndarray, values: np.ndarray, t_end: float) -> np.ndarray:
    """把 t_end 之后的工况固定为末值，实现恒温干燥阶段的恒定边界。"""
    extended = values.copy()
    extended[time > t_end] = values[time <= t_end][-1]
    return extended


def ambient_functions(t_hold: float = 14400.0):
    """返回 T_air(t)、C_air(t) 两个插值函数（t 单位 s，T 单位 ℃）。"""
    time, temp, conc = load_ambient()
    temp_ext = hold_after_end(time, temp, t_hold)
    conc_ext = hold_after_end(time, conc, t_hold)

    def t_air(t: float) -> float:
        return float(np.interp(t, time, temp_ext))

    def c_air(t: float) -> float:
        return float(np.interp(t, time, conc_ext))

    return t_air, c_air


def hold_values(t_hold: float = 14400.0) -> tuple[float, float]:
    time, temp, conc = load_ambient()
    mask = time <= t_hold
    return float(temp[mask][-1]), float(conc[mask][-1])
