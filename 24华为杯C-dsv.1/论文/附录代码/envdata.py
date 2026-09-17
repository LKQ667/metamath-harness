from __future__ import annotations
import csv
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PLOT_TYPES = ('平旱地', '梯田', '山坡地', '水浇地', '普通大棚', '智慧大棚')
PLOT_SEASONS = {'平旱地': ('单季',), '梯田': ('单季',), '山坡地': ('单季',), '水浇地': ('第一季', '第二季'), '普通大棚': ('第一季', '第二季'), '智慧大棚': ('第一季', '第二季')}
FOOD = tuple(range(1, 16))
RICE = (16,)
VEG = tuple(range(17, 35))
LATE_VEG = (35, 36, 37)
FUNGI = (38, 39, 40, 41)
BEAN = (1, 2, 3, 4, 5, 17, 18, 19)
UP_VEG = (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34)
GH_VEG = tuple((value for value in UP_VEG if value not in (35, 36, 37)))
SEASON_ORDER = ('单季', '第一季', '第二季')

def read_csv(rel):
    path = ROOT / rel
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def crops_all():
    return {int(row['crop_id']): row['crop'] for row in read_csv('data/派生/crops.csv')}

def plots_all():
    rows = read_csv('data/派生/plots.csv')
    return [{'plot': row['plot'], 'kind': row['plot_type'], 'area': num(row['area'])} for row in rows]

def load_base2023():
    rows = read_csv('data/派生/base2023.csv')
    result = []
    for row in rows:
        result.append({'plot': row['plot'], 'crop_id': int(row['crop_id']), 'season': row['season'], 'area': num(row['area'])})
    return result

def load_demand():
    rows = read_csv('data/派生/demand2023.csv')
    return {int(row['crop_id']): num(row['sales2023_jin']) for row in rows}

def season_of(kind, crop_id):
    if kind in ('平旱地', '梯田', '山坡地'):
        return ('单季',) if crop_id in FOOD else ()
    if kind == '水浇地':
        if crop_id in RICE:
            return ('单季',)
        if crop_id in LATE_VEG:
            return ('第二季',)
        if crop_id in UP_VEG:
            return ('第一季',)
        return ()
    if kind == '普通大棚':
        if crop_id in GH_VEG:
            return ('第一季',)
        if crop_id in FUNGI:
            return ('第二季',)
        return ()
    if kind == '智慧大棚':
        if crop_id in GH_VEG:
            return ('第一季', '第二季')
        return ()
    return ()

def build_params(plots, crops):
    rows = read_csv('data/派生/params.csv')
    index = {}
    for row in rows:
        key = (int(row['crop_id']), row['plot_type'].strip(), row['season'].strip())
        index[key] = {'yield_jin': num(row['yield_jin']), 'cost_yuan': num(row['cost_yuan']), 'price_low': num(row['price_low']), 'price_high': num(row['price_high']), 'price_mid': num(row['price_mid'])}
    kinds = []
    for plot in plots:
        if plot['kind'] not in kinds:
            kinds.append(plot['kind'])
    params = {}
    for crop_id in sorted(crops):
        for kind in kinds:
            for season in PLOT_SEASONS[kind]:
                record = index.get((crop_id, kind, season))
                if record is None:
                    record = index.get((crop_id, '普通大棚', season))
                if record is None:
                    continue
                params[crop_id, kind, season] = dict(record)
    return params

def load_all():
    plots = plots_all()
    crops = crops_all()
    params = build_params(plots, crops)
    base = load_base2023()
    demand = load_demand()
    return {'plots': plots, 'crops': crops, 'params': params, 'base2023': base, 'demand': demand, 'plot_types': PLOT_TYPES, 'plot_seasons': PLOT_SEASONS, 'season_order': SEASON_ORDER, 'food': FOOD, 'rice': RICE, 'veg': VEG, 'late_veg': LATE_VEG, 'fungi': FUNGI, 'bean': BEAN, 'up_veg': UP_VEG, 'gh_veg': GH_VEG, 'price_by_crop': price_by_crop({'plots': plots, 'crops': crops, 'params': params, 'base2023': base}), 'cost_by_kind': cost_by_kind({'plots': plots, 'crops': crops, 'params': params}), 'yield_by_kind': yield_by_kind({'plots': plots, 'crops': crops, 'params': params, 'base2023': base})}

def capacity(data, crop_id, kind):
    seasons = season_of(kind, crop_id)
    if not seasons:
        return 0.0
    record = data['params'].get((crop_id, kind, seasons[0]))
    if record is None:
        return 0.0
    return record['yield_jin']

def cost_of(data, crop_id, kind):
    for season in PLOT_SEASONS[kind]:
        record = data['params'].get((crop_id, kind, season))
        if record is not None:
            return record['cost_yuan']
    return 0.0

def price_of(data, crop_id, kind):
    for season in PLOT_SEASONS[kind]:
        record = data['params'].get((crop_id, kind, season))
        if record is not None:
            return record['price_mid']
    return 0.0

def yield_by_plot(data, crop_id, kind):
    key = (crop_id, kind)
    base_area = data.setdefault('_base_area', None)
    if base_area is None:
        base_area = {}
        for row in data['base2023']:
            plot_kind = next((item['kind'] for item in data['plots'] if item['plot'] == row['plot']))
            base_area[row['crop_id'], plot_kind] = base_area.get((row['crop_id'], plot_kind), 0.0) + row['area']
        data['_base_area'] = base_area
    weighted = 0.0
    weight = 0.0
    for season in PLOT_SEASONS[kind]:
        record = data['params'].get((crop_id, kind, season))
        if record is None:
            continue
        share = base_area.get(key, 0.0)
        if share <= 0:
            share = 1.0
        weighted += share * record['yield_jin']
        weight += share
    if weight <= 0:
        return 0.0
    return weighted / weight

def price_by_crop(data):
    weight = {}
    for row in data['base2023']:
        kind = next((item['kind'] for item in data['plots'] if item['plot'] == row['plot']))
        weight[row['crop_id'], kind] = weight.get((row['crop_id'], kind), 0.0) + row['area']
    result = {}
    for crop_id in data['crops']:
        low = 0.0
        high = 0.0
        total = 0.0
        for item in data['plots']:
            kind = item['kind']
            if not season_of(kind, crop_id):
                continue
            record = None
            for season in PLOT_SEASONS[kind]:
                record = data['params'].get((crop_id, kind, season)) or record
            if record is None:
                continue
            share = weight.get((crop_id, kind), 0.0)
            if share <= 0:
                share = 1.0
            low += share * record['price_low']
            high += share * record['price_high']
            total += share
        if total <= 0:
            low = 0.0
            high = 0.0
            count = 0
            for item in data['plots']:
                kind = item['kind']
                for season in PLOT_SEASONS[kind]:
                    record = data['params'].get((crop_id, kind, season))
                    if record is None:
                        continue
                    low += record['price_low']
                    high += record['price_high']
                    count += 1
            if count == 0:
                continue
            result[crop_id] = {'low': low / count, 'high': high / count, 'mid': (low + high) / 2.0 / count}
        else:
            result[crop_id] = {'low': low / total, 'high': high / total, 'mid': (low + high) / 2.0 / total}
    return result

def cost_by_kind(data):
    result = {}
    for crop_id in data['crops']:
        for item in data['plots']:
            kind = item['kind']
            if not season_of(kind, crop_id):
                continue
            result[crop_id, kind] = cost_of(data, crop_id, kind)
    return result

def yield_by_kind(data):
    result = {}
    for crop_id in data['crops']:
        for item in data['plots']:
            kind = item['kind']
            if not season_of(kind, crop_id):
                continue
            result[crop_id, kind] = yield_by_plot(data, crop_id, kind)
    return result

def dump_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return target
