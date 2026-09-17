from __future__ import annotations
import json
from pathlib import Path
import pulp
import envdata as ed
YEARS = tuple(range(2024, 2031))
SEASON_CODE = {'单季': 's0', '第一季': 's1', '第二季': 's2'}

def combos(data):
    kind = {item['plot']: item['kind'] for item in data['plots']}
    area = {item['plot']: item['area'] for item in data['plots']}
    allow = {}
    for item in data['plots']:
        name = item['plot']
        for crop_id in data['crops']:
            for season in ed.season_of(item['kind'], crop_id):
                allow[name, crop_id, season] = True
    return (kind, area, allow)

def base_index(data):
    index = {}
    for row in data['base2023']:
        index[row['plot'], row['crop_id'], row['season']] = row['area']
    return index

def bean_2023(data, plot):
    for row in data['base2023']:
        if row['plot'] == plot and row['crop_id'] in ed.BEAN:
            return True
    return False

def build(cfg):
    data = cfg['data']
    years = tuple(cfg.get('years', YEARS))
    kind, area, allow = combos(data)
    base = base_index(data)
    plots = [item['plot'] for item in data['plots']]
    subset = cfg.get('plot_subset')
    if subset:
        keep = set(subset)
        plots = [name for name in plots if name in keep]
        allow = {key: value for key, value in allow.items() if key[0] in keep}
    coef = cfg.get('coef', {})

    def scale(table_name, crop_id, year):
        table = coef.get(table_name, {}).get(year)
        if table is None:
            return 1.0
        return float(table.get(crop_id, 1.0))

    def yld(crop_id, plot, year):
        return cfg['yield'][crop_id, plot] * scale('yield', crop_id, year)

    def cst(crop_id, plot, year):
        return cfg['cost'][crop_id, plot] * scale('cost', crop_id, year)

    def prv(crop_id, year):
        if crop_id not in cfg['price']:
            return 0.0
        return cfg['price'][crop_id] * scale('price', crop_id, year)

    def cap(crop_id, year):
        return cfg['cap'][crop_id] * scale('demand', crop_id, year)
    prob = pulp.LpProblem('crop_plan', pulp.LpMaximize)
    pen = float(cfg.get('pen', 0.0))
    discount = float(cfg.get('discount', 0.0))
    x = {}
    on = {}
    for name, crop_id, season in allow:
        for year in years:
            key = (name, crop_id, season, year)
            tag = SEASON_CODE[season]
            x[key] = pulp.LpVariable(f'x_{name}_{crop_id}_{tag}_{year}', lowBound=0)
            on[key] = pulp.LpVariable(f'o_{name}_{crop_id}_{tag}_{year}', cat='Binary')
    use = {}
    for name, crop_id, _season in allow:
        for year in years:
            key = (name, crop_id, year)
            if key in use:
                continue
            use[key] = pulp.LpVariable(f'u_{name}_{crop_id}_{year}', cat='Binary')
    done = {}
    for name, crop_id, year in use:
        done[name, crop_id, year] = pulp.LpVariable(f'd_{name}_{crop_id}_{year}', cat='Binary')
    low = cfg.get('min_area', 0.3)
    for key, var in x.items():
        name, crop_id, season, year = key
        prob += var <= area[name] * on[key]
        prob += var >= min(low, area[name]) * on[key]
    for name in plots:
        for year in years:
            for season in ed.PLOT_SEASONS[kind[name]]:
                pool = [x[name, cid, season, year] for cid in data['crops'] if (name, cid, season) in allow]
                if pool:
                    prob += pulp.lpSum(pool) <= area[name]
        if kind[name] == '水浇地':
            for year in years:
                first = pulp.lpSum((x[name, cid, '第一季', year] for cid in data['crops'] if (name, cid, '第一季') in allow))
                second = pulp.lpSum((x[name, cid, '第二季', year] for cid in data['crops'] if (name, cid, '第二季') in allow))
                prob += first + second <= area[name]
                if cfg.get('strict_use', True):
                    prob += first + second >= 0.5 * area[name]
                if cfg.get('late_exclusive', True):
                    prob += second <= area[name] * use[name, 35, year]
                    prob += second <= area[name] * use[name, 36, year]
                    prob += second <= area[name] * use[name, 37, year]
                    prob += use[name, 35, year] + use[name, 36, year] + use[name, 37, year] <= 1
        if kind[name] == '普通大棚':
            for year in years:
                first = pulp.lpSum((x[name, cid, '第一季', year] for cid in data['crops'] if (name, cid, '第一季') in allow))
                second = pulp.lpSum((x[name, cid, '第二季', year] for cid in data['crops'] if (name, cid, '第二季') in allow))
                prob += first + second <= area[name]
    for name in plots:
        seed = 1.0 if bean_2023(data, name) else 0.0
        bean_years = []
        for year in years:
            terms = [x[name, cid, season, year] for cid in ed.BEAN for season in ed.season_of(kind[name], cid) if (name, cid, season, year) in x]
            if not terms:
                continue
            bean_years.append((year, pulp.lpSum(terms)))
        windows = []
        if seed > 0:
            windows.append((2023, [item[1] for item in bean_years if item[0] <= 2025]))
        for index, (year, _) in enumerate(bean_years):
            if 2024 <= year <= 2028:
                windows.append((year, [item[1] for item in bean_years[index:index + 3]]))
        for start, group in windows:
            if group:
                prob += (pulp.lpSum(group) >= 0.1, f'bean_{name}_{start}')
    for (name, crop_id, year), flag in use.items():
        seasons = list(ed.season_of(kind[name], crop_id))
        pool = [x[name, crop_id, season, year] for season in seasons if (name, crop_id, season, year) in x]
        if not pool:
            continue
        prob += pulp.lpSum(pool) <= area[name] * flag
        prob += pulp.lpSum(pool) >= min(low, area[name]) * flag
        prob += done[name, crop_id, year] >= flag
        prob += done[name, crop_id, year] <= flag
        if year == years[0]:
            seed_area = sum((base.get((name, crop_id, season), 0.0) for season in seasons))
            if seed_area > 0:
                prob += done[name, crop_id, year] <= 0
        else:
            prob += done[name, crop_id, year] + done[name, crop_id, year - 1] <= 1
    limit = cfg.get('plot_limit', 10)
    if limit:
        for crop_id in data['crops']:
            for year in years:
                pool = [flag for (name, cid, y), flag in use.items() if cid == crop_id and y == year]
                if pool:
                    prob += pulp.lpSum(pool) <= limit
    produce = {}
    revenue = {}
    margin = {}
    over = {}
    for crop_id in data['crops']:
        for year in years:
            terms = [yld(crop_id, name, year) * x[name, crop_id, season, year] for name in plots for season in ed.season_of(kind[name], crop_id) if (name, crop_id, season, year) in x]
            if not terms:
                continue
            produce[crop_id, year] = pulp.lpSum(terms)
            revenue[crop_id, year] = pulp.LpVariable(f'r_{crop_id}_{year}')
            margin[crop_id, year] = pulp.LpVariable(f'g_{crop_id}_{year}', lowBound=0)
            over[crop_id, year] = pulp.LpVariable(f'v_{crop_id}_{year}', lowBound=0)
    for year in years:
        for crop_id in data['crops']:
            key = (crop_id, year)
            if key not in produce:
                continue
            price = prv(crop_id, year)
            cap_now = cap(crop_id, year)
            prob += over[key] >= produce[key] - cap_now
            prob += revenue[key] <= price * (produce[key] - over[key])
            prob += revenue[key] <= price * produce[key]
            if discount < 1.0:
                prob += revenue[key] <= price * cap_now + discount * price * (produce[key] - cap_now)
            if pen > 0:
                prob += margin[key] <= revenue[key]
                prob += margin[key] <= price * (produce[key] - over[key])
    profit = {}
    for year in years:
        gain = pulp.lpSum((revenue[cid, year] for cid in data['crops'] if (cid, year) in revenue))
        outlay = pulp.lpSum((cst(crop_id, name, year) * x[name, crop_id, season, year] for name, crop_id, season, year in x))
        if pen > 0:
            gain = pulp.lpSum((margin[cid, year] for cid in data['crops'] if (cid, year) in margin))
        profit[year] = gain - outlay
    weights = cfg.get('weights')
    if weights:
        mean = pulp.lpSum((weights[year] * profit[year] for year in years))
    else:
        mean = pulp.lpSum((profit[year] for year in years)) / len(years)
    total = pulp.lpSum((profit[year] for year in years))
    risk = float(cfg.get('risk', 0.0))
    short = {}
    if risk > 0:
        alpha = float(cfg.get('alpha', 0.9))
        eta = pulp.LpVariable('eta', lowBound=-1000000000.0)
        used = weights or {year: 1.0 / len(years) for year in years}
        for year in years:
            short[year] = pulp.LpVariable(f'mu_{year}', lowBound=0)
            prob += short[year] >= -profit[year] - eta
        cvar = eta + pulp.lpSum((used[year] * short[year] for year in years)) / (1 - alpha)
        prob += mean - risk * cvar
    elif weights:
        prob += mean
    else:
        prob += total
    return {'problem': prob, 'x': x, 'on': on, 'use': use, 'done': done, 'produce': produce, 'revenue': revenue, 'margin': margin, 'over': over, 'profit': profit, 'short': short, 'plots': plots, 'kind': kind, 'area': area, 'allow': allow, 'base': base, 'data': data, 'years': years, 'cap': dict(cfg['cap']), 'coef': coef, 'pen': pen, 'discount': discount}

def solve(model, time_limit=600, gap=0.005):
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, gapRel=gap)
    model['problem'].solve(solver)
    return {'status': pulp.LpStatus[model['problem'].status], 'objective': pulp.value(model['problem'].objective), 'profit': {year: pulp.value(value) or 0.0 for year, value in model['profit'].items()}, 'runtime': model['problem'].solutionTime}

def plan_rows(model):
    rows = []
    data = model['data']
    for (name, crop_id, season, year), var in model['x'].items():
        value = var.value() or 0.0
        if value > 5e-05:
            rows.append({'plot': name, 'kind': model['kind'][name], 'crop_id': crop_id, 'crop': data['crops'][crop_id], 'season': season, 'year': year, 'area': round(value, 4)})
    rows.sort(key=lambda item: (item['year'], item['plot'], item['crop_id'], item['season']))
    return rows

def _scale_of(model, crop_id, year):
    table = model['coef'].get('demand', {}).get(year)
    if table is None:
        return 1.0
    return float(table.get(crop_id, 1.0))

def sales_rows(model):
    rows = []
    data = model['data']
    for key, var in model['produce'].items():
        crop_id, year = key
        total = var.value() or 0.0
        price = data['price_by_crop'].get(crop_id, {}).get('mid', 0.0)
        table_price = model['coef'].get('price', {}).get(year, {}) or {}
        price = price * float(table_price.get(crop_id, 1.0))
        cap_value = model['cap'][crop_id] * _scale_of(model, crop_id, year)
        revenue = model['revenue'][key].value() or 0.0
        loss = model['over'][key].value() or 0.0
        sold = min(total, cap_value)
        rows.append({'crop_id': crop_id, 'crop': data['crops'][crop_id], 'year': year, 'produce_jin': round(total, 2), 'sales_jin': round(sold, 2), 'surplus_jin': round(max(0.0, total - cap_value), 2), 'discard_jin': round(max(0.0, loss), 2), 'revenue_yuan': round(revenue, 2), 'price_yuan': round(price, 4), 'cap_jin': round(cap_value, 2)})
    rows.sort(key=lambda item: (item['year'], item['crop_id']))
    return rows

def audit(model):
    data = model['data']
    kind = model['kind']
    area = model['area']
    rows = plan_rows(model)
    group = {}
    beanyears = {}
    for row in rows:
        group.setdefault((row['plot'], row['crop_id']), set()).add(row['year'])
        if row['crop_id'] in ed.BEAN:
            beanyears.setdefault(row['plot'], set()).add(row['year'])
    repeat = []
    for (name, crop_id), years in group.items():
        order = sorted(years)
        for index in range(len(order) - 1):
            if order[index + 1] == order[index] + 1:
                repeat.append({'plot': name, 'crop_id': crop_id, 'years': [order[index], order[index + 1]]})
    bean_bad = []
    for name in model['plots']:
        years = set(beanyears.get(name, set()))
        if bean_2023(data, name):
            years.add(2023)
        for start in range(2024, 2029):
            if not [item for item in years if start <= item <= start + 2]:
                bean_bad.append({'plot': name, 'start': start})
    over = []
    for year in model['years']:
        for name in model['plots']:
            total = sum((row['area'] for row in rows if row['plot'] == name and row['year'] == year))
            if total > area[name] + 0.001:
                over.append({'plot': name, 'year': year, 'area': round(total, 4)})
    small = [{'plot': row['plot'], 'crop_id': row['crop_id'], 'year': row['year'], 'area': row['area']} for row in rows if row['area'] < 0.3 - 1e-06]
    return {'repeat_count': len(repeat), 'bean_window_fail': len(bean_bad), 'over_capacity': len(over), 'undersize_count': len(small), 'repeat_detail': repeat[:20], 'bean_detail': bean_bad[:20], 'over_detail': over[:20]}

def margin_rows(model):
    rows = []
    data = model['data']
    for key, var in model['margin'].items():
        crop_id, year = key
        rows.append({'crop_id': crop_id, 'crop': data['crops'][crop_id], 'year': year, 'margin_yuan': round(var.value() or 0.0, 2), 'revenue_yuan': round(model['revenue'][key].value() or 0.0, 2), 'produce_jin': round(model['produce'][key].value() or 0.0, 2)})
    rows.sort(key=lambda item: (item['year'], item['crop_id']))
    return rows

def summary(model, result):
    rows = plan_rows(model)
    sales = sales_rows(model)
    margins = margin_rows(model)
    profit = {str(year): round(value, 2) for year, value in result['profit'].items()}
    revenue = sum((row['revenue_yuan'] for row in sales))
    margin_total = sum((row['margin_yuan'] for row in margins))
    produce_total = sum((row['produce_jin'] for row in sales))
    sold_total = sum((row['sales_jin'] for row in sales))
    surplus_total = sum((row['surplus_jin'] for row in sales))
    outlay = sum((row['area'] * model['data']['cost_by_kind'][row['crop_id'], row['kind']] for row in rows))
    full = sum((row['produce_jin'] * row['price_yuan'] for row in sales))
    return {'objective': round(result['objective'] or 0.0, 2), 'status': result['status'], 'profit_by_year': profit, 'revenue_yuan': round(revenue, 2), 'margin_yuan': round(margin_total, 2), 'cost_yuan': round(outlay, 2), 'profit_value_yuan': round(margin_total - outlay, 2) if model['pen'] > 0 else round(revenue - outlay, 2), 'produce_jin': round(produce_total, 2), 'sales_jin': round(sold_total, 2), 'surplus_jin': round(surplus_total, 2), 'full_price_value_yuan': round(full, 2), 'plant_area': round(sum((row['area'] for row in rows)), 2), 'crop_count': len({row['crop_id'] for row in rows}), 'audit': {key: value for key, value in audit(model).items() if not key.endswith('detail')}}

def dump(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return target
