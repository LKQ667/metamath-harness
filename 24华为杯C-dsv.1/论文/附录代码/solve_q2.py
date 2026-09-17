from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
import numpy as np
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / '共享'))
import cropmodel as cm
import envdata as ed
PYTHON = sys.executable
FAST = os.environ.get('CROP_FAST') == '1'
LIMIT = int(os.environ.get('CROP_TIME_LIMIT', '200'))
LIMIT = LIMIT if LIMIT > 0 else None
YEAR_COUNT = int(os.environ.get('CROP_YEARS', '7'))
YEARS = tuple(range(2024, 2024 + YEAR_COUNT))
ALPHA = 0.9
VEG = tuple(range(17, 35))
FUNGI = tuple(range(38, 42))
WHEAT_MAIZE = (6, 7)
CORNERS = [('基准情形', {'grain': 0.075, 'other': 0.0, 'yld': 0.0, 'cost': 0.05, 'veg': 0.05, 'fung': 0.03}), ('粮价需求高增长', {'grain': 0.1, 'other': 0.05, 'yld': 0.05, 'cost': 0.05, 'veg': 0.05, 'fung': 0.03}), ('粮价需求低增长', {'grain': 0.05, 'other': -0.05, 'yld': -0.05, 'cost': 0.05, 'veg': 0.05, 'fung': 0.03}), ('产量与成本双压', {'grain': 0.075, 'other': 0.0, 'yld': -0.1, 'cost': 0.08, 'veg': 0.05, 'fung': 0.05}), ('产量与成本双松', {'grain': 0.075, 'other': 0.0, 'yld': 0.1, 'cost': 0.03, 'veg': 0.05, 'fung': 0.01}), ('蔬菜价格快涨', {'grain': 0.075, 'other': 0.05, 'yld': 0.0, 'cost': 0.05, 'veg': 0.07, 'fung': 0.01}), ('食用菌价格快降', {'grain': 0.075, 'other': -0.05, 'yld': 0.0, 'cost': 0.05, 'veg': 0.03, 'fung': 0.05}), ('综合不利', {'grain': 0.05, 'other': -0.05, 'yld': -0.1, 'cost': 0.08, 'veg': 0.03, 'fung': 0.05})]
if FAST:
    CORNERS = CORNERS[:1]
RISKS = (0.0,) if FAST else (0.0, 1.0, 3.0)

def tables(data):
    yld = {}
    cst = {}
    for item in data['plots']:
        for crop_id in data['crops']:
            if not ed.season_of(item['kind'], crop_id):
                continue
            yld[crop_id, item['plot']] = ed.yield_by_plot(data, crop_id, item['kind'])
            cst[crop_id, item['plot']] = ed.cost_of(data, crop_id, item['kind'])
    return (yld, cst)

def scenario_table(crops, years, driver):
    table = {'yield': {}, 'cost': {}, 'price': {}, 'demand': {}}
    for year in years:
        t = year - years[0]
        yield_row = {}
        cost_row = {}
        price_row = {}
        demand_row = {}
        for crop_id in crops:
            yield_row[crop_id] = (1.0 + driver['yld']) ** t
            cost_row[crop_id] = (1.0 + driver['cost']) ** t
            if crop_id in WHEAT_MAIZE:
                demand_row[crop_id] = (1.0 + driver['grain']) ** t
            else:
                demand_row[crop_id] = (1.0 + driver['other']) ** t
            if crop_id in VEG:
                price_row[crop_id] = (1.0 + driver['veg']) ** t
            elif crop_id in FUNGI:
                if crop_id == 41:
                    price_row[crop_id] = (1.0 - 0.05) ** t
                else:
                    price_row[crop_id] = (1.0 - driver['fung']) ** t
            else:
                price_row[crop_id] = 1.0
        table['yield'][year] = yield_row
        table['cost'][year] = cost_row
        table['price'][year] = price_row
        table['demand'][year] = demand_row
    return table

def mean_table(tables_list, crops, years, weights):
    table = {'yield': {}, 'cost': {}, 'price': {}, 'demand': {}}
    for year in years:
        for key in ('yield', 'cost', 'price', 'demand'):
            row = {}
            for crop_id in crops:
                row[crop_id] = float(sum((w * item[key][year][crop_id] for w, item in zip(weights, tables_list))))
            table[key][year] = row
    return table

def base_cfg(data, yld, cst, coef, weights, risk=0.0):
    return {'data': data, 'yield': yld, 'cost': cst, 'price': {crop_id: record['mid'] for crop_id, record in data['price_by_crop'].items()}, 'cap': dict(data['demand']), 'pen': 1.0, 'discount': 0.5, 'coef': coef, 'risk': risk, 'alpha': ALPHA, 'weights': {year: weights[index] if index < len(weights) else 1.0 / len(YEARS) for index, year in enumerate(YEARS)} if weights else None, 'plot_limit': 10, 'years': YEARS}

def evaluate(plan, data, tables_list, weights, years):
    values = []
    for table in tables_list:
        total = 0.0
        for year in years:
            revenue = 0.0
            cost = 0.0
            for entry in plan:
                if entry['year'] != year:
                    continue
                crop_id = entry['crop_id']
                kind = entry['kind']
                area = entry['area']
                yield_now = data['yield_by_kind'][crop_id, kind] * table['yield'][year][crop_id]
                price_now = data['price_by_crop'].get(crop_id, {}).get('mid', 0.0) * table['price'][year][crop_id]
                cap_now = data['demand'].get(crop_id, 0.0) * table['demand'][year][crop_id]
                cost += area * data['cost_by_kind'][crop_id, kind] * table['cost'][year][crop_id]
                revenue += price_now * min(area * yield_now, cap_now)
            total += revenue - cost
        values.append(total)
    array = np.array(values, dtype=float)
    weights_array = np.array(weights, dtype=float)
    mean = float((array * weights_array).sum())
    std = float(np.sqrt(((array - mean) ** 2 * weights_array).sum()))
    order = np.argsort(array)
    cumulative = 0.0
    tail = []
    for index in order:
        if cumulative >= 1 - ALPHA:
            break
        tail.append(array[index])
        cumulative += weights_array[index]
    cvar = float(np.mean(tail)) if tail else float(array.min())
    return {'mean': mean, 'std': std, 'cvar': cvar, 'worst': float(array.min()), 'best': float(array.max()), 'per_scenario': [round(float(item), 2) for item in array]}

def main():
    data = ed.load_all()
    yld, cst = tables(data)
    crops = sorted(data['crops'])
    count = len(CORNERS)
    weights = [1.0 / count for _ in CORNERS]
    tables_list = [scenario_table(crops, YEARS, driver) for _, driver in CORNERS]
    mean_coef = mean_table(tables_list, crops, YEARS, weights)
    out = {'alpha': ALPHA, 'scenario_count': count, 'scenarios': [name for name, _ in CORNERS], 'drivers': {name: driver for name, driver in CORNERS}, 'frontier': [], 'plans': {}, 'single': []}
    single = []
    for index, (name, driver) in enumerate(CORNERS):
        cfg = base_cfg(data, yld, cst, tables_list[index], weights, risk=0.0)
        model = cm.build(cfg)
        result = cm.solve(model, time_limit=LIMIT, gap=0.01)
        plan = cm.plan_rows(model)
        stats = evaluate(plan, data, tables_list, weights, YEARS)
        row = {'scenario': name, 'status': result['status'], 'plan_rows': len(plan), 'profit_value': round(stats['mean'], 2), 'audit': {key: value for key, value in cm.audit(model).items() if not key.endswith('detail')}}
        cm.dump(BASE / 'Q2' / f'q2_scen_{index}.json', {'summary': cm.summary(model, result), 'evaluation': stats})
        single.append(row)
        print(json.dumps(row, ensure_ascii=False))
    out['single'] = single
    for risk in RISKS:
        started = time.time()
        cfg = base_cfg(data, yld, cst, mean_coef, weights, risk=risk)
        model = cm.build(cfg)
        result = cm.solve(model, time_limit=LIMIT, gap=0.01)
        plan = cm.plan_rows(model)
        stats = evaluate(plan, data, tables_list, weights, YEARS)
        item = {'risk': risk, 'status': result['status'], 'objective': round(result['objective'] or 0.0, 2), 'mean_profit': round(stats['mean'], 2), 'std_profit': round(stats['std'], 2), 'cvar': round(stats['cvar'], 2), 'worst': round(stats['worst'], 2), 'audit': {key: value for key, value in cm.audit(model).items() if not key.endswith('detail')}}
        out['frontier'].append(item)
        print(json.dumps(item, ensure_ascii=False))
        if risk in (0.0, RISKS[-1]):
            key = 'neutral' if risk == 0.0 else 'robust'
            out['plans'][key] = {'summary': cm.summary(model, result), 'evaluation': stats, 'plan': plan, 'sales': cm.sales_rows(model), 'profit_by_year': {str(year): round(value, 2) for year, value in result['profit'].items()}}
            cm.dump(BASE / 'Q2' / f'q2_plan_{key}.json', plan)
            cm.dump(BASE / 'Q2' / f'q2_sales_{key}.json', cm.sales_rows(model))
            cm.dump(BASE / 'Q2' / f'q2_audit_{key}.json', cm.audit(model))
    ce_cfg = base_cfg(data, yld, cst, {}, None, risk=0.0)
    ce_model = cm.build(ce_cfg)
    ce_result = cm.solve(ce_model, time_limit=240, gap=0.01)
    ce_plan = cm.plan_rows(ce_model)
    ce_stats = evaluate(ce_plan, data, tables_list, weights, YEARS)
    out['certainty_equivalent'] = {'summary': cm.summary(ce_model, ce_result), 'evaluation': ce_stats}
    cm.dump(BASE / 'Q2' / 'q2_plan_ce.json', ce_plan)
    out['vss'] = round(out['frontier'][0]['mean_profit'] - ce_stats['mean'], 2)
    cm.dump(BASE / 'Q2' / 'q2_metrics.json', out)
    print(json.dumps({'vss': out['vss']}, ensure_ascii=False))
if __name__ == '__main__':
    main()
