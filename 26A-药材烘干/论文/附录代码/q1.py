from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
from drying_model import properties_from_appendix2, solve_cylinder
RESULTS_DIR = PROJECT_ROOT / 'results'
DERIVED_DIR = PROJECT_ROOT / 'data' / 'derived'
RADIUS_M = 0.02
T_END_S = 1800.0
DT_S = 1.0
N_CELLS = 200
T0_C = 28.0
C0 = 2.55
H_W = 25.0
H_M = 8e-07
OUTPUT_R_CM = np.round(np.arange(0.0, 2.0 + 1e-09, 0.1), 1)

def ambient_functions():
    frame = pd.read_csv(DERIVED_DIR / 'ambient_conditions.csv')
    time = frame['时间'].to_numpy(dtype=float)
    temp = frame['温度'].to_numpy(dtype=float)
    conc = frame['水分浓度'].to_numpy(dtype=float)

    def t_air(t: float) -> float:
        return float(np.interp(t, time, temp))

    def c_air(t: float) -> float:
        return float(np.interp(t, time, conc))
    return (t_air, c_air)

def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    t_air, c_air = ambient_functions()
    result = solve_cylinder(props=properties_from_appendix2(), radius=RADIUS_M, t_end=T_END_S, dt=DT_S, n_cells=N_CELLS, t_initial=T0_C, c_initial=C0, t_air=t_air, c_air=c_air, h=H_W, h_m=H_M)
    radii_cm = result.radii * 100.0
    index = [int(np.argmin(np.abs(radii_cm - value))) for value in OUTPUT_R_CM]
    seconds = np.arange(1, result.times.size).astype(int)
    temperature = result.temperature[1:][:, index]
    moisture = result.moisture[1:][:, index]
    header = ['时间'] + [f'{value:.1f}' for value in OUTPUT_R_CM]
    with pd.ExcelWriter(RESULTS_DIR / 'result1.xlsx', engine='openpyxl') as writer:
        pd.DataFrame(np.column_stack([seconds, temperature]), columns=header).to_excel(writer, sheet_name='温度', index=False)
        pd.DataFrame(np.column_stack([seconds, moisture]), columns=header).to_excel(writer, sheet_name='水分浓度', index=False)
    table_times = [100, 300, 600, 900, 1200, 1500, 1800]
    table_r = [0.0, 0.5, 1.0, 1.5, 2.0]
    table_index = [int(np.argmin(np.abs(radii_cm - value))) for value in table_r]
    rows_t = {}
    rows_c = {}
    for value in table_times:
        step = int(np.argmin(np.abs(result.times - value)))
        rows_t[str(value)] = [round(float(result.temperature[step, j]), 4) for j in table_index]
        rows_c[str(value)] = [round(float(result.moisture[step, j]), 4) for j in table_index]
    last = int(np.argmin(np.abs(result.times - T_END_S)))
    changed = np.where(result.moisture[last] < C0 - 0.001)[0]
    penetration_cm = 0.0 if changed.size == 0 else round(float(2.0 - radii_cm[changed.min()]), 4)
    summary = {'question': 1, 'table_columns_cm': table_r, 'temperature_table': rows_t, 'moisture_table': rows_c, 'result_surface_temperature_1800s_C': round(float(result.temperature[last, -1]), 4), 'result_center_temperature_1800s_C': round(float(result.temperature[last, 0]), 4), 'result_surface_moisture_1800s': round(float(result.moisture[last, -1]), 4), 'result_center_moisture_1800s': round(float(result.moisture[last, 0]), 4), 'result_surface_moisture_drop_1800s': round(float(C0 - result.moisture[last, -1]), 4), 'result_penetration_depth_1800s_cm': penetration_cm, 'meta': {'dt_s': DT_S, 'n_cells': N_CELLS, 'radius_cm': 2.0, 't_end_s': T_END_S, 'h_w_m2k': H_W, 'h_m_m_s': H_M}}
    (RESULTS_DIR / 'q1_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'rows': int(seconds.size), 'cols': len(OUTPUT_R_CM)}, ensure_ascii=False))
if __name__ == '__main__':
    main()
