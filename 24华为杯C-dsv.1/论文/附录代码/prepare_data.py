from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
PROJECT = Path(__file__).resolve().parents[1]
RAW = PROJECT / 'data' / 'raw'
OUT = PROJECT / 'data' / '派生'
YEARS = list(range(2024, 2031))
PLOT_TYPE_ALIAS = {'平旱地': '平旱地', '梯田': '梯田', '山坡地': '山坡地', '水浇地': '水浇地', '普通大棚': '普通大棚', '智慧大棚': '智慧大棚'}
SEASON_CAPACITY = {'平旱地': ['单季'], '梯田': ['单季'], '山坡地': ['单季'], '水浇地': ['单季', '第一季', '第二季'], '普通大棚': ['第一季', '第二季'], '智慧大棚': ['第一季', '第二季']}
BEAN_FOOD = [1, 2, 3, 4, 5]
BEAN_VEG = [17, 18, 19]
MUSHROOM = [38, 39, 40, 41]
SECOND_SEASON_VEG = [35, 36, 37]
MAIN_VEG = [17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34]
FOOD_ALL = list(range(1, 16))
RICE = [16]

def read_plots() -> pd.DataFrame:
    frame = pd.read_excel(RAW / '附件1.xlsx', sheet_name='乡村的现有耕地')
    frame = frame.rename(columns={'地块名称': 'plot', '地块类型': 'plot_type', '地块面积/亩': 'area'})
    frame['plot'] = frame['plot'].astype(str).str.strip()
    frame['plot_type'] = frame['plot_type'].astype(str).str.strip().map(PLOT_TYPE_ALIAS)
    frame['area'] = frame['area'].astype(float)
    frame = frame[['plot', 'plot_type', 'area']].dropna()
    frame['plot'] = frame['plot'].str.strip()
    keep = frame['plot'].str.match('^[A-F]\\d+$')
    frame = frame[keep].reset_index(drop=True)
    frame['seasons'] = frame['plot_type'].map(lambda name: ','.join(SEASON_CAPACITY[name]))
    return frame

def parse_crop_space(text: str) -> list[str]:
    value = str(text or '')
    names = []
    for name in ('平旱地', '梯田', '山坡地', '水浇地', '普通大棚', '智慧大棚'):
        if name in value:
            names.append(name)
    return names

def read_crops() -> pd.DataFrame:
    frame = pd.read_excel(RAW / '附件1.xlsx', sheet_name='乡村种植的农作物', nrows=41)
    frame = frame.rename(columns={'作物编号': 'crop_id', '作物名称': 'crop', '作物类型': 'ctype', '种植耕地': 'space'})
    frame = frame[['crop_id', 'crop', 'ctype', 'space']].dropna(subset=['crop_id'])
    frame['crop_id'] = frame['crop_id'].astype(int)
    frame['crop'] = frame['crop'].astype(str).str.strip()
    frame['ctype'] = frame['ctype'].astype(str).str.strip()
    frame['space_list'] = frame['space'].map(parse_crop_space)
    fallback = {'粮食': ['平旱地', '梯田', '山坡地'], '蔬菜': ['水浇地', '普通大棚', '智慧大棚']}
    frame['space_list'] = [spaces if spaces else fallback.get(kind, []) for spaces, kind in zip(frame['space_list'], frame['ctype'])]
    frame['is_bean'] = frame['crop_id'].isin(BEAN_FOOD + BEAN_VEG)
    frame['family'] = frame['ctype'].map(lambda value: '粮食（豆类）' if '豆类' in value and '粮食' in value else '蔬菜（豆类）' if '豆类' in value else value)
    return frame[['crop_id', 'crop', 'ctype', 'space_list', 'is_bean', 'family']]

def read_params() -> pd.DataFrame:
    frame = pd.read_excel(RAW / '附件2.xlsx', sheet_name='2023年统计的相关数据', nrows=107)
    frame = frame.rename(columns={'序号': 'seq', '作物编号': 'crop_id', '作物名称': 'crop', '地块类型': 'plot_type', '种植季次': 'season', '亩产量/斤': 'yield_jin', '种植成本/(元/亩)': 'cost_yuan', '销售单价/(元/斤)': 'price_range'})
    frame = frame.dropna(subset=['seq'])
    frame['plot_type'] = frame['plot_type'].astype(str).str.strip()
    frame['season'] = frame['season'].astype(str).str.strip()
    frame['yield_jin'] = frame['yield_jin'].astype(float)
    frame['cost_yuan'] = frame['cost_yuan'].astype(float)
    bounds = frame['price_range'].astype(str).str.split('-', expand=True)
    frame['price_low'] = bounds[0].astype(float)
    frame['price_high'] = bounds[1].astype(float)
    frame['price_mid'] = (frame['price_low'] + frame['price_high']) / 2.0
    frame = frame[['crop_id', 'crop', 'plot_type', 'season', 'yield_jin', 'cost_yuan', 'price_low', 'price_high', 'price_mid']]
    smart = frame[(frame['plot_type'] == '普通大棚') & (frame['season'] == '第一季')].copy()
    smart['plot_type'] = '智慧大棚'
    frame = pd.concat([frame, smart], ignore_index=True)
    frame['crop_id'] = frame['crop_id'].astype(int)
    return frame

def read_base2023() -> pd.DataFrame:
    frame = pd.read_excel(RAW / '附件2.xlsx', sheet_name='2023年的农作物种植情况', nrows=87)
    frame = frame.rename(columns={'种植地块': 'plot', '作物编号': 'crop_id', '作物名称': 'crop', '作物类型': 'ctype', '种植面积/亩': 'area', '种植季次': 'season'})
    frame = frame[['plot', 'crop_id', 'crop', 'ctype', 'area', 'season']]
    frame['plot'] = frame['plot'].ffill().astype(str).str.strip()
    frame = frame.dropna(subset=['crop_id'])
    frame['crop_id'] = frame['crop_id'].astype(int)
    frame['crop'] = frame['crop'].astype(str).str.strip()
    frame['ctype'] = frame['ctype'].astype(str).str.strip()
    frame['season'] = frame['season'].astype(str).str.strip()
    frame['area'] = frame['area'].astype(float)
    return frame.reset_index(drop=True)

def crop_plot_types(crop_id: int, crops: pd.DataFrame) -> list[str]:
    row = crops[crops['crop_id'] == crop_id]
    if row.empty:
        return []
    space = row.iloc[0]['space_list']
    if crop_id in FOOD_ALL:
        return [name for name in space if name in ('平旱地', '梯田', '山坡地')] or ['平旱地', '梯田', '山坡地']
    if crop_id in RICE:
        return ['水浇地']
    if crop_id in MUSHROOM:
        return ['普通大棚']
    if crop_id in SECOND_SEASON_VEG:
        return ['水浇地']
    return [name for name in space if name in ('水浇地', '普通大棚', '智慧大棚')]

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plots = read_plots()
    crops = read_crops()
    params = read_params()
    base = read_base2023()
    params['plot_types'] = params['crop_id'].map(lambda value: ','.join(crop_plot_types(int(value), crops)))
    plot_type_map = plots.set_index('plot')['plot_type'].to_dict()
    base_merge = base.copy()
    base_merge['plot_type'] = base_merge['plot'].map(plot_type_map)
    base_merge['plot_type'] = base_merge['plot_type'].fillna(base_merge['ctype'].map(lambda value: '平旱地' if '粮食' in value else '水浇地'))
    param_index = params.set_index(['crop_id', 'plot_type', 'season'])
    yield_values = []
    cost_values = []
    price_values = []
    for _, row in base_merge.iterrows():
        key = (int(row['crop_id']), str(row['plot_type']), str(row['season']))
        if key not in param_index.index:
            key = (int(row['crop_id']), '普通大棚', '第一季')
        record = param_index.loc[key]
        if isinstance(record, pd.DataFrame):
            record = record.iloc[0]
        yield_values.append(float(record['yield_jin']))
        cost_values.append(float(record['cost_yuan']))
        price_values.append(float(record['price_mid']))
    base_merge['yield_jin'] = yield_values
    base_merge['cost_yuan'] = cost_values
    base_merge['price_mid'] = price_values
    base_merge['production_jin'] = base_merge['area'] * base_merge['yield_jin']
    demand = base_merge.groupby(['crop_id', 'crop'], as_index=False).agg(sales2023_jin=('production_jin', 'sum'), area2023=('area', 'sum'), revenue2023_yuan=('production_jin', lambda values: float(values.sum()))).sort_values('crop_id')
    revenue = base_merge.assign(revenue=base_merge['production_jin'] * base_merge['price_mid']).groupby(['crop_id', 'crop'], as_index=False).agg(revenue2023_yuan=('revenue', 'sum'))
    demand = demand.drop(columns=['revenue2023_yuan']).merge(revenue, on=['crop_id', 'crop'], how='left')
    demand['sales2023_jin'] = demand['sales2023_jin'].round(4)
    crops.to_csv(OUT / 'crops.csv', index=False, encoding='utf-8-sig')
    plots.to_csv(OUT / 'plots.csv', index=False, encoding='utf-8-sig')
    params.to_csv(OUT / 'params.csv', index=False, encoding='utf-8-sig')
    base_merge.to_csv(OUT / 'base2023.csv', index=False, encoding='utf-8-sig')
    demand.to_csv(OUT / 'demand2023.csv', index=False, encoding='utf-8-sig')
    area_total = float(plots['area'].sum())
    summary = {'地块数量': int(len(plots)), '地块总面积亩': round(area_total, 4), '地块类型分布': {str(k): int(v) for k, v in plots['plot_type'].value_counts().items()}, '地块类型面积': {str(k): round(float(v), 4) for k, v in plots.groupby('plot_type')['area'].sum().items()}, '作物数量': int(len(crops)), '作物类型分布': {str(k): int(v) for k, v in crops['family'].value_counts().items()}, '豆类作物数量': int(crops['is_bean'].sum()), '参数记录数': int(len(params)), '2023种植记录数': int(len(base)), '缺失值统计': {'附件1_plots': int(plots.isna().sum().sum()), '附件1_crops': int(crops.isna().sum().sum()), '附件2_params': int(params.isna().sum().sum()), '附件2_base2023': int(base.isna().sum().sum())}, '重复值统计': {'附件1_plots地块名重复': int(plots['plot'].duplicated().sum()), '附件2_params组合重复': int(params.duplicated(subset=['crop_id', 'plot_type', 'season']).sum())}, '亩产量区间': [round(float(params['yield_jin'].min()), 4), round(float(params['yield_jin'].max()), 4)], '种植成本区间': [round(float(params['cost_yuan'].min()), 4), round(float(params['cost_yuan'].max()), 4)], '销售价格区间': [round(float(params['price_low'].min()), 4), round(float(params['price_high'].max()), 4)], '2023总产值元': round(float((base_merge['production_jin'] * base_merge['price_mid']).sum()), 4), '2023总成本元': round(float((base_merge['area'] * base_merge['cost_yuan']).sum()), 4), '折旧系数': round(float((base_merge['production_jin'].fillna(0) * base_merge['price_mid'].fillna(0) - base_merge['area'] * base_merge['cost_yuan'].fillna(0)).sum() / (base_merge['production_jin'].fillna(0) * base_merge['price_mid'].fillna(0)).sum()), 6), '预期销售量口径': '以 2023 年各作物实际总产量作为 2023 年销售量，问题一假定其保持稳定', '类别均价': {str(k): round(float(v), 4) for k, v in params.groupby('plot_type')['price_mid'].mean().items()}}
    (OUT / 'eda_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
