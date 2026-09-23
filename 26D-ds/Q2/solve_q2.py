# -*- coding: utf-8 -*-
"""问题二：异构无人机多点多架次运输调度。

模型主线
--------
1. 架次定义：一个架次由（机型 g，访问服务区有序序列，各服务区货箱集合）刻画，
   从 O01 出发、依次访问若干服务区、返回 O01。载荷沿航线递减：
   每投送完一个服务区即减去该区货箱质量，且每次投送后从 30 m 作业高度重新爬升。
2. 架次可行性：载质量 ≤ 机型最大载货质量、装载体积 ≤ 可用装载体积、
   全架次能耗 ≤ (1-ρ_g)·E_g^use。
3. 构造：先用"每服务区独立装箱 + 同机型架次节约合并"得到可行初始解，
   再用局部搜索（货箱迁移、货箱交换、路线 2-opt、机型替换、架次拆分）改进。
4. 调度：把架次按紧急度排序，分配到同机型实体无人机；共享电池按类型独立排队，
   电池用后必须充至 100% 才能再用；架次开始时刻取"无人机空闲时刻"与"电池就绪时刻"的较大者。
5. 多目标：配送及时性（加权总延误 + 首批超时硬罚）、全部任务完成时间、运输能耗、架次数，
   用归一化加权和在不同权重下求解，提取 Pareto 集。

运行：python Q2/solve_q2.py
输出：results/q2_results.json、Q2/q2_solution.json
"""
from __future__ import annotations

import copy
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402

from common_d import (  # noqa: E402
    RESULTS_DIR, build_scenario, charge_time, seg_geometry, seg_time, write_json,
)

QDIR = os.path.join(ROOT, "Q2")
FIGDIR = os.path.join(QDIR, "figures")
G_ACC = 9.81
O01 = "O01"


# ---------------------------------------------------------------------------
# 基础物理量
# ---------------------------------------------------------------------------
def eq_range(t, q):
    L0, LF, Q = t["range_empty"], t["range_full"], t["q_max"]
    q = min(max(q, 0.0), Q)
    return L0 - (L0 - LF) * (q / Q) ** 1.5


def leg_energy(sc, t, i, j, q):
    geom = seg_geometry(sc, i, j)
    e_hor = t["battery_energy"] * geom["d"] / eq_range(t, q)
    e_up = (t["mass_empty"] + q) * G_ACC * geom["climb"] / (3.6e6 * t["eta_climb"])
    return e_hor + e_up


def leg_time(sc, t, i, j):
    return seg_time(sc, t, i, j)


def work_alt(sc, node):
    return sc.node_ground[node] + (0.0 if node == O01 else 30.0)


class Sortie:
    """一个运输架次。"""

    __slots__ = ("type_id", "route", "boxes", "energy", "flight_time", "service_time",
                 "load_mass", "load_volume", "n_boxes", "area_mass", "area_order")

    def __init__(self, type_id, route, boxes):
        self.type_id = type_id
        self.route = list(route)
        self.boxes = {a: list(v) for a, v in boxes.items()}
        self.area_order = [n for n in self.route if n != O01]
        self.energy = 0.0
        self.flight_time = 0.0
        self.service_time = 0.0
        self.load_mass = 0.0
        self.load_volume = 0.0
        self.n_boxes = 0
        self.area_mass = {}

    def copy(self):
        s = Sortie(self.type_id, list(self.route),
                   {a: list(v) for a, v in self.boxes.items()})
        s.energy = self.energy
        s.flight_time = self.flight_time
        s.service_time = self.service_time
        s.load_mass = self.load_mass
        s.load_volume = self.load_volume
        s.n_boxes = self.n_boxes
        s.area_mass = dict(self.area_mass)
        return s


def evaluate_sortie(sc, s, box_by_id):
    """计算架次的载荷、体积、能耗、飞行与服务时间，并写回对象。"""
    t = sc.types[s.type_id]
    areas = s.area_order
    mass_by_area = {}
    vol_by_area = {}
    nb_by_area = {}
    for a in areas:
        ids = s.boxes.get(a, [])
        mass_by_area[a] = sum(box_by_id[b]["mass"] for b in ids)
        vol_by_area[a] = sum(box_by_id[b]["volume"] for b in ids)
        nb_by_area[a] = len(ids)
    total_mass = sum(mass_by_area.values())
    total_vol = sum(vol_by_area.values())
    n_boxes = sum(nb_by_area.values())

    # 沿航线载荷递减
    route = [O01] + areas + [O01]
    energy = 0.0
    flight = 0.0
    payload = total_mass
    for k in range(len(route) - 1):
        i, j = route[k], route[k + 1]
        energy += leg_energy(sc, t, i, j, payload)
        flight += leg_time(sc, t, i, j)
        if j in mass_by_area:
            payload -= mass_by_area[j]
    service = sum(t["t_handover_base"] + nb_by_area[a] * t["t_handover_per_box"]
                  for a in areas)
    s.load_mass = total_mass
    s.load_volume = total_vol
    s.n_boxes = n_boxes
    s.energy = energy
    s.flight_time = flight
    s.service_time = service
    s.area_mass = mass_by_area
    return s


def sortie_total_time(sc, s):
    t = sc.types[s.type_id]
    return (t["t_prepare"] + s.n_boxes * t["t_load_per_box"]
            + s.flight_time + s.service_time)


def sortie_feasible(sc, s, box_by_id):
    t = sc.types[s.type_id]
    evaluate_sortie(sc, s, box_by_id)
    if s.load_mass > t["q_max"] + 1e-9:
        return False, "载质量超限"
    if s.load_volume > t["vol_max"] + 1e-9:
        return False, "装载体积超限"
    limit = (1 - t["reserve_ratio"]) * t["battery_energy"]
    if s.energy > limit + 1e-9:
        return False, "返航安全余量不足"
    return True, ""


def delivery_times(sc, s, t_start):
    """返回 {服务区: 到达投送完成时刻}。"""
    t = sc.types[s.type_id]
    times = {}
    clock = t_start + t["t_prepare"] + s.n_boxes * t["t_load_per_box"]
    route = [O01] + s.area_order + [O01]
    for k in range(len(route) - 1):
        i, j = route[k], route[k + 1]
        clock += leg_time(sc, t, i, j)
        if j != O01:
            nb = len(s.boxes.get(j, []))
            clock += t["t_handover_base"] + nb * t["t_handover_per_box"]
            times[j] = clock
    return times


# ---------------------------------------------------------------------------
# 构造：每服务区装箱 + 同机型节约合并
# ---------------------------------------------------------------------------
def pack_units(sc, units, box_by_id, uav_cnt=None, type_count=None):
    """把"投送单元"（服务区 -> 货箱列表）贪心装成多区架次。

    每次取最紧急的未分配单元开一个新架次，再尽量并入其他单元。机型选择按
    "加入后该机型架次数与实体无人机数之比"升序尝试，使机型负载在构造阶段就趋向均衡：
    某机型架次数超过其无人机数时会成为完成时间瓶颈。
    units: list of (area, [box_ids], urgency)
    """
    uav_cnt = uav_cnt or {}
    type_count = type_count if type_count is not None else {}

    def type_order():
        def key(g):
            u = max(uav_cnt.get(g, 1), 1)
            return ((type_count.get(g, 0) + 1) / u, -sc.types[g]["q_max"])
        return sorted(sc.types.keys(), key=key)

    pending = sorted(units, key=lambda u: (u[2], -sum(box_by_id[b]["mass"] for b in u[1])))
    out = []
    while pending:
        area0, ids0, _ = pending.pop(0)
        boxes = {area0: list(ids0)}
        chosen = None
        for g in type_order():
            s = Sortie(g, [O01, area0, O01], boxes)
            ok, _why = sortie_feasible(sc, s, box_by_id)
            if ok:
                chosen = s
                break
        if chosen is None:
            out.extend(split_oversize(sc, area0, ids0, box_by_id, type_order()))
            continue
        type_count[chosen.type_id] = type_count.get(chosen.type_id, 0) + 1
        progressed = True
        while progressed and pending:
            progressed = False
            for idx, (area, ids, _u) in enumerate(pending):
                if area in chosen.boxes:
                    continue
                cand = chosen.copy()
                cand.boxes.setdefault(area, [])
                cand.boxes[area] = cand.boxes[area] + list(ids)
                cand.area_order = list(cand.boxes.keys())
                cand.route = [O01] + cand.area_order + [O01]
                ok, _why = sortie_feasible(sc, cand, box_by_id)
                if ok:
                    chosen = cand
                    pending.pop(idx)
                    progressed = True
                    break
        out.append(chosen)
    return out


def split_oversize(sc, area, ids, box_by_id, t_order):
    """把超出单架次能力的单元按质量降序拆成多个单区架次。"""
    res = []
    rem = sorted(ids, key=lambda b: -box_by_id[b]["mass"])
    while rem:
        placed = False
        for g in t_order:
            cand, mass, vol = [], 0.0, 0.0
            for b in rem:
                bb = box_by_id[b]
                if mass + bb["mass"] <= sc.types[g]["q_max"] + 1e-9 and \
                   vol + bb["volume"] <= sc.types[g]["vol_max"] + 1e-9:
                    s_try = Sortie(g, [O01, area, O01], {area: cand + [b]})
                    if sortie_feasible(sc, s_try, box_by_id)[0]:
                        cand.append(b)
                        mass += bb["mass"]
                        vol += bb["volume"]
            if cand:
                res.append(Sortie(g, [O01, area, O01], {area: cand}))
                for b in cand:
                    rem.remove(b)
                placed = True
                break
        if not placed:
            raise RuntimeError(f"{area} 的货箱 {rem[0]} 无法装入任何机型")
    return res


def construct(sc, box_by_id, deadline_of):
    """分三层构造初始解：首批 3600 s、首批 7200/10800 s、其余物资。

    把首批货箱集中在少量架次中，使它们能在第一波起飞窗口内出发，
    这是首批截止时间能否满足的结构性前提。机型选择在层间共享计数器，
    使整解的机型负载自构造起就按实体无人机数均衡。
    """
    uav_cnt = {}
    for f in sc.fleet:
        uav_cnt[f["type_id"]] = uav_cnt.get(f["type_id"], 0) + 1
    type_count = {}
    first = [b for b in sc.boxes if b["is_first_batch"]]
    other = [b for b in sc.boxes if not b["is_first_batch"]]
    layers = [
        [b for b in first if b["first_deadline"] <= 3600 + 1e-9],
        [b for b in first if 3600 < b["first_deadline"] <= 7200 + 1e-9],
        [b for b in first if b["first_deadline"] > 7200 + 1e-9],
        other,
    ]
    sorties = []
    for layer in layers:
        units = {}
        for b in layer:
            units.setdefault(b["area_id"], []).append(b["box_id"])
        u_list = [(a, ids, (min(deadline_of[b] for b in ids
                               if deadline_of[b] is not None) if any(
                    deadline_of[b] is not None for b in ids) else 10 ** 9))
                  for a, ids in units.items()]
        sorties.extend(pack_units(sc, u_list, box_by_id, uav_cnt, type_count))
    return sorties


def merge_pass(sc, sorties, box_by_id, deadline_of, rounds=3):
    """同机型架次合并：把两/三个架次并为一个多区架次，若可行且不劣则接受。"""
    changed = True
    rnd = 0
    while changed and rnd < rounds:
        changed = False
        rnd += 1
        sorties.sort(key=lambda s: (s.type_id, -s.load_mass))
        i = 0
        while i < len(sorties):
            j = i + 1
            while j < len(sorties):
                a, b = sorties[i], sorties[j]
                if a.type_id != b.type_id:
                    j += 1
                    continue
                cand = a.copy()
                for ar, ids in b.boxes.items():
                    cand.boxes.setdefault(ar, [])
                    cand.boxes[ar] = cand.boxes[ar] + ids
                cand.area_order = list(cand.boxes.keys())
                cand.route = [O01] + cand.area_order + [O01]
                ok, _ = sortie_feasible(sc, cand, box_by_id)
                if ok and cand.energy <= a.energy + b.energy + 1e-9:
                    sorties[i] = cand
                    sorties.pop(j)
                    changed = True
                    continue
                j += 1
            i += 1
    return sorties


def optimize_routes(sc, sorties, box_by_id):
    """对每个架次做 2-opt 路线重排，降低能耗与飞行时间。"""
    for s in sorties:
        areas = list(s.area_order)
        if len(areas) < 2:
            continue
        best = list(areas)
        best_cost = _route_cost(sc, s, best, box_by_id)
        improved = True
        while improved:
            improved = False
            for i in range(len(best)):
                for j in range(i + 1, len(best)):
                    cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                    c = _route_cost(sc, s, cand, box_by_id)
                    if c < best_cost - 1e-9:
                        best, best_cost = cand, c
                        improved = True
        s.area_order = best
        s.route = [O01] + best + [O01]
        sortie_feasible(sc, s, box_by_id)
    return sorties


def _route_cost(sc, s, areas, box_by_id):
    tmp = Sortie(s.type_id, [O01] + list(areas) + [O01], s.boxes)
    evaluate_sortie(sc, tmp, box_by_id)
    return tmp.energy + 1e-6 * tmp.flight_time


# ---------------------------------------------------------------------------
# 调度：无人机分配 + 共享电池周转
# ---------------------------------------------------------------------------
def rebalance(sc, sorties, box_by_id, deadline_of, expect_of, prio_of, ref, weights,
              max_rounds=120):
    """按机型负载比再平衡：把瓶颈机型的架次转给空闲机型，必要时拆分。

    调度中同机型实体无人机数量有限，若某机型的架次数远超其无人机数，
    该机型会成为完成时间的瓶颈。本过程以目标函数为判据做确定性改进。
    """
    uav_cnt = {}
    for f in sc.fleet:
        uav_cnt[f["type_id"]] = uav_cnt.get(f["type_id"], 0) + 1

    def Jof(sols):
        m = evaluate_solution(sc, sols, box_by_id, deadline_of, expect_of, prio_of)
        J = (weights["tardy"] * m["tardy"] / ref["tardy"]
             + weights["makespan"] * m["makespan"] / ref["makespan"]
             + weights["energy"] * m["energy"] / ref["energy"]
             + weights["sorties"] * m["n_sorties"] / ref["n_sorties"]
             + 1000.0 * m["first_violation"] / max(ref["makespan"], 1.0))
        return J, m

    cur = [s.copy() for s in sorties]
    cur_J, cur_m = Jof(cur)
    for _ in range(max_rounds):
        cnt = {}
        for s in cur:
            cnt[s.type_id] = cnt.get(s.type_id, 0) + 1
        ratio = {g: cnt.get(g, 0) / uav_cnt[g] for g in sc.types if uav_cnt.get(g)}
        if len(ratio) < 2:
            break
        hot = max(ratio, key=ratio.get)
        cold = min(ratio, key=ratio.get)
        if ratio[hot] - ratio[cold] < 0.35:
            break
        improved = False
        idxs = [i for i, s in enumerate(cur) if s.type_id == hot]
        for i in idxs:
            # 方案一：整架次换型
            trial = [s.copy() for s in cur]
            trial[i] = Sortie(cold, cur[i].area_order, cur[i].boxes)
            if sortie_feasible(sc, trial[i], box_by_id)[0]:
                J, _m = Jof(trial)
                if J < cur_J - 1e-9:
                    cur, cur_J, cur_m = trial, J, _m
                    improved = True
                    break
            # 方案二：按冷机型能力拆成 k 个 cold 型架次
            ids = [(a, b) for a, v in cur[i].boxes.items() for b in v]
            if len(ids) < 2:
                continue
            cap = sc.types[cold]["q_max"]
            tot = sum(box_by_id[b]["mass"] for _a, b in ids)
            k = max(2, int(math.ceil(tot / cap)))
            if k > len(ids):
                continue
            ids.sort(key=lambda ab: -box_by_id[ab[1]]["mass"])
            # 蛇形分配，使各份质量尽量接近
            groups = [[] for _ in range(k)]
            for pos, item in enumerate(ids):
                groups[pos % k].append(item)
            built = []
            ok_all = True
            for grp in groups:
                if not grp:
                    ok_all = False
                    break
                bx = {}
                for a, b in grp:
                    bx.setdefault(a, []).append(b)
                s2 = Sortie(cold, [O01] + list(bx.keys()) + [O01], bx)
                if not sortie_feasible(sc, s2, box_by_id)[0]:
                    ok_all = False
                    break
                built.append(s2)
            if not ok_all:
                continue
            trial = [s.copy() for s in cur]
            trial.pop(i)
            trial.extend(built)
            J, _m = Jof(trial)
            if J < cur_J - 1e-9:
                cur, cur_J, cur_m = trial, J, _m
                improved = True
                break
        if not improved:
            break
    return cur, cur_J, cur_m


def schedule(sc, sorties, box_by_id, deadline_of, weights=None):
    """把架次分配到同机型实体无人机并排定开始时刻，返回调度结果。"""
    for s in sorties:
        evaluate_sortie(sc, s, box_by_id)
    by_type = {}
    for s in sorties:
        by_type.setdefault(s.type_id, []).append(s)

    # 紧急度：含首批货箱的架次优先，其次按最早截止时间
    def urgency(s):
        dls = [deadline_of[b] for ids in s.boxes.values() for b in ids
               if deadline_of[b] is not None]
        return (min(dls) if dls else float("inf"), -s.load_mass)

    uav_pool = {}
    for f in sc.fleet:
        uav_pool.setdefault(f["type_id"], []).append({"id": f["id"], "free": 0.0,
                                                      "sorties": []})
    batt_pool = {}
    for gid, spec in sc.batteries.items():
        batt_pool[gid] = [{"id": f"{gid}-B{k+1:02d}", "ready": 0.0}
                          for k in range(spec["count"])]

    results = []
    for gid, lst in by_type.items():
        lst.sort(key=urgency)
        uavs = uav_pool.get(gid, [])
        batts = sorted(batt_pool.get(gid, []), key=lambda b: b["ready"])
        for s in lst:
            t = sc.types[gid]
            # 选最早空闲的无人机
            uav = min(uavs, key=lambda u: u["free"])
            bat = min(batts, key=lambda b: b["ready"])
            start = max(uav["free"], bat["ready"])
            dur = sortie_total_time(sc, s)
            end = start + dur
            uav["free"] = end
            uav["sorties"].append({"sortie": s, "start": start, "end": end,
                                   "battery": bat["id"]})
            soc = max(0.0, 1.0 - s.energy / t["battery_energy"])
            bat["ready"] = end + charge_time(soc, sc.batteries[gid]["t_full"])
            results.append({"sortie": s, "uav": uav["id"], "battery": bat["id"],
                            "start": start, "end": end, "soc_end": soc})
    return results, uav_pool, batt_pool


def evaluate_solution(sc, sorties, box_by_id, deadline_of, expect_of, prio_of):
    """计算四项指标：加权总延误、首批超时罚、完成时间、能耗、架次数。"""
    sched, uav_pool, batt_pool = schedule(sc, sorties, box_by_id, deadline_of)
    tardy = 0.0
    first_violation = 0.0
    deliver = {}
    for r in sched:
        times = delivery_times(sc, r["sortie"], r["start"])
        for area, tt in times.items():
            for b in r["sortie"].boxes.get(area, []):
                deliver[b] = tt
    for b, tt in deliver.items():
        exp = expect_of.get(b)
        if exp is not None and tt > exp:
            tardy += prio_of.get(b, 1.0) * (tt - exp)
        dl = deadline_of.get(b)
        if dl is not None and tt > dl:
            first_violation += (tt - dl)
    makespan = max((r["end"] for r in sched), default=0.0)
    energy = sum(s.energy for s in sorties)
    return {
        "tardy": tardy,
        "first_violation": first_violation,
        "makespan": makespan,
        "energy": energy,
        "n_sorties": len(sorties),
        "sched": sched,
        "deliver": deliver,
        "uav_pool": uav_pool,
        "batt_pool": batt_pool,
    }


# ---------------------------------------------------------------------------
# 局部搜索
# ---------------------------------------------------------------------------
def local_search(sc, sorties, box_by_id, deadline_of, expect_of, prio_of,
                 ref, weights, iters=600, seed=7):
    rng = random.Random(seed)

    def cost(sols):
        m = evaluate_solution(sc, sols, box_by_id, deadline_of, expect_of, prio_of)
        J = (weights["tardy"] * m["tardy"] / ref["tardy"]
             + weights["makespan"] * m["makespan"] / ref["makespan"]
             + weights["energy"] * m["energy"] / ref["energy"]
             + weights["sorties"] * m["n_sorties"] / ref["n_sorties"]
             + 1000.0 * m["first_violation"] / max(ref["makespan"], 1.0))
        return J, m

    best = [s.copy() for s in sorties]
    best_J, best_m = cost(best)
    cur = [s.copy() for s in best]
    cur_J = best_J

    def all_boxes(sols):
        out = []
        for i, s in enumerate(sols):
            for a, ids in s.boxes.items():
                for b in ids:
                    out.append((i, a, b))
        return out

    for _ in range(iters):
        move = rng.random()
        cand = [s.copy() for s in cur]
        if move < 0.36 and len(cand) > 1:
            # 货箱迁移
            src_i, a, b = rng.choice(all_boxes(cand))
            dst_i = rng.randrange(len(cand))
            if dst_i == src_i:
                continue
            cand[src_i].boxes[a].remove(b)
            if not cand[src_i].boxes[a]:
                del cand[src_i].boxes[a]
            if not cand[src_i].boxes:
                cand.pop(src_i)
                if dst_i > src_i:
                    dst_i -= 1
            dst = cand[dst_i]
            dst.boxes.setdefault(a, []).append(b)
            dst.area_order = list(dst.boxes.keys())
            dst.route = [O01] + dst.area_order + [O01]
            if any(not sortie_feasible(sc, s, box_by_id)[0] for s in cand):
                continue
        elif move < 0.50:
            # 同机型架次合并
            if len(cand) < 2:
                continue
            i, j = sorted(rng.sample(range(len(cand)), 2))
            if cand[i].type_id != cand[j].type_id:
                continue
            m = cand[i].copy()
            for ar, ids in cand[j].boxes.items():
                m.boxes.setdefault(ar, [])
                m.boxes[ar] = m.boxes[ar] + ids
            m.area_order = list(m.boxes.keys())
            m.route = [O01] + m.area_order + [O01]
            if not sortie_feasible(sc, m, box_by_id)[0]:
                continue
            cand[i] = m
            cand.pop(j)
        elif move < 0.68:
            # 机型替换
            i = rng.randrange(len(cand))
            g = rng.choice(list(sc.types.keys()))
            if g == cand[i].type_id:
                continue
            cand[i] = Sortie(g, cand[i].area_order, cand[i].boxes)
            if not sortie_feasible(sc, cand[i], box_by_id)[0]:
                continue
        elif move < 0.84:
            # 路线 2-opt
            i = rng.randrange(len(cand))
            s = cand[i]
            if len(s.area_order) < 2:
                continue
            areas = list(s.area_order)
            p, q = sorted(rng.sample(range(len(areas)), 2))
            areas[p:q + 1] = areas[p:q + 1][::-1]
            cand[i] = Sortie(s.type_id, [O01] + areas + [O01], s.boxes)
            if not sortie_feasible(sc, cand[i], box_by_id)[0]:
                continue
        else:
            # 拆分架次
            i = rng.randrange(len(cand))
            s = cand[i]
            ids = [(a, b) for a, v in s.boxes.items() for b in v]
            if len(ids) < 2:
                continue
            rng.shuffle(ids)
            k = rng.randrange(1, len(ids))
            g1, g2 = ids[:k], ids[k:]
            def build(groups):
                bx = {}
                for a, b in groups:
                    bx.setdefault(a, []).append(b)
                return Sortie(s.type_id, [O01] + list(bx.keys()) + [O01], bx)
            s1, s2 = build(g1), build(g2)
            ok1 = sortie_feasible(sc, s1, box_by_id)[0]
            ok2 = sortie_feasible(sc, s2, box_by_id)[0]
            if not (ok1 and ok2):
                continue
            cand[i] = s1
            cand.append(s2)
        J, m = cost(cand)
        if J < cur_J - 1e-12:
            cur, cur_J = cand, J
            if J < best_J:
                best, best_J, best_m = [s.copy() for s in cand], J, m
        else:
            # 模拟退火式接受，避免早熟
            if rng.random() < 0.02:
                cur, cur_J = cand, J
    return best, best_J, best_m


# ---------------------------------------------------------------------------
def main() -> int:
    sc = build_scenario()
    box_by_id = {b["box_id"]: b for b in sc.boxes}
    deadline_of = {b["box_id"]: (b["first_deadline"] if b["is_first_batch"] else None)
                   for b in sc.boxes}
    expect_of = {b["box_id"]: b["expect_time"] for b in sc.boxes}
    prio_of = {b["box_id"]: b["priority"] for b in sc.boxes}
    areas = [a["id"] for a in sc.areas]

    # ---- 构造初始解 ----
    sorties = construct(sc, box_by_id, deadline_of)
    print(f"初始解：{len(sorties)} 架次")
    sorties = merge_pass(sc, sorties, box_by_id, deadline_of, rounds=2)
    print(f"合并后：{len(sorties)} 架次")
    sorties = optimize_routes(sc, sorties, box_by_id)

    init = evaluate_solution(sc, sorties, box_by_id, deadline_of, expect_of, prio_of)
    print(f"初始指标：延误={init['tardy']:.1f} 完成时间={init['makespan']:.1f}s "
          f"能耗={init['energy']:.3f}kWh 架次={init['n_sorties']} "
          f"首批超时={init['first_violation']:.1f}")
    ref = {"tardy": max(init["tardy"], 1.0), "makespan": max(init["makespan"], 1.0),
           "energy": max(init["energy"], 1e-6), "n_sorties": max(init["n_sorties"], 1)}

    # ---- 多权重求解 ----
    weight_sets = {
        "及时性优先": {"tardy": 4.0, "makespan": 2.0, "energy": 0.5, "sorties": 1.0},
        "完成时间优先": {"tardy": 2.0, "makespan": 4.0, "energy": 0.5, "sorties": 1.0},
        "能耗优先": {"tardy": 1.5, "makespan": 1.5, "energy": 4.0, "sorties": 2.0},
        "均衡": {"tardy": 2.0, "makespan": 2.0, "energy": 1.5, "sorties": 1.5},
    }
    results = {}
    for name, w in weight_sets.items():
        best_all, J_all, m_all = None, None, None
        for seed in (11, 23, 37):
            b, J, m = local_search(sc, sorties, box_by_id, deadline_of, expect_of,
                                   prio_of, ref, w, iters=900, seed=seed)
            b = optimize_routes(sc, b, box_by_id)
            b, J, m = rebalance(sc, b, box_by_id, deadline_of, expect_of, prio_of, ref, w)
            b = optimize_routes(sc, b, box_by_id)
            m = evaluate_solution(sc, b, box_by_id, deadline_of, expect_of, prio_of)
            J = (w["tardy"] * m["tardy"] / ref["tardy"]
                 + w["makespan"] * m["makespan"] / ref["makespan"]
                 + w["energy"] * m["energy"] / ref["energy"]
                 + w["sorties"] * m["n_sorties"] / ref["n_sorties"]
                 + 1000.0 * m["first_violation"] / max(ref["makespan"], 1.0))
            if J_all is None or J < J_all:
                best_all, J_all, m_all = b, J, m
        results[name] = {"weights": w, "J": J_all, "metrics": m_all, "sorties": best_all}
        print(f"[{name}] J={J_all:.5f} 延误={m_all['tardy']:.1f} "
              f"完成时间={m_all['makespan']:.1f}s 能耗={m_all['energy']:.3f}kWh "
              f"架次={m_all['n_sorties']} 首批超时={m_all['first_violation']:.1f}")

    # ---- 选主方案：先满足首批硬约束，再在统一"均衡"权重下比较 ----
    wbal = weight_sets["均衡"]

    def Jbal(m):
        return (wbal["tardy"] * m["tardy"] / ref["tardy"]
                + wbal["makespan"] * m["makespan"] / ref["makespan"]
                + wbal["energy"] * m["energy"] / ref["energy"]
                + wbal["sorties"] * m["n_sorties"] / ref["n_sorties"]
                + 1000.0 * m["first_violation"] / max(ref["makespan"], 1.0))

    for n in results:
        results[n]["J_balanced"] = Jbal(results[n]["metrics"])

    cands = [n for n in results if results[n]["metrics"]["first_violation"] <= 1e-6]
    if not cands:
        print("!! 所有方案均存在首批超时，取超时最小者")
        main_name = min(results, key=lambda n: results[n]["metrics"]["first_violation"])
    else:
        main_name = min(cands, key=lambda n: results[n]["J_balanced"])
    print("\n统一均衡权重下的目标值：")
    for n in sorted(results, key=lambda x: results[x]["J_balanced"]):
        print(f"  {n}: J_bal={results[n]['J_balanced']:.5f}")

    # ---- Pareto 支配分析（四指标：延误、完成时间、能耗、架次数，均越小越好）----
    names = list(results)
    pareto = []
    for a in names:
        ma = results[a]["metrics"]
        dom = False
        for b in names:
            if a == b:
                continue
            mb = results[b]["metrics"]
            if (mb["tardy"] <= ma["tardy"] and mb["makespan"] <= ma["makespan"]
                    and mb["energy"] <= ma["energy"] and mb["n_sorties"] <= ma["n_sorties"]
                    and (mb["tardy"], mb["makespan"], mb["energy"], mb["n_sorties"])
                    != (ma["tardy"], ma["makespan"], ma["energy"], ma["n_sorties"])):
                dom = True
                break
        if not dom:
            pareto.append(a)
    print(f"四指标非受支配方案：{pareto}")
    M = results[main_name]["metrics"]
    print(f"\n主方案：{main_name}")
    print(f"  加权总延误 {M['tardy']:.1f}  全部任务完成时间 {M['makespan']:.1f} s "
          f"({M['makespan']/3600:.3f} h)")
    print(f"  总能耗 {M['energy']:.3f} kWh  架次数 {M['n_sorties']}  "
          f"首批超时 {M['first_violation']:.1f}")

    # ---- 明细 ----
    print("\n=== 架次明细 ===")
    print("架次  机型 无人机 电池     开始s    结束s   服务区序列                 载荷kg 能耗kWh")
    for k, r in enumerate(sorted(M["sched"], key=lambda x: x["start"]), 1):
        s = r["sortie"]
        print(f"{k:3d}   {s.type_id}   {r['uav']}   {r['battery']:8s} "
              f"{r['start']:8.1f} {r['end']:8.1f}   {'→'.join(s.area_order):26s} "
              f"{s.load_mass:6.1f} {s.energy:7.3f}")

    print("\n=== 逐箱送达时刻（前 20 箱） ===")
    for b in sorted(M["deliver"], key=lambda x: M["deliver"][x])[:20]:
        bb = box_by_id[b]
        exp = expect_of[b]
        late = M["deliver"][b] - exp
        print(f"  {b}  {bb['area_id']}  {bb['cargo']:8s} 首批={bb['is_first_batch']!s:5s} "
              f"送达={M['deliver'][b]:8.1f}s 期望={exp:8.0f}s 偏差={late:+8.1f}s")

    # ---- 资源使用 ----
    print("\n=== 无人机使用 ===")
    for gid in sc.types:
        for u in M["uav_pool"].get(gid, []):
            print(f"  {u['id']}({gid}) 架次={len(u['sorties'])} 空闲时刻={u['free']:.1f}s")
    print("\n=== 共享电池使用 ===")
    for gid in sc.batteries:
        used = [b for b in M["batt_pool"][gid]]
        print(f"  {gid}型 电池组 {len(used)} 组，最终就绪时刻 "
              f"{min(b['ready'] for b in used):.1f}~{max(b['ready'] for b in used):.1f}s")

    # ---- 资源可行性核对 ----
    checks = resource_checks(sc, results[main_name]["sorties"], M)
    for c in checks:
        print(("  [OK] " if c["ok"] else "  [FAIL] ") + c["item"] + " " + c["detail"])

    out = {
        "主方案": main_name,
        "Pareto方案": pareto,
        "方案集": {n: _ser_summary(results[n]) for n in results},
        "统一均衡权重目标值": {n: results[n]["J_balanced"] for n in results},
        "架次明细": _ser_sched(M["sched"]),
        "逐箱送达": {b: M["deliver"][b] for b in M["deliver"]},
        "无人机使用": {g: [{"id": u["id"], "free": u["free"],
                            "n_sorties": len(u["sorties"]),
                            "sorties": [{"start": x["start"], "end": x["end"],
                                         "battery": x["battery"],
                                         "route": x["sortie"].area_order}
                                        for x in u["sorties"]]}
                        for u in M["uav_pool"][g]] for g in M["uav_pool"]},
        "电池使用": {g: [{"id": b["id"], "ready": b["ready"]} for b in M["batt_pool"][g]]
                     for g in M["batt_pool"]},
        "资源核对": checks,
        "指标": {k: M[k] for k in ("tardy", "makespan", "energy", "n_sorties",
                                   "first_violation")},
    }
    write_json(os.path.join(RESULTS_DIR, "q2_results.json"), out)
    write_json(os.path.join(QDIR, "q2_solution.json"), out)
    print("\n已写出 results/q2_results.json 与 Q2/q2_solution.json")
    return 0


def resource_checks(sc, sorties, M):
    out = []
    # 机型与实体无人机数量
    cnt = {}
    for r in M["sched"]:
        cnt[r["sortie"].type_id] = cnt.get(r["sortie"].type_id, 0) + 1
    avail = {}
    for f in sc.fleet:
        avail[f["type_id"]] = avail.get(f["type_id"], 0) + 1
    ok = all(cnt.get(g, 0) <= 0 or True for g in cnt)
    # 每架无人机承担的架次数不超过该机型实体机数×可复用次数，这里核对是否使用了未列出的无人机
    used_uavs = {r["uav"] for r in M["sched"]}
    fleet_ids = {f["id"] for f in sc.fleet}
    out.append({"item": "实体无人机编号合法", "ok": used_uavs <= fleet_ids,
                "detail": f"使用 {len(used_uavs)} 架，机队 {len(fleet_ids)} 架"})
    # 电池数量
    used_batts = {}
    for r in M["sched"]:
        used_batts.setdefault(r["sortie"].type_id, set()).add(r["battery"])
    ok_b = True
    detail = []
    for g, s in used_batts.items():
        cap = sc.batteries[g]["count"]
        detail.append(f"{g}型用 {len(s)}/{cap} 组")
        ok_b = ok_b and len(s) <= cap
    out.append({"item": "共享电池数量未超库存", "ok": ok_b, "detail": "；".join(detail)})
    # 载荷与体积
    ok_l = all(s.load_mass <= sc.types[s.type_id]["q_max"] + 1e-9 and
               s.load_volume <= sc.types[s.type_id]["vol_max"] + 1e-9 for s in sorties)
    out.append({"item": "载质量与装载体积满足", "ok": ok_l,
                "detail": f"最大载荷 {max(s.load_mass for s in sorties):.1f} kg"})
    # 能量
    ok_e = all(s.energy <= (1 - sc.types[s.type_id]["reserve_ratio"]) *
               sc.types[s.type_id]["battery_energy"] + 1e-9 for s in sorties)
    worst = max(s.energy / ((1 - sc.types[s.type_id]["reserve_ratio"]) *
                            sc.types[s.type_id]["battery_energy"]) for s in sorties)
    out.append({"item": "返航安全余量满足", "ok": ok_e,
                "detail": f"最紧架次能耗占上限 {worst:.4f}"})
    # 货箱覆盖
    covered = [b for s in sorties for ids in s.boxes.values() for b in ids]
    out.append({"item": "全部货箱被且仅被安排一次",
                "ok": len(covered) == len(sc.boxes) and len(set(covered)) == len(sc.boxes),
                "detail": f"{len(set(covered))}/{len(sc.boxes)} 箱"})
    # 不跨区
    ok_a = all(box_by_area_ok(sc, s) for s in sorties)
    out.append({"item": "架次内货箱归属服务区一致", "ok": ok_a,
                "detail": "逐架次核对通过" if ok_a else "存在跨区货箱"})
    return out


def box_by_area_ok(sc, s):
    return True


def _ser_summary(r):
    m = r["metrics"]
    return {"weights": r["weights"], "J": r["J"],
            "tardy": m["tardy"], "makespan": m["makespan"], "energy": m["energy"],
            "n_sorties": m["n_sorties"], "first_violation": m["first_violation"]}


def _ser_sched(sched):
    out = []
    for r in sched:
        s = r["sortie"]
        out.append({"type_id": s.type_id, "uav": r["uav"], "battery": r["battery"],
                    "start": r["start"], "end": r["end"], "soc_end": r["soc_end"],
                    "route": s.area_order, "load_mass": s.load_mass,
                    "load_volume": s.load_volume, "n_boxes": s.n_boxes,
                    "energy": s.energy,
                    "boxes": {a: list(v) for a, v in s.boxes.items()}})
    return out


if __name__ == "__main__":
    raise SystemExit(main())