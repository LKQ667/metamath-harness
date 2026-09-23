# -*- coding: utf-8 -*-
"""问题四：救援任务分区与资源配置优化方案。

模型主线
--------
1. 同架次约束图：以问题三的运输架次为边、服务区为点，构建"必须同组"关系图，
   取其连通分量作为不可拆分的基本单元。
2. 任务分区：在基本单元之上按空间邻近与工作量均衡构造 2 组与 3 组分方案；
   若同架次约束把全部服务区连成一个分量，则按"分区后重新组批"的口径执行，
   即保持货箱归属、访问顺序与通信保障关系不变，只把跨组架次按组拆分为组内架次。
3. 组内独立核算：对每个任务组独立重跑"装箱—合并—调度—通信保障"链路，
   得到该组所需的运输无人机数、共享电池数、中继无人机数与中继能源组件数。
4. 对比维度：资源配置规模、资源冗余、组间工作量均衡、与现有库存的资源缺口。

运行：python Q4/solve_q4.py
输出：results/q4_results.json、Q4/q4_solution.json
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "Q2"))
sys.path.insert(0, os.path.join(ROOT, "Q3"))

import numpy as np  # noqa: E402

from common_d import RESULTS_DIR, build_scenario, charge_time, write_json  # noqa: E402
import solve_q2 as Q2  # noqa: E402
import solve_q3 as Q3  # noqa: E402

QDIR = os.path.join(ROOT, "Q4")
FIGDIR = os.path.join(QDIR, "figures")
O01 = "O01"
RELAY_SEARCH_CAP = 10


# ---------------------------------------------------------------------------
# 同架次约束图
# ---------------------------------------------------------------------------
def colocation_components(sc, transport_sorties):
    """由问题三运输架次的"同架次"关系求必须同组的基本单元（连通分量）。"""
    parent = {a["id"]: a["id"] for a in sc.areas}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    edges = 0
    for s in transport_sorties:
        route = s["route"]
        for i in range(len(route) - 1):
            union(route[i], route[i + 1])
            edges += 1
    comps = {}
    for a in sc.areas:
        comps.setdefault(find(a["id"]), []).append(a["id"])
    return [sorted(v) for v in comps.values()], edges


# ---------------------------------------------------------------------------
# 分区构造：空间邻近 + 工作量均衡
# ---------------------------------------------------------------------------
def build_partition(sc, boxes_by_area, k):
    """把 15 个服务区划分为 k 个空间连贯且工作量较均衡的任务组。

    以加权质量与质心为基准做角度扫描切分：按绕全局质心的极角排序后，
    在 k-1 个切点处切分，使各组的"需求质量 + 空间跨度"综合代价最小。
    """
    areas = [a["id"] for a in sc.areas]
    pos = {a["id"]: (a["lon"], a["lat"]) for a in sc.areas}
    mass = {a: sum(b["mass"] for b in boxes_by_area.get(a, [])) for a in areas}
    clon = np.mean([pos[a][0] for a in areas])
    clat = np.mean([pos[a][1] for a in areas])
    ang = {a: math.atan2(pos[a][1] - clat, pos[a][0] - clon) for a in areas}
    order = sorted(areas, key=lambda a: ang[a])
    n = len(order)
    best, best_cost = None, None
    for cuts in _combinations(n, k):
        groups, prev = [], 0
        ok = True
        for c in list(cuts) + [n]:
            g = order[prev:c]
            if not g:
                ok = False
                break
            groups.append(g)
            prev = c
        if not ok:
            continue
        cost = _partition_cost(groups, pos, mass)
        if best_cost is None or cost < best_cost:
            best, best_cost = [sorted(g) for g in groups], cost
    return best


def _combinations(n, k):
    from itertools import combinations
    return combinations(range(1, n), k - 1)


def _partition_cost(groups, pos, mass):
    """代价 = 组间质量不均衡 + 组内空间跨度之和（均归一化）。"""
    ms = np.array([sum(mass[a] for a in g) for g in groups])
    imb = (ms.max() - ms.min()) / max(ms.mean(), 1e-9)
    spans = []
    for g in groups:
        xs = [pos[a][0] for a in g]
        ys = [pos[a][1] for a in g]
        spans.append(max(max(xs) - min(xs), max(ys) - min(ys)))
    span = sum(spans) / max(np.mean(spans), 1e-9)
    return 1.0 * imb + 0.35 * span


# ---------------------------------------------------------------------------
# 组内独立资源核算
# ---------------------------------------------------------------------------
def group_sorties(sc, areas, boxes_by_area, box_by_id, deadline_of):
    """对给定任务组独立重跑装箱与合并，得到组内运输架次。"""
    subset = [b for a in areas for b in boxes_by_area.get(a, [])]
    sub_ids = {b["box_id"] for b in subset}
    saved = sc.boxes
    sc.boxes = subset
    try:
        s = Q2.construct(sc, box_by_id, deadline_of)
        s = Q2.merge_pass(sc, s, box_by_id, deadline_of, rounds=2)
        s = Q2.optimize_routes(sc, s, box_by_id)
    finally:
        sc.boxes = saved
    return s


def min_uavs(sc, sorties, box_by_id, deadline_of, type_id, cap=None):
    """该机型下满足全部首批截止时间所需的最少无人机数，以及对应完成时间。"""
    lst = [s for s in sorties if s.type_id == type_id]
    if not lst:
        return 0, 0.0, 0.0
    top = cap if cap is not None else len(lst)
    for K in range(1, top + 1):
        mk, viol = simulate_fleet(sc, lst, box_by_id, deadline_of, K, 10 ** 6)
        if viol <= 1e-6:
            return K, mk, viol
    mk, viol = simulate_fleet(sc, lst, box_by_id, deadline_of, top, 10 ** 6)
    return top, mk, viol


def simulate_fleet(sc, lst, box_by_id, deadline_of, n_uav, n_batt):
    """给定无人机数与电池数，按最早空闲分配并计入充电周转，返回 (完成时间, 首批超时)。"""
    t = sc.types[lst[0].type_id]
    gid = lst[0].type_id
    uav_free = [0.0] * n_uav
    batt_ready = [0.0] * n_batt
    t_full = sc.batteries[gid]["t_full"]
    viol = 0.0
    makespan = 0.0
    order = sorted(lst, key=lambda s: min(
        [deadline_of[b] for ids in s.boxes.values() for b in ids
         if deadline_of[b] is not None] or [10 ** 9]))
    for s in order:
        Q2.evaluate_sortie(sc, s, box_by_id)
        i = int(np.argmin(uav_free))
        j = int(np.argmin(batt_ready))
        start = max(uav_free[i], batt_ready[j])
        dur = Q2.sortie_total_time(sc, s)
        end = start + dur
        uav_free[i] = end
        soc = max(0.0, 1.0 - s.energy / t["battery_energy"])
        batt_ready[j] = end + charge_time(soc, t_full)
        makespan = max(makespan, end)
        times = Q2.delivery_times(sc, s, start)
        for a, tt in times.items():
            for b in s.boxes.get(a, []):
                dl = deadline_of.get(b)
                if dl is not None and tt > dl:
                    viol += tt - dl
    return makespan, viol


def min_batteries(sc, lst, box_by_id, deadline_of, n_uav, target_makespan, top):
    """在给定无人机数下，使完成时间不超过目标的电池组数下界搜索。"""
    for B in range(1, top + 1):
        mk, viol = simulate_fleet(sc, lst, box_by_id, deadline_of, n_uav, B)
        if viol <= 1e-6 and mk <= target_makespan + 1e-6:
            return B
    return top


# ---------------------------------------------------------------------------
def main() -> int:
    sc = build_scenario()
    Q3.init_comm(sc)
    box_by_id = {b["box_id"]: b for b in sc.boxes}
    boxes_by_area = {}
    for b in sc.boxes:
        boxes_by_area.setdefault(b["area_id"], []).append(b)
    deadline_of = {b["box_id"]: (b["first_deadline"] if b["is_first_batch"] else None)
                   for b in sc.boxes}
    expect_of = {b["box_id"]: b["expect_time"] for b in sc.boxes}
    prio_of = {b["box_id"]: b["priority"] for b in sc.boxes}

    q3 = json.load(open(os.path.join(RESULTS_DIR, "q3_results.json"), encoding="utf-8"))
    transport = q3["运输架次"]

    # ---- 1. 同架次约束图 ----
    comps, n_edges = colocation_components(sc, transport)
    print("=== 同架次约束图 ===")
    print(f"  同架次相邻关系 {n_edges} 条，连通分量 {len(comps)} 个")
    for c in comps:
        print(f"    分量：{'、'.join(c)}")
    single = len(comps) == 1
    print(f"  全部服务区是否被连成单一分量：{'是' if single else '否'}")

    inventory = {
        "运输无人机": {g: sum(1 for f in sc.fleet if f["type_id"] == g) for g in sc.types},
        "共享电池": {g: sc.batteries[g]["count"] for g in sc.batteries},
        "中继无人机": len(sc.relay_fleet),
        "中继能源组件": sc.relay_components[sc.relay["type_id"]]["count"],
    }
    print(f"  现有库存：{inventory}")

    # ---- 2. 分区与独立核算 ----
    results = {}
    for k in (2, 3):
        groups = build_partition(sc, boxes_by_area, k)
        print(f"\n=== 划分为 {k} 个任务组 ===")
        for gi, g in enumerate(groups, 1):
            m = sum(b["mass"] for b in boxes_by_area_boxes(g, boxes_by_area))
            nb = sum(len(boxes_by_area[a]) for a in g)
            print(f"  组{gi}：{'、'.join(g)}  货箱 {nb} 箱  质量 {m:.0f} kg")

        detail = []
        for gi, g in enumerate(groups, 1):
            sorties = group_sorties(sc, g, boxes_by_area, box_by_id, deadline_of)
            # 组内同架次约束核对：组内架次只能覆盖本组服务区
            cross = [s.area_order for s in sorties if not set(s.area_order) <= set(g)]
            uavs, batteries, mk, viol = account_group(
                sc, g, sorties, box_by_id, deadline_of, expect_of, prio_of)
            relay = relay_requirement(sc, g, transport, box_by_id, deadline_of,
                                      expect_of, prio_of)
            detail.append({
                "组": gi, "服务区": g,
                "货箱数": sum(len(boxes_by_area[a]) for a in g),
                "需求质量_kg": sum(b["mass"] for b in boxes_by_area_boxes(g, boxes_by_area)),
                "运输架次": len(sorties),
                "运输能耗_kWh": sum(s.energy for s in sorties),
                "运输无人机需求": uavs, "共享电池需求": batteries,
                "组内完成时间_s": mk, "首批超时_s": viol,
                "中继无人机需求": relay["n_relay_uav"],
                "中继能源组件需求": relay["n_relay_comp"],
                "中继能耗_kWh": relay["energy_relay"],
                "通信缺口点": relay["n_gap"],
                "中继悬停位置数": relay.get("n_hover", 0),
                "中继架次数": relay.get("n_missions", 0),
                "中继需求是否触顶": relay.get("capped", False),
                "跨组架次数": len(cross),
            })
            print(f"    组{gi} 运输架次 {len(sorties)}（跨组 {len(cross)}），"
                  f"无人机需求 {uavs}，电池需求 {batteries}，"
                  f"组内完成 {mk:.0f}s，中继需求 {relay['n_relay_uav']} 架 / "
                  f"{relay['n_relay_comp']} 组件（缺口点 {relay['n_gap']}，"
                  f"悬停位置 {relay.get('n_hover', 0)}）")
        results[f"{k}组"] = {"分区": groups, "组明细": detail,
                            "合计": aggregate(detail)}

    # ---- 3. 对比 ----
    print("\n=== 两种分区方式对比 ===")
    header = ("分区  运输无人机 共享电池 中继无人机 中继组件 运输架次 "
              "完成时间s 组间质量不均衡 冗余(机/池/继/件)")
    print(header)
    for key in ("2组", "3组"):
        a = results[key]["合计"]
        print(f"{key:5s} {a['运输无人机']:10d} {a['共享电池']:8d} {a['中继无人机']:10d} "
              f"{a['中继能源组件']:8d} {a['运输架次']:8d} {a['完成时间']:9.1f} "
              f"{a['质量不均衡']:14.3f} "
              f"{a['冗余_运输无人机']}/{a['冗余_共享电池']}/{a['冗余_中继无人机']}/{a['冗余_中继组件']}")
        gap = a["缺口"]
        print(f"      资源缺口：运输无人机 {gap['运输无人机']}，共享电池 {gap['共享电池']}，"
              f"中继无人机 {gap['中继无人机']}，中继能源组件 {gap['中继能源组件']}")

    out = {
        "同架次约束图": {"边数": n_edges, "连通分量": comps, "单一分量": single},
        "现有库存": inventory,
        "分区结果": results,
    }
    write_json(os.path.join(RESULTS_DIR, "q4_results.json"), out)
    write_json(os.path.join(QDIR, "q4_solution.json"), out)
    print("\n已写出 results/q4_results.json 与 Q4/q4_solution.json")
    return 0


def boxes_by_area_boxes(areas, boxes_by_area):
    out = []
    for a in areas:
        out.extend(boxes_by_area.get(a, []))
    return out


def account_group(sc, areas, sorties, box_by_id, deadline_of, expect_of, prio_of):
    """核算单个任务组的运输无人机与共享电池需求。"""
    uav_need, batt_need = {}, {}
    mk_all, viol_all = 0.0, 0.0
    for gid in sc.types:
        lst = [s for s in sorties if s.type_id == gid]
        if not lst:
            uav_need[gid] = 0
            batt_need[gid] = 0
            continue
        # 无人机需求：满足首批截止时间的最少架数
        K = None
        mkK = 0.0
        violK = 0.0
        for k in range(1, len(lst) + 1):
            mk, viol = simulate_fleet(sc, lst, box_by_id, deadline_of, k, 10 ** 6)
            if viol <= 1e-6:
                K, mkK, violK = k, mk, viol
                break
        if K is None:
            K = len(lst)
            mkK, violK = simulate_fleet(sc, lst, box_by_id, deadline_of, K, 10 ** 6)
        uav_need[gid] = K
        # 电池需求：在 K 架无人机下达到同一起飞可行性所需的组数
        B = len(lst)
        for b in range(1, len(lst) + 1):
            mk2, viol2 = simulate_fleet(sc, lst, box_by_id, deadline_of, K, b)
            if viol2 <= 1e-6 and mk2 <= mkK + 1e-6:
                B = b
                break
        batt_need[gid] = B
        mk_all = max(mk_all, mkK)
        viol_all += violK
    return uav_need, batt_need, mk_all, viol_all


def relay_requirement(sc, areas, transport, box_by_id, deadline_of, expect_of, prio_of):
    """核算任务组独立执行所需的中继无人机与能源组件数。

    做法：先由通信剖面求出该组的通信缺口点，用集合覆盖选出悬停位置；
    每个悬停位置对应一个必须提供服务的时段（区间）。中继无人机数等于这些
    服务区间在时间上的最大重叠数（区间图着色数），能源组件数等于计入充电
    周转后的资源占用区间的最大重叠数。该口径不依赖运输时刻的重排，
    可直接给出"独立执行"所需的最小并发资源量。
    """
    r = sc.relay
    comp = sc.relay_components[r["type_id"]]
    sub = [s for s in transport if set(s["route"]) <= set(areas)]
    if not sub:
        return {"n_relay_uav": 0, "n_relay_comp": 0, "energy_relay": 0.0,
                "n_gap": 0, "n_hover": 0, "n_missions": 0, "capped": False}
    profiles = []
    for k, s in enumerate(sorted(sub, key=lambda x: x["start"]), 1):
        t = sc.types[s["type_id"]]
        route = [O01] + s["route"] + [O01]
        nb = {a: len(v) for a, v in s["boxes"].items()}
        pts, _end = Q3.sample_trajectory(sc, t, route, s["start"], nb)
        flags = [Q3.direct_ok(sc, p) for _tt, p in pts]
        profiles.append({"idx": k, "sortie": dict(s), "pts": pts, "flags": flags,
                         "gap": sum(1 for f in flags if not f), "n": len(pts),
                         "dur": s["end"] - s["start"], "start0": s["start"]})
    gaps = []
    for p in profiles:
        for (tt, pt), ok in zip(p["pts"], p["flags"]):
            if not ok:
                gaps.append({"t": tt, "pt": pt, "sortie": p["idx"]})
    if not gaps:
        return {"n_relay_uav": 0, "n_relay_comp": 0, "energy_relay": 0.0,
                "n_gap": 0, "n_hover": 0, "n_missions": 0, "capped": False}
    cands = Q3.hover_candidates(sc)
    options, sample_idx = Q3.build_coverage(sc, gaps, cands)
    chosen, _un = Q3.greedy_cover(options, sample_idx)

    # 每个悬停位置的服务区间与其飞行时间
    intervals = []
    for o in chosen:
        idxs = [gi for gi in range(len(gaps))
                if Q3.relay_ok(sc, gaps[gi]["pt"], (o["lon"], o["lat"], o["alt"]))]
        if not idxs:
            continue
        ts = [gaps[gi]["t"] for gi in idxs]
        fl = o["flight"]
        lead = r["t_prepare"] + fl["t_out"] + r["t_link"]
        svc = max(60.0, max(ts) - min(ts))
        s_max = Q3.max_service_seconds(sc, fl["e_flight"])
        svc_capped = min(svc + 120.0, s_max)
        a = min(ts) - lead
        b = min(ts) + svc_capped
        e = fl["e_flight"] + Q3.relay_service_energy(sc, svc_capped)
        soc = max(0.0, 1.0 - e / r["energy_component"])
        intervals.append({
            "lon": o["lon"], "lat": o["lat"], "hover_h": o["hover_h"],
            "alt": o["alt"], "a": max(a, 0.0), "b": b,
            "busy_a": max(a, 0.0), "busy_b": b + fl["t_back"] + r["t_turnaround"],
            "energy": e, "soc_end": soc, "n_gap": len(idxs),
            "capped": svc + 120.0 > s_max + 1e-9,
            "charge": charge_time(soc, comp["t_full"]),
        })
    if not intervals:
        return {"n_relay_uav": 0, "n_relay_comp": 0, "energy_relay": 0.0,
                "n_gap": len(gaps), "n_hover": len(chosen), "n_missions": 0,
                "capped": False}

    def max_overlap(spans):
        events = []
        for a, b in spans:
            events.append((a, 1))
            events.append((b, -1))
        events.sort(key=lambda x: (x[0], -x[1]))
        cur = peak = 0
        for _t, d in events:
            cur += d
            peak = max(peak, cur)
        return peak

    n_uav = max_overlap([(iv["a"], iv["b"]) for iv in intervals])
    n_comp = max_overlap([(iv["busy_a"], iv["busy_b"] + iv["charge"])
                          for iv in intervals])
    return {
        "n_relay_uav": int(n_uav),
        "n_relay_comp": int(n_comp),
        "energy_relay": float(sum(iv["energy"] for iv in intervals)),
        "n_gap": len(gaps),
        "n_hover": len(chosen),
        "n_missions": len(intervals),
        "capped": any(iv["capped"] for iv in intervals),
        "intervals": intervals,
    }


def aggregate(detail):
    """把各组需求汇总并与库存比较，得到冗余与缺口。"""
    inv_uav = {g: sum(1 for f in sc_fleet_cache["fleet"] if f["type_id"] == g)
               for g in sc_fleet_cache["types"]}
    inv_batt = sc_fleet_cache["batt"]
    need_uav = {g: sum(d["运输无人机需求"][g] for d in detail) for g in inv_uav}
    need_batt = {g: sum(d["共享电池需求"][g] for d in detail) for g in inv_batt}
    need_relay = sum(d["中继无人机需求"] for d in detail)
    need_comp = sum(d["中继能源组件需求"] for d in detail)
    ms = [d["需求质量_kg"] for d in detail]
    imb = (max(ms) - min(ms)) / max(sum(ms) / len(ms), 1e-9)
    return {
        "运输无人机": sum(need_uav.values()),
        "共享电池": sum(need_batt.values()),
        "中继无人机": need_relay,
        "中继能源组件": need_comp,
        "运输架次": sum(d["运输架次"] for d in detail),
        "完成时间": max(d["组内完成时间_s"] for d in detail),
        "质量不均衡": imb,
        "按机型运输无人机需求": need_uav,
        "按机型共享电池需求": need_batt,
        "冗余_运输无人机": sum(inv_uav.values()) - sum(need_uav.values()),
        "冗余_共享电池": sum(inv_batt.values()) - sum(need_batt.values()),
        "冗余_中继无人机": len(sc_fleet_cache["relay_fleet"]) - need_relay,
        "冗余_中继组件": sc_fleet_cache["relay_comp"] - need_comp,
        "缺口": {
            "运输无人机": max(0, sum(need_uav.values()) - sum(inv_uav.values())),
            "共享电池": max(0, sum(need_batt.values()) - sum(inv_batt.values())),
            "中继无人机": max(0, need_relay - len(sc_fleet_cache["relay_fleet"])),
            "中继能源组件": max(0, need_comp - sc_fleet_cache["relay_comp"]),
        },
    }


sc_fleet_cache = {}


if __name__ == "__main__":
    _sc = build_scenario()
    sc_fleet_cache.update({
        "fleet": _sc.fleet, "types": list(_sc.types),
        "batt": {g: _sc.batteries[g]["count"] for g in _sc.batteries},
        "relay_fleet": _sc.relay_fleet,
        "relay_comp": _sc.relay_components[_sc.relay["type_id"]]["count"],
    })
    raise SystemExit(main())