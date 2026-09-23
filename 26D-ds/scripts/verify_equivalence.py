# -*- coding: utf-8 -*-
"""附录代码等价性回归探针。

对每个入附录的模块，用一组规模受控但覆盖核心逻辑的确定性计算生成结构化结果，
供 prepare_appendix_code.py 在「原版」与「净化版」两个隔离副本中分别运行并逐值比对。
探针不修改任何真实业务代码，只调用其公开函数。

用法：python scripts/verify_equivalence.py --module <key> --out <json path>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _jdump(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=_def)


def _def(o):
    import numpy as np
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(str(type(o)))


def probe_common_d():
    """公共数据层：附件读取、航段几何、能耗、链路余量、充电时间。"""
    from common_d import (COMM, build_scenario, charge_time, equivalent_range,
                          gateway_point, link_max_loss, seg_energy, seg_geometry,
                          seg_time)
    sc = build_scenario()
    areas = [a["id"] for a in sc.areas]
    out = {
        "center": sc.center["id"],
        "n_areas": len(areas),
        "types": {g: [sc.types[g]["q_max"], sc.types[g]["vol_max"],
                      sc.types[g]["battery_energy"], sc.types[g]["reserve_ratio"]]
                  for g in sorted(sc.types)},
        "n_boxes": len(sc.boxes),
        "batteries": {g: sc.batteries[g]["count"] for g in sorted(sc.batteries)},
        "relay": [sc.relay["energy_component"], sc.relay["h_hover_max"],
                  sc.relay["reserve_ratio"]],
        "dem_res": [round(float(x), 6) for x in sc.dem.res],
        "dem_shape": list(sc.dem.elev.shape),
        "segments": [],
        "ranges": {},
        "link_max": {k: round(link_max_loss(*k.split("|")), 6)
                     for k in ("uav|gateway", "uav|relay_acc", "relay_back|gateway")},
        "gateway": [round(float(x), 6) for x in gateway_point(sc)],
        "charge": [round(charge_time(s, 1800.0), 6) for s in (0.0, 0.25, 0.5, 0.89, 0.95, 1.0)],
    }
    for a in areas[:4]:
        g = seg_geometry(sc, "O01", a)
        out["segments"].append([a, round(g["d"], 6), round(g["cruise_alt"], 6),
                                round(g["climb"], 6), round(g["descend"], 6)])
    for gid in sorted(sc.types):
        t = sc.types[gid]
        out["ranges"][gid] = [round(equivalent_range(t, q), 6)
                              for q in (0.0, t["q_max"] * 0.5, t["q_max"])]
    t = sc.types["C"]
    out["energy_S003"] = [round(seg_energy(sc, t, "O01", "S003", q), 9)
                          for q in (0.0, 40.0, 80.0)]
    out["time_S003"] = [round(seg_time(sc, t, "O01", "S003"), 6),
                        round(seg_time(sc, t, "S003", "O01"), 6)]
    return out


def probe_eda():
    """数据预处理：节点高程核对、需求汇总、航段几何与 DEM 统计。"""
    import pandas as pd
    from common_d import DERIVED_DIR, PROJECT, build_scenario, haversine
    sc = build_scenario()
    c = sc.center
    nodes = []
    for a in sc.areas:
        nodes.append([a["id"], round(a["alt"], 3),
                      round(sc.dem.sample(a["lon"], a["lat"]), 3),
                      round(haversine(c["lon"], c["lat"], a["lon"], a["lat"]), 3),
                      a["pop"]])
    boxes = sorted(sc.boxes, key=lambda b: b["box_id"])
    import numpy as np
    valid = sc.dem.elev[~np.isnan(sc.dem.elev)]
    return {
        "nodes": nodes,
        "n_boxes": len(boxes),
        "mass_sum": round(sum(b["mass"] for b in boxes), 6),
        "vol_sum": round(sum(b["volume"] for b in boxes), 6),
        "n_first": int(sum(1 for b in boxes if b["is_first_batch"])),
        "box_head": [[b["box_id"], b["area_id"], b["cargo"], b["mass"], b["volume"]]
                     for b in boxes[:6]],
        "dem": [round(float(valid.min()), 4), round(float(valid.max()), 4),
                round(float(valid.mean()), 4)],
        "n_valid": int(len(valid)),
    }


def probe_q1():
    """问题一：最大安全载荷二分与组批精确动态规划。"""
    from common_d import build_scenario
    sys.path.insert(0, os.path.join(ROOT, "Q1"))
    import solve_q1 as Q1
    sc = build_scenario()
    areas = [a["id"] for a in sc.areas]
    by_area = {}
    for b in sc.boxes:
        by_area.setdefault(b["area_id"], []).append(b)
    payload = {a: {g: round(Q1.max_safe_payload(sc, t, a), 6)
                   for g, t in sorted(sc.types.items())} for a in areas}
    detail = []
    for a in ("S001", "S003", "S011"):
        cats, counts = Q1.classify(by_area[a])
        caps = Q1.build_caps(sc, a, payload[a])
        r = Q1.solve_area(cats, counts, caps, ("N", "E", "T"))
        detail.append([a, r["N"], round(r["E"], 9), round(r["T"], 6),
                       sorted(s["type_id"] for s in r["plan"])])
    tot_n = sum(Q1.solve_area(Q1.classify(by_area[a])[0], Q1.classify(by_area[a])[1],
                              Q1.build_caps(sc, a, payload[a]), ("N", "E", "T"))["N"]
                for a in areas)
    return {"payload": payload, "detail": detail, "total_sorties": tot_n,
            "rho_crit_probe": round(Q1.max_safe_payload(sc, sc.types["C"], "S008",
                                                       rho=0.35), 6)}


def probe_q2():
    """问题二：分层构造、同型合并与一次排程的四项指标。"""
    from common_d import build_scenario
    sys.path.insert(0, os.path.join(ROOT, "Q2"))
    import solve_q2 as Q2
    sc = build_scenario()
    box_by_id = {b["box_id"]: b for b in sc.boxes}
    deadline = {b["box_id"]: (b["first_deadline"] if b["is_first_batch"] else None)
                for b in sc.boxes}
    expect = {b["box_id"]: b["expect_time"] for b in sc.boxes}
    prio = {b["box_id"]: b["priority"] for b in sc.boxes}
    sorties = Q2.construct(sc, box_by_id, deadline)
    n0 = len(sorties)
    sorties = Q2.merge_pass(sc, sorties, box_by_id, deadline, rounds=1)
    n1 = len(sorties)
    sorties = Q2.optimize_routes(sc, sorties, box_by_id)
    m = Q2.evaluate_solution(sc, sorties, box_by_id, deadline, expect, prio)
    routes = sorted("→".join(s.area_order) for s in sorties)
    return {"n_construct": n0, "n_merged": n1,
            "tardy": round(m["tardy"], 6), "makespan": round(m["makespan"], 6),
            "energy": round(m["energy"], 9), "n_sorties": m["n_sorties"],
            "first_violation": round(m["first_violation"], 6),
            "routes": routes}


def probe_q3():
    """问题三：轨迹采样、直连判定、中继判定与集合覆盖。"""
    from common_d import build_scenario
    sys.path.insert(0, os.path.join(ROOT, "Q3"))
    import solve_q3 as Q3
    sc = build_scenario()
    Q3.init_comm(sc)
    out = {"limits": {k: round(v, 6) for k, v in Q3.LMAX.items()},
           "direct": {}, "relay_flight": {}, "cover": {}}
    for a in ("S001", "S003", "S008"):
        area = next(x for x in sc.areas if x["id"] == a)
        pt = (area["lon"], area["lat"], area["alt"] + 30.0)
        out["direct"][a] = bool(Q3.direct_ok(sc, pt))
    rp = None
    for cand in Q3.hover_candidates(sc)[:6]:
        g0 = sc.dem.sample(cand["lon"], cand["lat"])
        rp = (cand["lon"], cand["lat"], g0 + 300.0)
        fl = Q3.relay_flight(sc, rp)
        out["relay_flight"][f"{cand['lon']:.5f},{cand['lat']:.5f}"] = [
            round(fl["t_flight"], 6), round(fl["e_flight"], 9),
            round(Q3.max_service_seconds(sc, fl["e_flight"]), 6)]
    area = next(x for x in sc.areas if x["id"] == "S003")
    t = sc.types["C"]
    pts, end = Q3.sample_trajectory(sc, t, ["O01", "S003", "O01"], 0.0, {"S003": 6})
    flags = [Q3.direct_ok(sc, p) for _tt, p in pts]
    out["traj"] = [len(pts), round(end, 6), int(sum(1 for f in flags if not f))]
    return out


def probe_q4():
    """问题四：同架次关系图、分区构造与组内独立资源核算。"""
    from common_d import RESULTS_DIR, build_scenario
    sys.path.insert(0, os.path.join(ROOT, "Q4"))
    import solve_q4 as Q4
    sc = build_scenario()
    q3 = json.load(open(os.path.join(RESULTS_DIR, "q3_results.json"), encoding="utf-8"))
    comps, edges = Q4.colocation_components(sc, q3["运输架次"])
    boxes_by_area = {}
    for b in sc.boxes:
        boxes_by_area.setdefault(b["area_id"], []).append(b)
    parts = {k: Q4.build_partition(sc, boxes_by_area, k) for k in (2, 3)}
    box_by_id = {b["box_id"]: b for b in sc.boxes}
    deadline = {b["box_id"]: (b["first_deadline"] if b["is_first_batch"] else None)
                for b in sc.boxes}
    g = parts[2][0]
    sorties = Q4.group_sorties(sc, g, boxes_by_area, box_by_id, deadline)
    lst = [s for s in sorties if s.type_id == "C"]
    mk, viol = Q4.simulate_fleet(sc, lst, box_by_id, deadline, 1, 4) if lst else (0.0, 0.0)
    return {"n_edges": edges, "n_components": len(comps),
            "components": sorted(sorted(c) for c in comps),
            "partition_2": [sorted(x) for x in parts[2]],
            "partition_3": [sorted(x) for x in parts[3]],
            "group1_sorties": len(sorties),
            "group1_C_makespan": round(mk, 6), "group1_C_viol": round(viol, 6)}


def probe_sensitivity():
    """灵敏度分析：小网格响应面与临界可行性。"""
    from common_d import build_scenario
    sys.path.insert(0, os.path.join(ROOT, "灵敏度分析"))
    import sensitivity as S
    sc = build_scenario()
    areas = [a["id"] for a in sc.areas]
    by_area = {}
    for b in sc.boxes:
        by_area.setdefault(b["area_id"], []).append(b)
    cats, counts = {}, {}
    for a in areas:
        cats[a], counts[a] = S.classify(by_area[a])
    grid = S.evaluate_grid(sc, areas, by_area, cats, counts,
                           [0.15, 0.25, 0.35], [0.8, 1.0, 1.2])
    return {"rho": grid["rho"], "scale": grid["scale"],
            "N": [None if x != x else float(x) for x in grid["N"]],
            "E": [None if x != x else round(float(x), 9) for x in grid["E"]],
            "feasible": grid["feasible"]}


PROBES = {
    "common_d": probe_common_d,
    "eda": probe_eda,
    "solve_q1": probe_q1,
    "solve_q2": probe_q2,
    "solve_q3": probe_q3,
    "solve_q4": probe_q4,
    "sensitivity": probe_sensitivity,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True, choices=sorted(PROBES))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = PROBES[args.module]()
    _jdump(args.out, result)
    print(f"equivalence probe {args.module} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())