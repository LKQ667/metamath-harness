from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DERIVED_DIR = PROJECT_ROOT / 'data' / 'derived'

def load_ambient() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frame = pd.read_csv(DERIVED_DIR / 'ambient_conditions.csv')
    return (frame['时间'].to_numpy(dtype=float), frame['温度'].to_numpy(dtype=float), frame['水分浓度'].to_numpy(dtype=float))

def hold_after_end(time: np.ndarray, values: np.ndarray, t_end: float) -> np.ndarray:
    extended = values.copy()
    extended[time > t_end] = values[time <= t_end][-1]
    return extended

def ambient_functions(t_hold: float=14400.0):
    time, temp, conc = load_ambient()
    temp_ext = hold_after_end(time, temp, t_hold)
    conc_ext = hold_after_end(time, conc, t_hold)

    def t_air(t: float) -> float:
        return float(np.interp(t, time, temp_ext))

    def c_air(t: float) -> float:
        return float(np.interp(t, time, conc_ext))
    return (t_air, c_air)

def hold_values(t_hold: float=14400.0) -> tuple[float, float]:
    time, temp, conc = load_ambient()
    mask = time <= t_hold
    return (float(temp[mask][-1]), float(conc[mask][-1]))
