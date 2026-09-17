from __future__ import annotations
import json
import os
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / '共享'))
import cropmodel as cm
import envdata as ed
YEAR_COUNT = int(os.environ.get('CROP_YEARS', '2'))
YEARS = tuple(range(2024, 2024 + YEAR_COUNT))
_LIMIT = int(os.environ.get('CROP_TIME_LIMIT', '0'))
LIMIT = _LIMIT if _LIMIT > 0 else None

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

def build_case(data, yld, cst, risk, coef):
    return {'data': data, 'yield': yld, 'cost': cst, 'price': {crop_id: record['mid'] for crop_id, record in data['price_by_crop'].items()}, 'cap': dict(data['demand']), 'pen': 1.0, 'discount': 0.5, 'coef': coef, 'risk': risk, 'alpha': 0.9, 'years': YEARS, 'plot_limit': 10}

def run(data, yld, cst, risk, coef, label):
    cfg = build_case(data, yld, cst, risk, coef)
    model = cm.build(cfg)
    result = cm.solve(model, time_limit=LIMIT, gap=0.02)
    audit = cm.audit(model)
    rows = cm.plan_rows(model)
    return {'case': label, 'status': result['status'], 'objective': round(float(result['objective'] or 0.0), 2), 'rows': len(rows), 'area': round(sum((row['area'] for row in rows)), 4), 'audit': {key: audit[key] for key in ('repeat_count', 'bean_window_fail', 'over_capacity', 'undersize_count')}}

def main():
    data = ed.load_all()
    yld, cst = tables(data)
    out = {'years': list(YEARS), 'time_limit': LIMIT, 'cases': []}
    out['cases'].append(run(data, yld, cst, 0.0, {}, '问题一情形一'))
    out['cases'].append(run(data, yld, cst, 0.0, {}, '问题二均值口径'))
    out['cases'].append(run(data, yld, cst, 1.0, {}, '问题二风险口径'))
    target = BASE / '检查结果' / '核心复核.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
