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
FAST = os.environ.get('CROP_FAST') == '1'
LIMIT = int(os.environ.get('CROP_TIME_LIMIT', '200'))
LIMIT = LIMIT if LIMIT > 0 else None
YEAR_COUNT = int(os.environ.get('CROP_YEARS', '7'))
YEARS = tuple(range(2024, 2024 + YEAR_COUNT))
ALPHA = 0.9
SEED = 20240603
N_SCEN = 1 if FAST else 8
RISKS = (0.0,) if FAST else (0.0, 1.0, 3.0)
GROUPS = {'粮食': [6, 7, 8, 9, 10, 11, 12, 13, 14, 15], '豆类': [1, 2, 3, 4, 5, 17, 18, 19], '蔬菜': [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37], '食用菌': [38, 39, 40, 41]}
VEG_GROUP = {'粮食': 0, '豆类': 1, '蔬菜': 2, '食用菌': 3}
CORR = np.array([[1.0, 0.1, -0.15, -0.05], [0.1, 1.0, -0.08, -0.05], [-0.15, -0.08, 1.0, 0.12], [-0.05, -0.05, 0.12, 1.0]])
ELASTICITY = {'蔬菜': 0.35, '食用菌': 0.3, '粮食': 0.15, '豆类': 0.2}

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

def group_of(crop_id):
    for name, members in GROUPS.items():
        if crop_id in members:
            return name
    return '粮食'

def scenario_table(crops, years, factors, idio, drivers):
    table = {'yield': {}, 'cost': {}, 'price': {}, 'demand': {}}
    for year in years:
        t = year - years[0]
        yield_row = {}
        cost_row = {}
        price_row = {}
        demand_row = {}
        for crop_id in crops:
            name = group_of(crop_id)
            shock = float(factors[VEG_GROUP[name]]) + float(idio.get(crop_id, 0.0))
            cost_row[crop_id] = (1.0 + drivers['cost']) ** t
            yield_row[crop_id] = (1.0 + drivers['yld']) ** t * (1.0 + 0.5 * shock)
            if name == '蔬菜':
                price_row[crop_id] = ((1.0 + drivers['veg']) * (1.0 + 0.6 * shock)) ** t
            elif name == '食用菌':
                price_row[crop_id] = ((1.0 - drivers['fung']) * (1.0 + 0.5 * shock)) ** t
            else:
                price_row[crop_id] = (1.0 + 0.35 * shock) ** t
            if crop_id in (6, 7):
                demand_row[crop_id] = ((1.0 + drivers['grain']) * (1.0 + 0.4 * shock)) ** t
            else:
                demand_row[crop_id] = (1.0 + 0.5 * shock) ** t
        table['yield'][year] = yield_row
        table['cost'][year] = cost_row
        table['price'][year] = price_row
        table['demand'][year] = demand_row
    return table

def mean_table(tables_list, weights, crops, years):
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

def evaluate(plan, data, tables_list, weights, years, elastic=True):
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
                name = group_of(crop_id)
                yield_now = data['yield_by_kind'][crop_id, kind] * table['yield'][year][crop_id]
                unit = data['price_by_crop'].get(crop_id, {}).get('mid', 0.0) * table['price'][year][crop_id]
                cap_now = data['demand'].get(crop_id, 0.0) * table['demand'][year][crop_id]
                produced = area * yield_now
                sold = min(produced, cap_now)
                price_now = unit
                if elastic:
                    beta = ELASTICITY.get(name, 0.2)
                    ratio = sold / cap_now if cap_now > 0 else 0.0
                    price_now = unit * (1.0 - beta * ratio)
                revenue += price_now * sold
                cost += area * data['cost_by_kind'][crop_id, kind] * table['cost'][year][crop_id]
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
    return {'mean': mean, 'std': std, 'cvar': float(np.mean(tail)) if tail else float(array.min()), 'worst': float(array.min()), 'per_scenario': [round(float(item), 2) for item in array]}

def main():
    data = ed.load_all()
    yld, cst = tables(data)
    crops = sorted(data['crops'])
    rng = np.random.default_rng(SEED)
    weights = [1.0 / N_SCEN for _ in range(N_SCEN)]
    drivers_list = [{'grain': 0.075, 'yld': 0.05, 'cost': 0.05, 'veg': 0.05, 'fung': 0.03}, {'grain': 0.1, 'yld': 0.1, 'cost': 0.04, 'veg': 0.07, 'fung': 0.02}, {'grain': 0.05, 'yld': -0.1, 'cost': 0.08, 'veg': 0.03, 'fung': 0.05}, {'grain': 0.05, 'yld': 0.08, 'cost': 0.03, 'veg': 0.06, 'fung': 0.01}, {'grain': 0.075, 'yld': -0.06, 'cost': 0.06, 'veg': 0.04, 'fung': 0.04}, {'grain': 0.1, 'yld': -0.04, 'cost': 0.05, 'veg': 0.08, 'fung': 0.03}, {'grain': 0.06, 'yld': 0.06, 'cost': 0.06, 'veg': 0.02, 'fung': 0.05}, {'grain': 0.075, 'yld': 0.02, 'cost': 0.05, 'veg': 0.05, 'fung': 0.03}]
    tables_list = []
    factor_log = []
    for index in range(N_SCEN):
        factors = rng.multivariate_normal(np.zeros(4), CORR) * 0.06
        idio = {crop_id: float(rng.normal(0.0, 0.04)) for crop_id in crops}
        tables_list.append(scenario_table(crops, YEARS, factors, idio, drivers_list[index]))
        factor_log.append([round(float(value), 4) for value in factors])
    mean_coef = mean_table(tables_list, weights, crops, YEARS)
    out = {'alpha': ALPHA, 'scenario_count': N_SCEN, 'seed': SEED, 'correlation': CORR.tolist(), 'elasticity': ELASTICITY, 'group_shocks': factor_log, 'frontier': [], 'plans': {}}
    for risk in RISKS:
        started = time.time()
        cfg = base_cfg(data, yld, cst, mean_coef, weights, risk=risk)
        model = cm.build(cfg)
        result = cm.solve(model, time_limit=LIMIT, gap=0.01)
        plan = cm.plan_rows(model)
        stats = evaluate(plan, data, tables_list, weights, YEARS, elastic=True)
        plain = evaluate(plan, data, tables_list, weights, YEARS, elastic=False)
        item = {'risk': risk, 'status': result['status'], 'objective': round(result['objective'] or 0.0, 2), 'mean_profit': round(stats['mean'], 2), 'std_profit': round(stats['std'], 2), 'cvar': round(stats['cvar'], 2), 'mean_profit_no_elastic': round(plain['mean'], 2), 'audit': {key: value for key, value in cm.audit(model).items() if not key.endswith('detail')}}
        out['frontier'].append(item)
        print(json.dumps(item, ensure_ascii=False))
        if risk in (0.0, RISKS[-1]):
            key = 'neutral' if risk == 0.0 else 'robust'
            out['plans'][key] = {'summary': cm.summary(model, result), 'evaluation': stats, 'plan': plan, 'sales': cm.sales_rows(model), 'profit_by_year': {str(year): round(value, 2) for year, value in result['profit'].items()}}
            cm.dump(BASE / 'Q3' / f'q3_plan_{key}.json', plan)
            cm.dump(BASE / 'Q3' / f'q3_sales_{key}.json', cm.sales_rows(model))
            cm.dump(BASE / 'Q3' / f'q3_audit_{key}.json', cm.audit(model))
    q2_path = BASE / 'Q2' / 'q2_metrics.json'
    if q2_path.exists():
        q2 = json.loads(q2_path.read_text(encoding='utf-8'))
        out['comparison'] = {'q2_mean_profit': q2['frontier'][0]['mean_profit'], 'q2_std_profit': q2['frontier'][0]['std_profit'], 'q2_cvar': q2['frontier'][0]['cvar'], 'q3_mean_profit': out['frontier'][0]['mean_profit'], 'q3_std_profit': out['frontier'][0]['std_profit'], 'q3_cvar': out['frontier'][0]['cvar']}
        out['comparison']['mean_gap'] = round(out['comparison']['q3_mean_profit'] - out['comparison']['q2_mean_profit'], 2)
        base_std = out['comparison']['q2_std_profit']
        out['comparison']['std_ratio'] = round(out['comparison']['q3_std_profit'] / base_std, 4) if base_std else 0.0
    cm.dump(BASE / 'Q3' / 'q3_metrics.json', out)
    print(json.dumps(out.get('comparison', {}), ensure_ascii=False))
if __name__ == '__main__':
    main()
