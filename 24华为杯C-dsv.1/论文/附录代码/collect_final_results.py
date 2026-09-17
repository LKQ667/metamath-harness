from __future__ import annotations
import json
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / '共享'))

def load(rel):
    path = BASE / rel
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))

def main():
    q1 = load('Q1/q1_metrics.json')
    q2 = load('Q2/q2_metrics.json')
    q3 = load('Q3/q3_metrics.json')
    sensitivity = load('灵敏度分析/sensitivity_metrics.json')
    eda = load('data/派生/eda_summary.json')
    results = {'问题一': {}, '问题二': {}, '问题三': {}, '灵敏度分析': {}, '数据概况': {}}
    if eda:
        results['数据概况'] = {'地块数量': eda['地块数量'], '地块总面积亩': eda['地块总面积亩'], '作物数量': eda['作物数量'], '豆类作物数量': eda['豆类作物数量'], '参数记录数': eda['参数记录数'], '结果_2023总产值元': eda['2023总产值元'], '结果_2023总成本元': eda['2023总成本元']}
    if q1:
        for key, name in (('case1', '情形一_超产滞销'), ('case2', '情形二_超产降价50%')):
            item = q1[key]
            results['问题一'][name] = {'结果_七年净利润元': item['profit_value_yuan'], '结果_七年销售收入元': item['revenue_yuan'], '结果_七年种植成本元': item['cost_yuan'], '结果_七年总产量斤': item['produce_jin'], '结果_七年正常销售量斤': item['sales_jin'], '结果_超产量斤': item['surplus_jin'], '结果_种植面积亩': item['plant_area'], '结果_作物种类数': item['crop_count'], '结果_重茬违规数': item['audit']['repeat_count'], '结果_豆类窗口违规数': item['audit']['bean_window_fail'], '结果_容量越界数': item['audit']['over_capacity'], '结果_最小面积违规数': item['audit']['undersize_count']}
    if q2:
        neutral = q2['plans']['neutral']
        results['问题二'] = {'结果_情景数': q2['scenario_count'], '结果_中性方案情景均值元': q2['frontier'][0]['mean_profit'], '结果_中性方案标准差元': q2['frontier'][0]['std_profit'], '结果_中性方案尾部均值元': q2['frontier'][0]['cvar'], '结果_稳健方案情景均值元': q2['frontier'][-1]['mean_profit'], '结果_稳健方案标准差元': q2['frontier'][-1]['std_profit'], '结果_稳健方案尾部均值元': q2['frontier'][-1]['cvar'], '结果_确定性等价均值元': q2['certainty_equivalent']['evaluation']['mean'], '结果_随机解价值元': q2['vss'], '结果_中性方案种植面积亩': neutral['summary']['plant_area'], '结果_中性方案作物种类数': neutral['summary']['crop_count'], '结果_重茬违规数': neutral['summary']['audit']['repeat_count'], '结果_豆类窗口违规数': neutral['summary']['audit']['bean_window_fail']}
    if q3:
        neutral3 = q3['plans']['neutral']
        results['问题三'] = {'结果_情景数': q3['scenario_count'], '结果_中性方案情景均值元': q3['frontier'][0]['mean_profit'], '结果_中性方案标准差元': q3['frontier'][0]['std_profit'], '结果_中性方案尾部均值元': q3['frontier'][0]['cvar'], '结果_稳健方案情景均值元': q3['frontier'][-1]['mean_profit'], '结果_稳健方案标准差元': q3['frontier'][-1]['std_profit'], '结果_稳健方案尾部均值元': q3['frontier'][-1]['cvar'], '结果_不含弹性均值元': q3['frontier'][0]['mean_profit_no_elastic'], '结果_量价相关影响元': round(q3['frontier'][0]['mean_profit_no_elastic'] - q3['frontier'][0]['mean_profit'], 2), '结果_中性方案种植面积亩': neutral3['summary']['plant_area'], '结果_中性方案作物种类数': neutral3['summary']['crop_count'], '结果_重茬违规数': neutral3['summary']['audit']['repeat_count'], '结果_豆类窗口违规数': neutral3['summary']['audit']['bean_window_fail']}
    if q2 and q3:
        results['三问对比'] = {'结果_问题二均值元': q2['frontier'][0]['mean_profit'], '结果_问题三均值元': q3['frontier'][0]['mean_profit'], '结果_均值差元': round(q3['frontier'][0]['mean_profit'] - q2['frontier'][0]['mean_profit'], 2), '结果_标准差比': round(q3['frontier'][0]['std_profit'] / q2['frontier'][0]['std_profit'], 4) if q2['frontier'][0]['std_profit'] else 0.0, '结果_尾部均值差元': round(q3['frontier'][0]['cvar'] - q2['frontier'][0]['cvar'], 2)}
    if sensitivity:
        levels = sensitivity['levels']
        cases = sensitivity['cases']
        base = sensitivity['base_profit']
        block = {}
        for factor, name in (('yield', '亩产量'), ('cost', '种植成本'), ('price', '销售价格'), ('demand', '预期销售量')):
            picked = [item for item in cases if item['factor'] == factor]
            low = next((item for item in picked if item['level'] == min(levels)), None)
            high = next((item for item in picked if item['level'] == max(levels)), None)
            if low and high:
                block[name] = {'结果_低端利润元': low['profit'], '结果_高端利润元': high['profit'], '结果_低端变化率': round((low['profit'] - base) / base, 4), '结果_高端变化率': round((high['profit'] - base) / base, 4)}
        results['灵敏度分析'] = {'结果_基准利润元': base, **block}
    results['汇总指标'] = {'问题数': 3, '结果_问题一情形一净利润元': q1['case1']['profit_value_yuan'] if q1 else 0, '结果_问题二情景均值元': q2['frontier'][0]['mean_profit'] if q2 else 0, '结果_问题三情景均值元': q3['frontier'][0]['mean_profit'] if q3 else 0, '全文图片总数': 16}
    ranges = {'情形一_超产滞销.结果_七年净利润元': {'min': 20000000, 'max': 30000000}, '情形二_超产降价50%.结果_七年净利润元': {'min': 20000000, 'max': 30000000}, '结果_中性方案情景均值元': {'min': 15000000, 'max': 25000000}, '结果_稳健方案情景均值元': {'min': 15000000, 'max': 25000000}, '结果_重茬违规数': {'min': 0, 'max': 0}, '结果_豆类窗口违规数': {'min': 0, 'max': 0}, '结果_容量越界数': {'min': 0, 'max': 0}, '结果_最小面积违规数': {'min': 0, 'max': 0}}
    payload = {'project': '24华为杯C-dsv.1', 'problem': '2024 年国赛 C 题 农作物的种植策略', 'results': results, 'ranges': ranges, 'notes': '本文件为全文唯一结果源；论文、摘要、各问 result.md 与图表数值均引用此文件。'}
    target = BASE / 'results' / 'final_results.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 结果对照表', '', '本表逐条列出唯一结果源中的全部数值，供论文、摘要与结果说明复核引用。', '', '| 结果路径 | 数值 |', '|---|---|']
    lines.extend(flatten(results))
    lines.extend(['', '## 取值范围约束', ''])
    for key, spec in ranges.items():
        lines.append(f'- {key}: 允许区间 [{spec['min']}, {spec['max']}]')
    lines.append('')
    markdown = BASE / 'results' / '结果对照表.md'
    markdown.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(results['汇总指标'], ensure_ascii=False, indent=2))

def flatten(obj, prefix=''):
    rows = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            rows.extend(flatten(value, f'{prefix}.{key}' if prefix else str(key)))
    elif isinstance(obj, (int, float)) and (not isinstance(obj, bool)):
        rows.append(f'| {prefix} | {obj:.4f} |')
    elif isinstance(obj, str):
        rows.append(f'| {prefix} | {obj} |')
    return rows
if __name__ == '__main__':
    main()
