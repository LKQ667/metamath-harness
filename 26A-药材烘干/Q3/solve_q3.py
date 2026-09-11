"""问题 3：以各处水分浓度低于 0.15 kg/kg 为判据确定烘干所需时间。

输出：
  results/result3.xlsx        —— 每隔 60 s、径向每隔 0.1 cm 的完整水分浓度
  results/q3_summary.json     —— 本问关键数值（供唯一结果源聚合）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ambient import ambient_functions, hold_values  # noqa: E402
from drying_model import properties_from_appendix3, solve_cylinder  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "results"

RADIUS_M = 0.02
DT_S = 10.0
N_CELLS = 200
T0_C = 28.0
C0 = 2.55
H_W = 25.0
H_M = 8e-7
TARGET = 0.15
MAX_DAYS = 30.0
RECORD_EVERY = 6
OUTPUT_R_CM = np.round(np.arange(0.0, 2.0 + 1e-9, 0.1), 1)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    t_air, c_air = ambient_functions()
    keep = np.arange(0, N_CELLS + 1, N_CELLS // 20)
    result = solve_cylinder(
        props=properties_from_appendix3(),
        radius=RADIUS_M,
        t_end=MAX_DAYS * 24 * 3600.0,
        dt=DT_S,
        n_cells=N_CELLS,
        t_initial=T0_C,
        c_initial=C0,
        t_air=t_air,
        c_air=c_air,
        h=H_W,
        h_m=H_M,
        record_every=RECORD_EVERY,
        stop_moisture=TARGET,
        keep_index=keep,
    )
    radii_cm = result.radii * 100.0
    seconds = result.times.astype(int)
    moisture = result.moisture

    header = ["时间"] + [f"{value:.1f}" for value in radii_cm]
    pd.DataFrame(np.column_stack([seconds, moisture]), columns=header).to_excel(
        RESULTS_DIR / "result3.xlsx", sheet_name="Sheet1", index=False
    )

    drying_time_s = float(result.meta["stop_time_s"])
    drying_time_h = round(drying_time_s / 3600.0, 4)

    table_hours = [6, 12, 18, 24, 30, 36, 42, 48]
    table_r = [0.0, 0.5, 1.0, 1.5, 2.0]
    table_index = [int(np.argmin(np.abs(radii_cm - value))) for value in table_r]
    rows_c = {}
    for value in table_hours:
        step = int(np.argmin(np.abs(result.times - value * 3600.0)))
        rows_c[str(value)] = [round(float(moisture[step, j]), 4) for j in table_index]
    final_step = moisture.shape[0] - 1
    rows_c["烘干结束时间"] = [round(float(moisture[final_step, j]), 4) for j in table_index]

    hold_t, hold_c = hold_values()
    summary = {
        "question": 3,
        "table_columns_cm": table_r,
        "moisture_table": rows_c,
        "result_drying_time_h": drying_time_h,
        "result_drying_time_days": round(drying_time_h / 24.0, 4),
        "result_surface_moisture_at_end": round(float(moisture[final_step, -1]), 4),
        "result_center_moisture_at_end": round(float(moisture[final_step, 0]), 4),
        "result_max_moisture_at_end": round(float(moisture[final_step].max()), 4),
        "result_moisture_threshold": TARGET,
        "meta": {
            "dt_s": DT_S,
            "n_cells": N_CELLS,
            "radius_cm": 2.0,
            "hold_temperature_C": round(hold_t, 4),
            "hold_moisture": round(hold_c, 6),
            "rows": int(seconds.size),
        },
    }
    (RESULTS_DIR / "q3_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "drying_time_h": drying_time_h, "rows": int(seconds.size)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
