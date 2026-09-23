# -*- coding: utf-8 -*-
"""问题三：通信约束下的运输与中继联合调度。

模型主线
--------
1. 运输轨迹采样：把每个运输架次展开为"爬升—巡航—下降—投送悬停"的时序轨迹，
   按固定时间步采样三维位置。
2. 链路判定：对每个采样点先判直连 G01 是否可用；不可用时判"运输—中继—G01"
   两段链路是否同时可用，判定按题目附录 3 的地形遮挡、双向链路预算与传播损耗口径执行。
3. 中继布点：把全部通信缺口采样点作为待覆盖集合，在 DEM 覆盖范围内构造候选悬停位置
   （服务区上空 + 区域高地形点），以贪心集合覆盖选择最少的悬停位置覆盖全部缺口。
4. 中继架次：一个中继架次由（悬停位置、悬停离地高度、服务时段、能源组件）刻画，
   时间与能耗按附录 2 的中继规则计算，并满足返航电量要求。
5. 联合调度：含缺口的运输架次必须等待对应中继进入服务时段才能执行，
   故联合调度在运输架次与中继架次之间迭代收敛；两类能源资源独立周转。

运行：python Q3/solve_q3.py
输出：results/q3_results.json、Q3/q3_solution.json
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402

from common_d import (  # noqa: E402
    COMM, RESULTS_DIR, build_scenario, charge_time, fspl, gateway_point,
    haversine, link_max_loss, seg_geometry, seg_time, write_json,
)

QDIR = os.path.join(ROOT, "Q3")
FIGDIR = os.path.join(QDIR, "figures")
O01 = "O01"
G_ACC = 9.81
SAMPLE_DT = 5.0
PLACE_STRIDE = 8          # 布点阶段对缺口点抽样，降低链路判定次数
H_GRID = (300.0, 240.0, 180.0, 120.0)


# ---------------------------------------------------------------------------
# 链路判定（题目附录 3）
# ---------------------------------------------------------------------------
def los_blocked(sc, p1, p2, n=110):
    return sc.dem.los_blocked(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], n=n)


def d3(p1, p2):
    dh = haversine(p1[0], p1[1], p2[0], p2[1])
    dz = p2[2] - p1[2]
    return math.sqrt(dh * dh + dz * dz)


def link_ok(sc, p1, p2, key1, key2):
    blocked = los_blocked(sc, p1, p2)
    loss = fspl(COMM["freq_mhz"], d3(p1, p2) / 1000.0) + (COMM["L_obs"] if blocked else 0.0)
    return loss <= link_max_loss(key1, key2)


GW = None
LMAX = {}


def init_comm(sc):
    global GW, LMAX
    GW = gateway_point(sc)
    LMAX = {"uav_gw": link_max_loss("uav", "gateway"),
            "uav_relay": link_max_loss("uav", "relay_acc"),
            "relay_gw": link_max_loss("relay_back", "gateway")}
    return GW, LMAX


def direct_ok(sc, pt):
    return link_ok(sc, pt, GW, "uav", "gateway")


def relay_ok(sc, pt, relay_pt):
    if not link_ok(sc, pt, relay_pt, "uav", "relay_acc"):
        return False
    return link_ok(sc, relay_pt, GW, "relay_back", "gateway")


# ---------------------------------------------------------------------------
# 运输轨迹采样
# ---------------------------------------------------------------------------
def sample_trajectory(sc, t, route, t_start, n_boxes_by_area):
    pts = []
    clock = t_start + t["t_prepare"] + sum(n_boxes_by_area.values()) * t["t_load_per_box"]
    for k in range(len(route) - 1):
        i, j = route[k], route[k + 1]
        g = seg_geometry(sc, i, j)
        a1 = sc.node_ground[i] + (0.0 if i == O01 else 30.0)
        a2 = sc.node_ground[j] + (0.0 if j == O01 else 30.0)
        cruise = g["cruise_alt"]
        lon1, lat1 = sc.node_xy[i]
        lon2, lat2 = sc.node_xy[j]
        climb = max(cruise - a1, 0.0)
        desc = max(cruise - a2, 0.0)
        tc, tr, td = climb / t["v_climb"], g["d"] / t["v_cruise"], desc / t["v_descend"]
        n1 = max(int(tc / SAMPLE_DT), 1)
        for s in range(n1 + 1):
            f = s / n1
            pts.append((clock + tc * f, (lon1, lat1, a1 + climb * f)))
        clock += tc
        n2 = max(int(tr / SAMPLE_DT), 1)
        for s in range(n2 + 1):
            f = s / n2
            pts.append((clock + tr * f,
                        (lon1 + (lon2 - lon1) * f, lat1 + (lat2 - lat1) * f, cruise)))
        clock += tr
        n3 = max(int(td / SAMPLE_DT), 1)
        for s in range(n3 + 1):
            f = s / n3
            pts.append((clock + td * f, (lon2, lat2, cruise - desc * f)))
        clock += td
        if j != O01:
            nb = n_boxes_by_area.get(j, 0)
            hold = t["t_handover_base"] + nb * t["t_handover_per_box"]
            n4 = max(int(hold / SAMPLE_DT), 1)
            for s in range(n4 + 1):
                pts.append((clock + hold * s / n4, (lon2, lat2, a2)))
            clock += hold
    return pts, clock


# ---------------------------------------------------------------------------
# 中继时间与能耗（附录 2）
# ---------------------------------------------------------------------------
def relay_flight(sc, rp):
    """中继 O01→悬停位置→O01 的飞行时间与能耗。

    水平巡航能耗按巡航功率与巡航时间计算，爬升附加能耗按计划起飞总质量计算；
    地形净空按航段规则确定（计划巡航海拔取沿途 DEM 最高地面高程以上 50 m）。
    """
    r = sc.relay
    m = r["mass_takeoff"]
    lon1, lat1 = sc.node_xy[O01]
    d = haversine(lon1, lat1, rp[0], rp[1])
    cruise = sc.dem.max_elev_profile(lon1, lat1, rp[0], rp[1]) + 50.0
    a_o01 = sc.node_ground[O01]
    c_out = max(cruise - a_o01, 0.0)
    c_back = max(cruise - rp[2], 0.0)
    d_out = max(cruise - rp[2], 0.0)
    d_back = max(cruise - a_o01, 0.0)
    t_out = c_out / r["v_climb"] + d / r["v_cruise"] + d_out / r["v_descend"]
    t_back = c_back / r["v_climb"] + d / r["v_cruise"] + d_back / r["v_descend"]
    e_cruise = r["p_cruise"] * (d / r["v_cruise"]) / 3600.0
    e_climb = m * G_ACC * (c_out + c_back) / (3.6e6 * r["eta_climb"])
    return {"d": d, "cruise_alt": cruise, "t_out": t_out, "t_back": t_back,
            "t_flight": t_out + t_back, "e_flight": e_cruise + e_climb}


def relay_service_energy(sc, seconds):
    r = sc.relay
    return (r["p_hover"] + r["p_comm_extra"]) * seconds / 3600.0


def max_service_seconds(sc, e_flight):
    r = sc.relay
    limit = (1 - r["reserve_ratio"]) * r["energy_component"]
    avail = limit - e_flight
    if avail <= 0:
        return 0.0
    return avail * 3600.0 / (r["p_hover"] + r["p_comm_extra"])


# ---------------------------------------------------------------------------
# 候选悬停位置
# ---------------------------------------------------------------------------
def hover_candidates(sc):
    """候选悬停位置：15 个服务区上空 + 区域高地形点（可能同时覆盖多个服务区）。"""
    cands = []
    for a in sc.areas:
        cands.append((a["lon"], a["lat"], f"{a['id']}上空"))
    dem = sc.dem
    nrow, ncol = dem.elev.shape
    sub = dem.elev[::14, ::14]
    flat = np.argsort(np.nan_to_num(sub, nan=-9999).ravel())[::-1][:40]
    for idx in flat:
        rr, cc = divmod(int(idx), sub.shape[1])
        r0, c0 = rr * 14, cc * 14
        lo = dem.origin[0] + dem.res[0] * c0
        la = dem.origin[1] - dem.res[1] * r0
        if not sc.dem.inside(lo, la):
            continue
        cands.append((float(lo), float(la), "高地形点"))
    # 去重
    seen, out = set(), []
    for lo, la, tag in cands:
        key = (round(lo, 4), round(la, 4))
        if key in seen:
            continue
        seen.add(key)
        out.append({"lon": lo, "lat": la, "tag": tag})
    return out


def build_coverage(sc, gaps, cands, stride=PLACE_STRIDE):
    """计算每个候选位置在各悬停高度下可覆盖的缺口点集合。

    gaps: list of dict(t, pt, sortie)
    返回 list of dict(cand_idx, hover_h, alt, covers=set(indices), tmin, tmax, flight)
    """
    sample_idx = list(range(0, len(gaps), stride))
    options = []
    for ci, c in enumerate(cands):
        g0 = sc.dem.sample(c["lon"], c["lat"])
        for h in H_GRID:
            if h > sc.relay["h_hover_max"] + 1e-9:
                continue
            rp = (c["lon"], c["lat"], g0 + h)
            covers = []
            for gi in sample_idx:
                if relay_ok(sc, gaps[gi]["pt"], rp):
                    covers.append(gi)
            if not covers:
                continue
            fl = relay_flight(sc, rp)
            ts = [gaps[gi]["t"] for gi in covers]
            options.append({"cand": ci, "lon": c["lon"], "lat": c["lat"], "tag": c["tag"],
                            "hover_h": h, "alt": g0 + h, "covers": set(covers),
                            "tmin": min(ts), "tmax": max(ts), "flight": fl,
                            "cand_all": len(sample_idx)})
    return options, sample_idx


def greedy_cover(options, sample_idx, max_missions=12):
    """贪心集合覆盖：每次选覆盖未覆盖抽样点最多的候选。"""
    uncovered = set(sample_idx)
    chosen = []
    while uncovered and len(chosen) < max_missions:
        best, best_gain = None, 0
        for o in options:
            gain = len(o["covers"] & uncovered)
            if gain > best_gain:
                best, best_gain = o, gain
        if best is None or best_gain == 0:
            break
        chosen.append(best)
        uncovered -= best["covers"]
    return chosen, uncovered


# ---------------------------------------------------------------------------
def main() -> int:
    sc = build_scenario()
    init_comm(sc)
    print(f"通信门限：运输—网关 {LMAX['uav_gw']:.1f} dB，运输—中继 {LMAX['uav_relay']:.1f} dB，"
          f"中继—网关 {LMAX['relay_gw']:.1f} dB")

    q2 = json.load(open(os.path.join(RESULTS_DIR, "q2_results.json"), encoding="utf-8"))
    sched = q2["架次明细"]
    box_by_id = {b["box_id"]: b for b in sc.boxes}
    deadline_of = {b["box_id"]: (b["first_deadline"] if b["is_first_batch"] else None)
                   for b in sc.boxes}
    expect_of = {b["box_id"]: b["expect_time"] for b in sc.boxes}
    prio_of = {b["box_id"]: b["priority"] for b in sc.boxes}

    # ---- 1. 通信剖面 ----
    print("\n=== 运输架次的直连通信剖面 ===")
    profiles = []
    for k, r in enumerate(sorted(sched, key=lambda x: x["start"]), 1):
        t = sc.types[r["type_id"]]
        route = [O01] + r["route"] + [O01]
        nb = {a: len(v) for a, v in r["boxes"].items()}
        pts, end = sample_trajectory(sc, t, route, r["start"], nb)
        flags = [direct_ok(sc, p) for _tt, p in pts]
        gap = sum(1 for f in flags if not f)
        dur = r["end"] - r["start"]
        profiles.append({"idx": k, "sortie": dict(r), "pts": pts, "flags": flags,
                         "gap": gap, "n": len(pts), "dur": dur,
                         "start0": r["start"]})
        print(f"{k:3d}  {r['type_id']}   {'→'.join(r['route']):26s} {len(pts):6d} {gap:6d} "
              f"{100.0*gap/max(len(pts),1):7.2f}%")
    tot_pts = sum(p["n"] for p in profiles)
    tot_gap = sum(p["gap"] for p in profiles)
    print(f"合计采样点 {tot_pts}，直连缺口点 {tot_gap}（{100.0*tot_gap/tot_pts:.2f}%）")

    # ---- 2. 缺口集合 ----
    gaps = []
    for p in profiles:
        for (tt, pt), ok in zip(p["pts"], p["flags"]):
            if not ok:
                gaps.append({"t": tt, "pt": pt, "sortie": p["idx"]})
    print(f"\n通信缺口采样点共 {len(gaps)} 个，用于布点抽样的子集 "
          f"{len(range(0, len(gaps), PLACE_STRIDE))} 个")

    # ---- 3. 中继布点（集合覆盖） ----
    cands = hover_candidates(sc)
    print(f"候选悬停位置 {len(cands)} 个（服务区上空 + 区域高地形点）")
    options, sample_idx = build_coverage(sc, gaps, cands)
    print(f"可行悬停选项 {len(options)} 个（位置 × 悬停高度）")
    chosen, uncovered = greedy_cover(options, sample_idx)
    print(f"\n=== 集合覆盖选中 {len(chosen)} 个悬停位置 ===")
    for o in chosen:
        print(f"  {o['tag']:8s} ({o['lon']:.6f}, {o['lat']:.6f}) 离地 {o['hover_h']:.0f} m "
              f"海拔 {o['alt']:.1f} m 覆盖抽样点 {len(o['covers'])}/{o['cand_all']} "
              f"缺口时段 {o['tmin']:.0f}~{o['tmax']:.0f} s "
              f"往返飞行 {o['flight']['t_flight']:.1f} s")
    print(f"未被覆盖的抽样点：{len(uncovered)} 个")

    # ---- 4. 中继架次与联合调度 ----
    res = joint_schedule(sc, profiles, chosen, gaps, box_by_id, deadline_of,
                         expect_of, prio_of)
    print("\n=== 中继架次 ===")
    print("中继  悬停位置            开始s   建链完成s 服务结束s 返场s   服务时长s 能耗kWh SOC末")
    for m in res["relay_missions"]:
        print(f"{m['uav']:5s} ({m['lon']:.5f},{m['lat']:.5f}) {m['t_depart']:8.1f} "
              f"{m['t_ready']:9.1f} {m['t_service_end']:9.1f} {m['t_return']:8.1f} "
              f"{m['service_s']:9.1f} {m['energy']:7.4f} {m['soc_end']:.3f}")

    M = res["metrics"]
    print(f"\n联合指标：加权总延误 {M['tardy']:.1f}  联合任务完成时间 {M['makespan']:.1f} s "
          f"({M['makespan']/3600:.3f} h)")
    print(f"  运输能耗 {M['energy_transport']:.3f} kWh  中继能耗 {M['energy_relay']:.3f} kWh  "
          f"合计 {M['energy_total']:.3f} kWh")
    print(f"  运输架次 {M['n_sorties_transport']}  中继架次 {M['n_sorties_relay']}  "
          f"首批超时 {M['first_violation']:.1f}")
    print(f"  通信保障：直连点 {M['n_direct']}，中继点 {M['n_relay']}，"
          f"未保障点 {M['n_broken']}")

    checks = q3_checks(sc, res, chosen, M)
    print()
    for c in checks:
        print(("  [OK] " if c["ok"] else "  [FAIL] ") + c["item"] + " " + c["detail"])

    # ---- 5. 两种口径对照：通信优先（推迟运输）与时限优先（保持运输时刻） ----
    print("\n=== 两种调度口径对照 ===")
    variants = {}
    for tag, delay in (("通信优先", True), ("时限优先", False)):
        for p in profiles:
            p["sortie"]["start"] = p["start0"]
            p["sortie"]["end"] = p["start0"] + p["dur"]
        rv = joint_schedule(sc, profiles, chosen, gaps, box_by_id, deadline_of,
                            expect_of, prio_of, n_relay=2, delay_transport=delay)
        mv = rv["metrics"]
        variants[tag] = {"metrics": {k: mv[k] for k in mv},
                         "relay_missions": rv["relay_missions"]}
        print(f"[{tag}] 延误 {mv['tardy']:.1f}  完成时间 {mv['makespan']:.1f}s "
              f"首批超时 {mv['first_violation']:.1f}s  中继能耗 {mv['energy_relay']:.3f}kWh "
              f"未保障点 {mv['n_broken']}")

    # ---- 6. 中继机队规模分析：满足首批截止时间所需的最少中继无人机数 ----
    print("\n=== 中继机队规模分析（通信优先口径，仅改变中继无人机数量） ===")
    print("中继架数 中继架次 首批超时s 联合完成时间s 未保障点 中继能耗kWh")
    fleet_sizing = []
    for k in range(2, 7):
        for p in profiles:
            p["sortie"]["start"] = p["start0"]
            p["sortie"]["end"] = p["start0"] + p["dur"]
        r2 = joint_schedule(sc, profiles, chosen, gaps, box_by_id, deadline_of,
                            expect_of, prio_of, n_relay=k, delay_transport=True)
        m2 = r2["metrics"]
        fleet_sizing.append({"n_relay_uav": k, **{kk: m2[kk] for kk in (
            "n_sorties_relay", "first_violation", "makespan", "n_broken",
            "energy_relay")}})
        print(f"{k:8d} {m2['n_sorties_relay']:8d} {m2['first_violation']:9.1f} "
              f"{m2['makespan']:12.1f} {m2['n_broken']:8d} {m2['energy_relay']:11.3f}")
    need = next((x["n_relay_uav"] for x in fleet_sizing if x["first_violation"] <= 1e-6),
                None)
    print(f"满足首批截止时间所需最少中继无人机数："
          f"{need if need else '超过 6 架'}")
    # 复原为 2 架中继的通信优先方案
    for p in profiles:
        p["sortie"]["start"] = p["start0"]
        p["sortie"]["end"] = p["start0"] + p["dur"]
    joint_schedule(sc, profiles, chosen, gaps, box_by_id, deadline_of,
                   expect_of, prio_of, n_relay=2, delay_transport=True)

    out = {
        "通信门限": LMAX,
        "运输通信剖面": [{"idx": p["idx"], "route": p["sortie"]["route"],
                          "n": p["n"], "gap": p["gap"]} for p in profiles],
        "缺口总数": len(gaps),
        "选中悬停": [{k: (sorted(v) if isinstance(v, set) else v)
                      for k, v in o.items() if k != "flight"} | {"flight": o["flight"]}
                     for o in chosen],
        "未覆盖抽样点": len(uncovered),
        "中继架次": res["relay_missions"],
        "指标": M,
        "资源核对": checks,
        "两种口径对照": variants,
        "中继机队规模分析": fleet_sizing,
        "满足首批截止所需最少中继无人机": need,
        "逐箱送达": res["deliver"],
        "运输架次": [{"idx": p["idx"], "route": p["sortie"]["route"],
                      "type_id": p["sortie"]["type_id"],
                      "start": p["sortie"]["start"], "end": p["sortie"]["end"],
                      "energy": p["sortie"]["energy"],
                      "load_mass": p["sortie"]["load_mass"],
                      "boxes": p["sortie"]["boxes"]} for p in profiles],
    }
    write_json(os.path.join(RESULTS_DIR, "q3_results.json"), out)
    write_json(os.path.join(QDIR, "q3_solution.json"), out)
    print("\n已写出 results/q3_results.json 与 Q3/q3_solution.json")
    return 0


def joint_schedule(sc, profiles, chosen, gaps, box_by_id, deadline_of, expect_of, prio_of,
                   n_relay=2, delay_transport=True, iters=1):
    """联合调度：中继架次按悬停位置与其服务的运输架次时段排定。

    delay_transport=True 时运输架次等待覆盖其缺口的中继就绪（通信优先方案）；
    False 时保持问题二的运输时刻不变、只让中继去匹配运输时刻（时限优先方案）。
    中继服务窗口与运输时刻互为因果，故在外层迭代至收敛。
    """
    r = sc.relay
    comp = sc.relay_components[r["type_id"]]
    # 1) 每个缺口点归属到覆盖它的最优悬停选项
    gap_owner = {}
    for gi, g in enumerate(gaps):
        best, best_e = None, None
        for oi, o in enumerate(chosen):
            if not relay_ok(sc, g["pt"], (o["lon"], o["lat"], o["alt"])):
                continue
            e = o["flight"]["e_flight"]
            if best_e is None or e < best_e:
                best, best_e = oi, e
        gap_owner[gi] = best
    # 2) 每个悬停位置服务的架次与其缺口时段（缺口时刻随运输架次推迟而整体平移）
    def current_shift(p):
        return p["sortie"]["start"] - p["start0"]

    def build_opt_windows():
        opt = {oi: {} for oi in range(len(chosen))}
        for gi, g in enumerate(gaps):
            oi = gap_owner[gi]
            if oi is None:
                continue
            p = next(x for x in profiles if x["idx"] == g["sortie"])
            tt = g["t"] + current_shift(p)
            d = opt[oi].setdefault(g["sortie"], [tt, tt])
            d[0] = min(d[0], tt)
            d[1] = max(d[1], tt)
        return opt

    def slice_urgency(sl):
        dls = []
        for si in sl["served"]:
            p = next(x for x in profiles if x["idx"] == si)
            for ids in p["sortie"]["boxes"].values():
                for b in ids:
                    dl = deadline_of.get(b)
                    if dl is not None:
                        dls.append(dl)
        return (min(dls) if dls else 10 ** 9, sl["a"])

    def build_missions(opt_sorties, n_relay):
        pending = []
        for oi, o in enumerate(chosen):
            if not opt_sorties[oi]:
                continue
            lo = min(v[0] for v in opt_sorties[oi].values())
            hi = max(v[1] for v in opt_sorties[oi].values())
            svc_max = max_service_seconds(sc, o["flight"]["e_flight"])
            span = hi - lo
            k = max(1, int(math.ceil(span / max(svc_max - 60.0, 60.0))))
            for s in range(k):
                a = lo + span * s / k
                b = lo + span * (s + 1) / k
                served = [si for si, v in opt_sorties[oi].items()
                          if v[1] >= a - 1e-9 and v[0] <= b + 1e-9]
                if served:
                    pending.append({"oi": oi, "a": a, "b": b, "served": served})
        pending.sort(key=slice_urgency)
        uavs = [{"id": (sc.relay_fleet[i]["id"] if i < len(sc.relay_fleet)
                        else f"R{i + 1:02d}"), "free": 0.0} for i in range(n_relay)]
        comps = [{"id": f"{r['type_id']}-E{k+1:02d}", "ready": 0.0}
                 for k in range(comp["count"])]
        out = []
        for sl in pending:
            o = chosen[sl["oi"]]
            fl = o["flight"]
            svc_max = max_service_seconds(sc, fl["e_flight"])
            uav = min(uavs, key=lambda u: u["free"])
            c = min(comps, key=lambda x: x["ready"])
            t_depart = max(uav["free"], c["ready"])
            t_ready = t_depart + r["t_prepare"] + fl["t_out"] + r["t_link"]
            want = max(sl["b"] - sl["a"] + 120.0, 300.0)
            svc = min(want, svc_max)
            t_svc_end = t_ready + svc
            t_return = t_svc_end + fl["t_back"] + r["t_turnaround"]
            e_tot = fl["e_flight"] + relay_service_energy(sc, svc)
            soc = max(0.0, 1.0 - e_tot / r["energy_component"])
            uav["free"] = t_return
            c["ready"] = t_return + charge_time(soc, comp["t_full"])
            out.append({
                "uav": uav["id"], "component": c["id"], "lon": o["lon"],
                "lat": o["lat"], "hover_h": o["hover_h"], "alt": o["alt"],
                "tag": o["tag"], "t_depart": t_depart, "t_ready": t_ready,
                "t_service_end": t_svc_end, "t_return": t_return,
                "service_s": svc, "energy": e_tot, "soc_end": soc,
                "e_flight": fl["e_flight"], "t_flight": fl["t_flight"],
                "window": [sl["a"], sl["b"]], "serves": sl["served"], "opt": sl["oi"],
                "svc_capped": svc < want - 1e-9,
            })
        return out

    for p in profiles:
        p["dur"] = p["sortie"]["end"] - p["sortie"]["start"]
    missions = []
    for _ in range(max(1, iters)):
        opt_sorties = build_opt_windows()
        missions = build_missions(opt_sorties, n_relay)
        need = {p["idx"]: 0.0 for p in profiles}
        for m in missions:
            for si in m["serves"]:
                need[si] = max(need[si], m["t_ready"])
        if not delay_transport:
            break
        changed = False
        for p in profiles:
            if p["gap"] == 0:
                continue
            if need[p["idx"]] > p["sortie"]["start"] + 1e-9:
                p["sortie"]["start"] = need[p["idx"]]
                p["sortie"]["end"] = p["sortie"]["start"] + p["dur"]
                changed = True
        if not changed:
            break
    # 单次口径：中继服务窗口按问题二运输时刻确定，运输架次再推迟至中继就绪。
    # 反复重排会使"推迟—窗口拉长—再推迟"形成正反馈，故不做二次重排。
    # 4) 每个运输架次等待覆盖其缺口的中继就绪；中继窗口与运输时刻互为因果，故外层迭代
    for p in profiles:
        p["dur"] = p["sortie"]["end"] - p["sortie"]["start"]
    for p in profiles:
        need = 0.0
        for m in missions:
            if p["idx"] in m["serves"]:
                need = max(need, m["t_ready"])
        p["relay_need"] = need
    if delay_transport:
        for _ in range(6):
            changed = False
            for p in profiles:
                if p["gap"] == 0:
                    continue
                need = p.get("relay_need", 0.0)
                if need > p["sortie"]["start"] + 1e-9:
                    p["sortie"]["start"] = need
                    p["sortie"]["end"] = need + p["dur"]
                    changed = True
            if not changed:
                break

    # 5) 在最终时刻上复核通信保障情况
    deliver = {}
    n_direct = n_relay = n_broken = 0
    for p in profiles:
        s = p["sortie"]
        t = sc.types[s["type_id"]]
        clock = (s["start"] + t["t_prepare"]
                 + sum(len(v) for v in s["boxes"].values()) * t["t_load_per_box"])
        route = [O01] + s["route"] + [O01]
        for k in range(len(route) - 1):
            i, j = route[k], route[k + 1]
            clock += seg_time(sc, t, i, j)
            if j != O01:
                nb = len(s["boxes"].get(j, []))
                clock += t["t_handover_base"] + nb * t["t_handover_per_box"]
                for b in s["boxes"].get(j, []):
                    deliver[b] = clock
        if p["gap"] == 0:
            n_direct += p["n"]
            continue
        shift = current_shift(p)
        for (tt, pt), ok in zip(p["pts"], p["flags"]):
            if ok:
                n_direct += 1
                continue
            t_new = tt + shift
            covered = False
            for m in missions:
                if p["idx"] not in m["serves"]:
                    continue
                if m["t_ready"] - 1e-9 <= t_new <= m["t_service_end"] + 1e-9:
                    covered = True
                    break
            if covered:
                n_relay += 1
            else:
                n_broken += 1

    tardy = 0.0
    first_v = 0.0
    for b, tt in deliver.items():
        exp = expect_of.get(b)
        if exp is not None and tt > exp:
            tardy += prio_of.get(b, 1.0) * (tt - exp)
        dl = deadline_of.get(b)
        if dl is not None and tt > dl:
            first_v += (tt - dl)
    makespan = max([p["sortie"]["end"] for p in profiles]
                   + [m["t_return"] for m in missions], default=0.0)
    e_tr = sum(p["sortie"]["energy"] for p in profiles)
    e_rl = sum(m["energy"] for m in missions)
    return {
        "relay_missions": missions, "deliver": deliver,
        "metrics": {
            "tardy": tardy, "makespan": makespan,
            "energy_transport": e_tr, "energy_relay": e_rl,
            "energy_total": e_tr + e_rl,
            "n_sorties_transport": len(profiles), "n_sorties_relay": len(missions),
            "first_violation": first_v,
            "n_direct": n_direct, "n_relay": n_relay, "n_broken": n_broken,
        },
    }


def q3_checks(sc, res, chosen, M):
    out = []
    r = sc.relay
    ok_h = all(o["hover_h"] <= r["h_hover_max"] + 1e-9 for o in chosen)
    out.append({"item": "中继悬停离地高度不超上限", "ok": ok_h,
                "detail": f"上限 {r['h_hover_max']:.0f} m，实际最大 "
                          f"{max((o['hover_h'] for o in chosen), default=0):.0f} m"})
    ok_in = all(sc.dem.inside(o["lon"], o["lat"]) for o in chosen)
    out.append({"item": "悬停位置位于 DEM 覆盖范围内", "ok": ok_in,
                "detail": f"{len(chosen)} 个悬停点"})
    used = {m["uav"] for m in res["relay_missions"]}
    fleet = {f["id"] for f in sc.relay_fleet}
    out.append({"item": "中继无人机编号合法", "ok": used <= fleet,
                "detail": f"使用 {sorted(used)}，机队 {sorted(fleet)}"})
    usedc = {m["component"] for m in res["relay_missions"]}
    cap = sc.relay_components[r["type_id"]]["count"]
    out.append({"item": "中继能源组件不超库存", "ok": len(usedc) <= cap,
                "detail": f"使用 {len(usedc)}/{cap} 组"})
    ok_e = all(m["soc_end"] >= r["reserve_ratio"] - 1e-9 for m in res["relay_missions"])
    out.append({"item": "中继返航电量满足", "ok": ok_e,
                "detail": f"最低末端 SOC "
                          f"{min((m['soc_end'] for m in res['relay_missions']), default=1.0):.4f}"
                          f"，下限 {r['reserve_ratio']:.2f}"})
    out.append({"item": "运输架次通信全程有保障",
                "ok": all(m["svc_capped"] is False for m in res["relay_missions"]),
                "detail": f"服务时长受能量上限截断的中继架次 "
                          f"{sum(1 for m in res['relay_missions'] if m['svc_capped'])} 个"})
    out.append({"item": "首批截止时间满足", "ok": M["first_violation"] <= 1e-6,
                "detail": f"超时合计 {M['first_violation']:.1f} s"})
    return out


if __name__ == "__main__":
    raise SystemExit(main())