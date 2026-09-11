from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
from ambient import ambient_functions
from drying_model import properties_from_appendix4, solve_shrinking
RESULTS_DIR = PROJECT_ROOT / 'results'
DERIVED_DIR = PROJECT_ROOT / 'data' / 'derived'
DT_S = 10.0
N_CELLS = 200
T0_C = 28.0
C0 = 2.55
H_W = 25.0
H_M = 8e-07
TARGET = 0.15
MAX_DAYS = 30.0
RECORD_EVERY = 6
COLUMN_R_CM = np.round(np.arange(0.0, 1.1 + 1e-09, 0.1), 1)

def radius_functions():
    frame = pd.read_csv(DERIVED_DIR / 'radius_profile.csv')
    time = frame['时间'].to_numpy(dtype=float)
    radius_cm = frame['半径'].to_numpy(dtype=float)
    spline = PchipInterpolator(time, radius_cm)
    derivative = spline.derivative()
    t_last = float(time[-1])
    r_last = float(radius_cm[-1])

    def radius_of(t: float) -> float:
        return float(spline(min(t, t_last))) / 100.0

    def rate_of(t: float) -> float:
        if t >= t_last:
            return 0.0
        return float(derivative(t)) / 100.0
    return (radius_of, rate_of, time, radius_cm)

def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    t_air, c_air = ambient_functions()
    radius_of, rate_of, time, radius_cm = radius_functions()
    result = solve_shrinking(props=properties_from_appendix4(), radius_of=radius_of, rate_of=rate_of, t_end=MAX_DAYS * 24 * 3600.0, dt=DT_S, n_cells=N_CELLS, t_initial=T0_C, c_initial=C0, t_air=t_air, c_air=c_air, h=H_W, h_m=H_M, record_every=RECORD_EVERY, stop_moisture=TARGET)
    times = result.times
    xi = result.radii / result.radii.max() if result.radii.max() > 0 else result.radii
    xi = np.linspace(0.0, 1.0, N_CELLS + 1)
    radius_hist = np.array(result.meta['radius_hist_cm']) / 100.0
    moisture = result.moisture
    columns = []
    for step, radius in enumerate(radius_hist):
        profile = moisture[step]
        distances = COLUMN_R_CM / 100.0
        values = [float(np.interp(d / radius, xi, profile)) for d in distances]
        surface = float(profile[-1])
        columns.append([*values, surface])
    table = np.array(columns)
    seconds = times.astype(int)
    header = ['时间'] + [f'{value:.1f}' for value in COLUMN_R_CM] + ['药材表面']
    pd.DataFrame(np.column_stack([seconds, table]), columns=header).to_excel(RESULTS_DIR / 'result4.xlsx', sheet_name='Sheet1', index=False)
    drying_time_s = float(result.meta['stop_time_s'])
    drying_time_h = round(drying_time_s / 3600.0, 4)
    final_step = table.shape[0] - 1
    final_radius_cm = round(float(radius_hist[-1] * 100.0), 4)
    table_hours = [6, 12, 18, 24, 30, 36, 42, 48]
    rows_c = {}
    for value in table_hours:
        step = int(np.argmin(np.abs(times - value * 3600.0)))
        rows_c[str(value)] = [round(float(v), 4) for v in table[step]]
    rows_c['烘干结束时间'] = [round(float(v), 4) for v in table[final_step]]
    summary = {'question': 4, 'table_columns_cm': [float(v) for v in COLUMN_R_CM] + ['药材表面'], 'moisture_table': rows_c, 'result_drying_time_h': drying_time_h, 'result_drying_time_days': round(drying_time_h / 24.0, 4), 'result_final_radius_cm': final_radius_cm, 'result_initial_radius_cm': 2.0, 'result_shrinkage_ratio': round(1.0 - final_radius_cm / 2.0, 4), 'result_surface_moisture_at_end': round(float(table[final_step, -1]), 4), 'result_center_moisture_at_end': round(float(table[final_step, 0]), 4), 'result_moisture_threshold': TARGET, 'meta': {'dt_s': DT_S, 'n_cells': N_CELLS, 'rows': int(seconds.size), 'radius_source': '附件2 保形插值，超出覆盖范围按末值保持', 'radius_covered_h': round(float(time[-1]) / 3600.0, 4), 'radius_last_cm': round(float(radius_cm[-1]), 4)}}
    (RESULTS_DIR / 'q4_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'drying_time_h': drying_time_h, 'rows': int(seconds.size)}, ensure_ascii=False))
if __name__ == '__main__':
    main()
