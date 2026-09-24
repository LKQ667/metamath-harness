from __future__ import annotations
import argparse
import glob
import json
import statistics
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / 'results' / 'evaluation'
PLANS = ROOT / 'results' / 'plans'
DATA = ROOT / '赛题' / '_附件解压' / 'data'
if not (DATA / 'config.txt').is_file():
    DATA = ROOT.parent / '_hw_suite' / 'data'
CORES = [1, 2, 3, 4, 5]
CROSS_WAIT = {1: 1000.0, 2: 500.0, 3: 500.0}

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def cases():
    names = []
    for path in sorted(glob.glob(str(EVAL / 'case_*_singlecore_res.json'))):
        names.append(Path(path).name.split('_singlecore_res.json')[0])
    return sorted(set(names))

def result_for(case, problem, cores, suffix=''):
    if cores == 1:
        candidates = [EVAL / f'{case}_singlecore_res.json']
    else:
        candidates = [EVAL / f'{case}_p{problem}_n{cores}{suffix}_res.json', EVAL / f'{case}_p{problem}_n{cores}_res.json']
    for path in candidates:
        if path.exists():
            return load(path)
    return None

def speedup(single, makespan):
    return round(single / makespan, 6) if makespan else None

def aggregate_problem(singles, problem, suffix='', extra_key=None):
    per_case = {}
    average_speedup = {}
    average_makespan = {}
    total_added = {}
    for cores in CORES:
        values, speeds, added = ([], [], [])
        for case, single in singles.items():
            result = result_for(case, problem, cores, suffix)
            if result is None:
                continue
            values.append(result['makespan'])
            added.append(result['data_movement_bytes']['added_copy_bytes'])
            if cores == 1:
                speeds.append(1.0)
            else:
                speeds.append(single / result['makespan'])
        if values:
            average_makespan[str(cores)] = round(statistics.fmean(values), 3)
            average_speedup[str(cores)] = round(statistics.fmean(speeds), 4)
            total_added[str(cores)] = int(sum(added))
    for case, single in singles.items():
        entry = {'singlecore_makespan': single}
        for cores in CORES:
            result = result_for(case, problem, cores, suffix)
            if result is None:
                continue
            item = {'makespan': result['makespan'], 'added_bytes': result['data_movement_bytes']['added_copy_bytes'], 'speedup': 1.0 if cores == 1 else round(single / result['makespan'], 6)}
            if cores > 1 and problem == 1:
                estimate = estimator_scores(case, cores, problem)
                if estimate:
                    item['estimate'] = round(estimate, 3)
                    item['estimate_ratio'] = round(estimate / result['makespan'], 6)
            entry[str(cores)] = item
        per_case[case] = entry
    payload = {'average_speedup': average_speedup, 'average_makespan': average_makespan, 'total_added_bytes': total_added, 'per_case': per_case}
    if extra_key:
        payload.update(extra_key)
    return payload

def estimator_scores(case, cores, problem):
    plan_path = PLANS / f'{case}_p{problem}_n{cores}_plan.json'
    graph_path = DATA / f'{case}.json'
    if not plan_path.exists() or not graph_path.exists():
        return None
    sys.path.insert(0, str(ROOT / 'scripts'))
    from graph_utils import load_graph
    from partition import GraphIndex, PartitionState
    graph = load_graph(graph_path)
    index = GraphIndex(graph)
    plan = load(plan_path)
    subgraph_of = {int(key): value for key, value in plan['node_to_subgraph'].items()}
    core_of_subgraph = {}
    for core, schedule in enumerate(plan['core_schedules']):
        for subgraph in schedule:
            core_of_subgraph[subgraph] = core
    state = PartitionState(index, cores)
    for node in index.order:
        subgraph = subgraph_of[node]
        state.add(node, core_of_subgraph.get(subgraph, 0), subgraph)
    return state.task_objective(CROSS_WAIT[problem], 100.0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(ROOT / 'results' / 'final_results.json'))
    args = parser.parse_args()
    single_path = ROOT / 'results' / 'singlecore_makespan.json'
    singles = load(single_path) if single_path.exists() else {}
    case_names = cases()
    singles = {case: singles[case] for case in case_names if case in singles}
    q1 = aggregate_problem(singles, 1)
    q2 = aggregate_problem(singles, 2)
    q3 = aggregate_problem(singles, 3, suffix='_l2')
    gain = {}
    for cores in CORES:
        ratios = []
        for case, single in singles.items():
            nol2 = result_for(case, 2, cores)
            with_l2 = result_for(case, 3, cores, '_l2')
            if nol2 is None or with_l2 is None or (not with_l2['makespan']):
                continue
            ratios.append(nol2['makespan'] / with_l2['makespan'])
        if ratios:
            gain[str(cores)] = round(statistics.fmean(ratios), 4)
    q3['average_cache_gain'] = gain
    hit_rate = {}
    for cores in CORES:
        rates = []
        for case in singles:
            result = result_for(case, 3, cores, '_l2')
            if result is None:
                continue
            cache = result.get('cache_stats') or {}
            accesses = cache.get('accesses') or 0
            if accesses:
                rates.append(cache.get('hits', 0) / accesses)
        if rates:
            hit_rate[str(cores)] = round(statistics.fmean(rates), 4)
    q3['average_cache_hit_rate'] = hit_rate
    per_case_q3 = {}
    for case, single in singles.items():
        entry = {'singlecore_makespan': single}
        for cores in CORES:
            nol2 = result_for(case, 2, cores)
            with_l2 = result_for(case, 3, cores, '_l2')
            item = {}
            if nol2 is not None:
                item['nol2_makespan'] = nol2['makespan']
                item['nol2_added_bytes'] = nol2['data_movement_bytes']['added_copy_bytes']
            if with_l2 is not None:
                cache = with_l2.get('cache_stats') or {}
                item['l2_makespan'] = with_l2['makespan']
                item['l2_added_bytes'] = with_l2['data_movement_bytes']['added_copy_bytes']
                item['cache_hits'] = cache.get('hits', 0)
                item['cache_accesses'] = cache.get('accesses', 0)
                item['cache_hit_bytes'] = cache.get('hit_bytes', 0)
                if nol2 is not None and with_l2['makespan']:
                    item['cache_gain'] = round(nol2['makespan'] / with_l2['makespan'], 6)
            if item:
                entry[str(cores)] = item
        per_case_q3[case] = entry
    q3['per_case'] = per_case_q3
    profile_path = ROOT / 'data' / 'case_profile.csv'
    profile_summary = {}
    if profile_path.exists():
        import csv
        with profile_path.open(encoding='utf-8') as handle:
            rows = list(csv.DictReader(handle))
        for key in ('ops_core', 'cycles_total', 'critical_path', 'parallel_width', 'ddr_bytes'):
            values = [float(row[key]) for row in rows]
            profile_summary[key] = {'min': min(values), 'median': statistics.median(values), 'max': max(values)}
    payload = {'meta': {'problem_title': '通用神经网络处理器下的多核调度问题', 'competition': '华为杯（中国研究生数学建模竞赛）', 'case_count': len(singles), 'cores': CORES, 'singlecore_source': '赛题官方 singlecore_evaluate.py', 'evaluator_source': '赛题官方 multicore_cut_evaluate_problem_{1,2,3}.py', 'config_source': '赛题官方 data/config.txt'}, 'ranges': {'speedup': {'min': 0.9, 'max': 5.5}, 'cache_hit_rate': {'min': 0.0, 'max': 1.0}}, 'results': {'key_result_q1_average_speedup_2core': q1['average_speedup'].get('2'), 'key_result_q1_average_speedup_5core': q1['average_speedup'].get('5'), 'key_result_q2_average_speedup_5core': q2['average_speedup'].get('5'), 'key_result_q3_average_cache_gain_5core': gain.get('5'), 'key_result_q3_cache_hit_percent_5core': round(float(hit_rate.get('5', 0.0)) * 100.0, 1), 'key_result_q3_cache_hit_rate_5core_fraction': hit_rate.get('5')}, 'profile': profile_summary, 'q1': q1, 'q2': q2, 'q3': q3}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'cases': len(singles), 'q1_speedup': q1['average_speedup'], 'q2_speedup': q2['average_speedup'], 'q3_gain': gain}, ensure_ascii=False))
if __name__ == '__main__':
    main()
