# -*- coding: utf-8 -*-
from __future__ import annotations
import itertools
import json
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import numpy as np
from common_d import RESULTS_DIR, build_scenario, seg_geometry, seg_time, write_json
QDIR = os.path.join(ROOT, 'Q1')
FIGDIR = os.path.join(QDIR, 'figures')
G = 9.81

def eq_range(t, q):
    L0, LF, Q = (t['range_empty'], t['range_full'], t['q_max'])
    q = min(max(q, 0.0), Q)
    return L0 - (L0 - LF) * (q / Q) ** 1.5

def seg_energy(sc, t, i, j, q):
    geom = seg_geometry(sc, i, j)
    e_hor = t['battery_energy'] * geom['d'] / eq_range(t, q)
    e_up = (t['mass_empty'] + q) * G * geom['climb'] / (3600000.0 * t['eta_climb'])
    return e_hor + e_up

def roundtrip_energy(sc, t, area, q):
    o = sc.center['id']
    return seg_energy(sc, t, o, area, q) + seg_energy(sc, t, area, o, 0.0)

def max_safe_payload(sc, t, area, rho=None, tol=1e-05):
    rho = t['reserve_ratio'] if rho is None else rho
    limit = (1.0 - rho) * t['battery_energy']
    if roundtrip_energy(sc, t, area, 0.0) > limit:
        return 0.0
    if roundtrip_energy(sc, t, area, t['q_max']) <= limit:
        return float(t['q_max'])
    lo, hi = (0.0, float(t['q_max']))
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if roundtrip_energy(sc, t, area, mid) <= limit:
            lo = mid
        else:
            hi = mid
    return float(lo)

def sortie_time(sc, t, area, n_boxes):
    o = sc.center['id']
    fly = seg_time(sc, t, o, area) + seg_time(sc, t, area, o)
    return t['t_prepare'] + n_boxes * t['t_load_per_box'] + fly + t['t_handover_base'] + n_boxes * t['t_handover_per_box']

def classify(boxes):
    keyed = {}
    for b in boxes:
        key = (b['cargo'], bool(b['is_first_batch']), b['mass'], b['volume'])
        keyed[key] = keyed.get(key, 0) + 1
    cats = [{'cargo': k[0], 'first_batch': k[1], 'mass': k[2], 'volume': k[3]} for k in keyed]
    cats.sort(key=lambda c: (c['cargo'], not c['first_batch']))
    counts = [keyed[c['cargo'], c['first_batch'], c['mass'], c['volume']] for c in cats]
    return (cats, counts)

def enumerate_patterns(cats, counts, payload_cap, vol_cap, e_fun, t_fun):
    ranges = [range(c + 1) for c in counts]
    pats = []
    for vec in itertools.product(*ranges):
        n = sum(vec)
        if n == 0:
            continue
        m = sum((v * c['mass'] for v, c in zip(vec, cats)))
        vol = sum((v * c['volume'] for v, c in zip(vec, cats)))
        if m > payload_cap + 1e-09 or vol > vol_cap + 1e-09:
            continue
        pats.append({'vec': vec, 'n': n, 'mass': m, 'volume': vol, 'energy': e_fun(m), 'time': t_fun(n)})
    return pats

def solve_area(cats, counts, caps, order):

    def key(c):
        return tuple((c[o] for o in order))
    patterns = []
    for gid, cap in caps.items():
        for p in enumerate_patterns(cats, counts, cap['payload'], cap['volume'], cap['energy_of'], cap['time_of']):
            patterns.append({**p, 'type_id': gid})
    INF = float('inf')
    start = tuple(counts)
    memo = {tuple([0] * len(counts)): {'N': 0, 'E': 0.0, 'T': 0.0, 'plan': []}}

    def rec(state):
        if state in memo:
            return memo[state]
        cand = None
        for p in patterns:
            if any((p['vec'][k] > state[k] for k in range(len(state)))):
                continue
            nxt = tuple((state[k] - p['vec'][k] for k in range(len(state))))
            sub = rec(nxt)
            if sub is None:
                continue
            cost = {'N': sub['N'] + 1, 'E': sub['E'] + p['energy'], 'T': sub['T'] + p['time']}
            if cand is None or key(cost) < key(cand):
                cand = {**cost, 'plan': [p] + sub['plan']}
        memo[state] = cand
        return cand
    sys.setrecursionlimit(10000)
    res = rec(start)
    return res if res is not None else {'N': INF, 'E': INF, 'T': INF, 'plan': None}

def build_caps(sc, area, payload_by_type, rho_by_type=None):
    caps = {}
    for gid, t in sc.types.items():
        qs = payload_by_type[gid]
        if qs <= 0:
            continue
        caps[gid] = {'payload': qs, 'volume': t['vol_max'], 'type': t, 'energy_of': (lambda t=t, a=area: lambda m: roundtrip_energy(sc, t, a, m))(), 'time_of': (lambda t=t, a=area: lambda c: sortie_time(sc, t, a, c))()}
    return caps

def main() -> int:
    sc = build_scenario()
    areas = [a['id'] for a in sc.areas]
    by_area = {}
    for b in sc.boxes:
        by_area.setdefault(b['area_id'], []).append(b)
    cats_by_area, counts_by_area = ({}, {})
    for a in areas:
        cats_by_area[a], counts_by_area[a] = classify(by_area[a])
    payload_tbl = {a: {g: max_safe_payload(sc, t, a) for g, t in sc.types.items()} for a in areas}
    tight = {}
    for gid, t in sc.types.items():
        lim = (1 - t['reserve_ratio']) * t['battery_energy']
        tight[gid] = {}
        for a in areas:
            e = roundtrip_energy(sc, t, a, t['q_max'])
            tight[gid][a] = {'E_full_kWh': e, 'limit_kWh': lim, 'ratio': e / lim}
    print('=== 最大安全载荷 q*(kg) 与满载往返能耗占返航上限比例 ===')
    print('区域      A型(q*/占比)        B型(q*/占比)        C型(q*/占比)')
    for a in areas:
        cells = []
        for gid in ('A', 'B', 'C'):
            cells.append(f'{payload_tbl[a][gid]:6.2f} / {tight[gid][a]['ratio']:5.3f}')
        print(f'{a}   ' + '   '.join(cells))
    print()
    for gid in sc.types:
        vals = [tight[gid][a]['ratio'] for a in areas]
        print(f'  {gid}型 满载往返能耗/返航上限: 最小 {min(vals):.4f} 最大 {max(vals):.4f} 载荷受限区域 {sum((1 for v in vals if v > 1))}/15')
    orders = {'N_E_T': ('N', 'E', 'T'), 'E_N_T': ('E', 'N', 'T'), 'T_N_E': ('T', 'N', 'E')}
    solutions = {}
    for name, order in orders.items():
        plans = {}
        for a in areas:
            caps = build_caps(sc, a, payload_tbl[a])
            plans[a] = solve_area(cats_by_area[a], counts_by_area[a], caps, order)
        tot = {k: sum((plans[a][k] for a in areas)) for k in ('N', 'E', 'T')}
        solutions[name] = {'order': list(order), 'per_area': plans, 'totals': tot}
        print(f'\n=== 字典序 {order} === 架次 {tot['N']}  能耗 {tot['E']:.3f} kWh  累计作业时间 {tot['T']:.1f} s')
    base = solutions['N_E_T']
    print('\n=== N→E→T 最优方案的分区明细 ===')
    print('区域  架次  能耗kWh   作业时间s   机型构成')
    for a in areas:
        p = base['per_area'][a]
        comp = {}
        for s in p['plan']:
            comp[s['type_id']] = comp.get(s['type_id'], 0) + 1
        comp_s = ' '.join((f'{k}×{v}' for k, v in sorted(comp.items())))
        print(f'{a}  {p['N']:3d}  {p['E']:8.3f}  {p['T']:10.1f}   {comp_s}')
    max_box_mass = {a: max((b['mass'] for b in by_area[a])) for a in areas}

    def area_feasible(a, payload_row):
        return any((payload_row[g][a] + 1e-09 >= max_box_mass[a] for g in sc.types))

    def all_feasible(rho):
        row = {g: {a: max_safe_payload(sc, t, a, rho=rho) for a in areas} for g, t in sc.types.items()}
        return (all((area_feasible(a, row) for a in areas)), row)
    ok_hi, _ = all_feasible(0.4)
    rho_crit = None
    if not ok_hi:
        lo, hi = (0.0, 0.4)
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            ok, _r = all_feasible(mid)
            if ok:
                lo = mid
            else:
                hi = mid
        rho_crit = lo
    print(f'\n=== 临界返航安全余量 ===\n  全部货箱可投递的最大 ρ = {('未触发（ρ=0.40 仍可行）' if rho_crit is None else f'{rho_crit:.4f}')}')
    if rho_crit is not None:
        _, row_c = all_feasible(rho_crit + 1e-06)
        bad = [a for a in areas if not area_feasible(a, row_c)]
        print(f'  超过该值后不可投递的服务区: {'、'.join(bad)}（其最重货箱 {max((max_box_mass[a] for a in bad)):.0f} kg 已超出所有机型的安全载荷）')
    rhos = [round(x, 3) for x in np.arange(0.1, 0.4001, 0.01)]
    sens = []
    for rho in rhos:
        row = {'rho': float(rho), 'payload': {}, 'N': None, 'E': None, 'T': None, 'feasible': True, 'infeasible_areas': []}
        for gid, t in sc.types.items():
            row['payload'][gid] = {a: max_safe_payload(sc, t, a, rho=rho) for a in areas}
        bad = [a for a in areas if not area_feasible(a, row['payload'])]
        if bad:
            row['feasible'] = False
            row['infeasible_areas'] = bad
            sens.append(row)
            continue
        n_tot, e_tot, t_tot = (0, 0.0, 0.0)
        for a in areas:
            caps = build_caps(sc, a, {g: row['payload'][g][a] for g in sc.types})
            r = solve_area(cats_by_area[a], counts_by_area[a], caps, ('N', 'E', 'T'))
            n_tot += r['N']
            e_tot += r['E']
            t_tot += r['T']
        row['N'], row['E'], row['T'] = (int(n_tot), float(e_tot), float(t_tot))
        sens.append(row)
    print('\n=== 灵敏度：返航安全余量 ρ ===')
    print(' rho   架次   能耗kWh   作业时间s   q*_C均值  q*_A均值  q*_B均值  可行性')
    for row in sens:
        qa = np.mean(list(row['payload']['A'].values()))
        qb = np.mean(list(row['payload']['B'].values()))
        qc = np.mean(list(row['payload']['C'].values()))
        if row['feasible']:
            print(f'{row['rho']:.2f}  {row['N']:4d}  {row['E']:9.3f}  {row['T']:10.1f}   {qc:8.2f}  {qa:8.2f}  {qb:8.2f}  可行')
        else:
            print(f'{row['rho']:.2f}     -          -           -   {qc:8.2f}  {qa:8.2f}  {qb:8.2f}  不可行({len(row['infeasible_areas'])}区)')
    out = {'最大安全载荷_kg': payload_tbl, '满载往返能耗与返航上限': tight, '组批方案': {n: _ser(solutions[n]) for n in solutions}, '灵敏度_返航余量': _ser(sens), '临界返航余量': rho_crit, '最重货箱_kg': max_box_mass, '类别划分': {a: {'cats': cats_by_area[a], 'counts': counts_by_area[a]} for a in areas}}
    write_json(os.path.join(RESULTS_DIR, 'q1_results.json'), out)
    write_json(os.path.join(QDIR, 'q1_solution.json'), out)
    print('\n已写出 results/q1_results.json 与 Q1/q1_solution.json')
    return 0

def _ser(o):
    if isinstance(o, dict):
        return {str(k): _ser(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_ser(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o
if __name__ == '__main__':
    raise SystemExit(main())
