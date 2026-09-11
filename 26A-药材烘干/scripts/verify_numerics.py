"""数值验证：网格与时间步收敛性、质量守恒与退化检验。

输出 检查结果/数值验证.json，供论文与三轮自查引用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ambient import ambient_functions  # noqa: E402
from drying_model import properties_from_appendix2, properties_from_appendix3, solve_cylinder, solve_shrinking  # noqa: E402

OUT = PROJECT_ROOT / "检查结果" / "数值验证.json"
DERIVED = PROJECT_ROOT / "data" / "derived"


def q1_case(n_cells: int, dt: float):
    t_air, c_air = ambient_functions()
    result = solve_cylinder(
        props=properties_from_appendix2(),
        radius=0.02,
        t_end=1800.0,
        dt=dt,
        n_cells=n_cells,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
        record_every=max(int(round(1.0 / dt)), 1),
        keep_index=np.array([0, n_cells]),
    )
    last = result.moisture.shape[0] - 1
    return {
        "n_cells": n_cells,
        "dt_s": dt,
        "surface_temperature_C": round(float(result.temperature[last, -1]), 6),
        "center_temperature_C": round(float(result.temperature[last, 0]), 6),
        "surface_moisture": round(float(result.moisture[last, -1]), 6),
        "center_moisture": round(float(result.moisture[last, 0]), 6),
    }


def q1_flux_balance() -> dict:
    """按表面通量积分得到的水分损失与内部含水率降低量对比。"""
    t_air, c_air = ambient_functions()
    n_cells = 200
    radius = 0.02
    dt = 1.0
    result = solve_cylinder(
        props=properties_from_appendix2(),
        radius=radius,
        t_end=1800.0,
        dt=dt,
        n_cells=n_cells,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
        record_every=1,
    )
    radii = result.radii
    d = 7e-9 * np.exp(-0.89 / np.maximum(result.moisture, 1e-6))
    dr = radius / n_cells
    flux = 8e-7 * (result.moisture[:, -1] - np.array([c_air(t) for t in result.times]))
    loss_flux = float(np.trapezoid(flux * radius, result.times) * 2.0)
    weight = 2.0 * radii * dr
    stored = float(np.sum((result.moisture[0] - result.moisture[-1]) * weight))
    return {
        "surface_flux_integral": round(loss_flux, 8),
        "internal_loss": round(stored, 8),
        "relative_gap": round(abs(loss_flux - stored) / max(abs(stored), 1e-12), 6),
    }


def q3_case(dt: float) -> float:
    t_air, c_air = ambient_functions()
    result = solve_cylinder(
        props=properties_from_appendix3(),
        radius=0.02,
        t_end=30.0 * 24 * 3600.0,
        dt=dt,
        n_cells=200,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
        record_every=1,
        stop_moisture=0.15,
        keep_index=np.array([0]),
    )
    return round(float(result.meta["stop_time_s"]) / 3600.0, 4)


def q4_degenerate() -> dict:
    """退化检验：半径固定且物性取附录 3 时，收缩模型应还原为固定域结果。"""
    t_air, c_air = ambient_functions()
    result = solve_shrinking(
        props=properties_from_appendix3(),
        radius_of=lambda t: 0.02,
        rate_of=lambda t: 0.0,
        t_end=30.0 * 24 * 3600.0,
        dt=10.0,
        n_cells=200,
        t_initial=28.0,
        c_initial=2.55,
        t_air=t_air,
        c_air=c_air,
        h=25.0,
        h_m=8e-7,
        record_every=6,
        stop_moisture=0.15,
    )
    return {"drying_time_h": round(float(result.meta["stop_time_s"]) / 3600.0, 4)}


def main() -> None:
    payload = {
        "网格收敛": [q1_case(100, 1.0), q1_case(200, 1.0), q1_case(400, 1.0)],
        "时间步收敛": [q1_case(200, 1.0), q1_case(200, 0.5)],
        "质量守恒": q1_flux_balance(),
        "烘干时间时间步无关性": {"dt_20_s": q3_case(20.0), "dt_10_s": q3_case(10.0), "dt_5_s": q3_case(5.0)},
        "收缩模型退化检验": q4_degenerate(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
