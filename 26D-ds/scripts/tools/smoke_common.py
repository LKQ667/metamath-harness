# -*- coding: utf-8 -*-
"""冒烟测试：验证公共数据层能正确读取附件与 DEM。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common_d import (  # noqa: E402
    COMM, build_scenario, charge_time, equivalent_range, haversine,
    link_max_loss, seg_energy, seg_geometry, seg_time, link_available,
    gateway_point, altitude_of,
)

sc = build_scenario()
print("调度中心:", sc.center["id"], sc.center["name"], sc.center["lon"], sc.center["lat"], sc.center["alt"])
print("服务区数:", len(sc.areas))
print("机型:", {k: (v["q_max"], v["vol_max"], v["battery_energy"], v["range_empty"], v["range_full"]) for k, v in sc.types.items()})
print("机队:", [(f["id"], f["type_id"]) for f in sc.fleet])
print("共享电池:", {k: v["count"] for k, v in sc.batteries.items()})
print("中继:", sc.relay["type_id"], sc.relay["energy_component"], sc.relay["h_hover_max"])
print("中继机队:", [f["id"] for f in sc.relay_fleet])
print("中继组件:", {k: v["count"] for k, v in sc.relay_components.items()})
print("货箱数:", len(sc.boxes))
print("DEM shape:", sc.dem.elev.shape, "res:", sc.dem.res)

# DEM 高程与附件海拔对比
print("\n--- 节点海拔核对（附件值 vs DEM 采样） ---")
for a in sc.areas:
    e = sc.dem.sample(a["lon"], a["lat"])
    print(f"  {a['id']} 附件={a['alt']:7.1f}  DEM={e:7.1f}  差={e - a['alt']:7.1f}")
c = sc.center
print(f"  {c['id']} 附件={c['alt']:7.1f}  DEM={sc.dem.sample(c['lon'], c['lat']):7.1f}")

# 航段几何抽样
print("\n--- 航段几何（O01 -> 各服务区） ---")
for a in sc.areas[:5]:
    g = seg_geometry(sc, "O01", a["id"])
    tA = sc.types["A"]
    print(f"  O01->{a['id']} d={g['d']:8.1f}m cruise={g['cruise_alt']:7.1f} climb={g['climb']:6.1f} desc={g['descend']:6.1f} "
          f"t={seg_time(sc, tA, 'O01', a['id']):6.1f}s")

# 等效航程与能耗
print("\n--- 等效航程 L_g(q) ---")
for k, t in sc.types.items():
    for q in (0, t["q_max"] * 0.5, t["q_max"]):
        print(f"  {k} q={q:5.1f} -> L={equivalent_range(t, q):9.1f} m")

print("\n--- 满载荷单点往返可行性（机型 A/B/C 对 S001） ---")
a = sc.areas[0]
for k, t in sc.types.items():
    q = t["q_max"]
    e1 = seg_energy(sc, t, "O01", a["id"], q)
    e2 = seg_energy(sc, t, a["id"], "O01", q)
    tot = e1 + e2
    lim = (1 - t["reserve_ratio"]) * t["battery_energy"]
    print(f"  {k}: 去 {e1:.4f} 回 {e2:.4f} 合计 {tot:.4f} kWh  余量上限 {lim:.4f} kWh  {'可行' if tot <= lim else '超限'}")

# 通信
print("\n--- 通信门限与直连可用性 ---")
print("  Lmax(uav<->gateway) =", round(link_max_loss("uav", "gateway"), 2), "dB")
print("  Lmax(uav<->relay_acc) =", round(link_max_loss("uav", "relay_acc"), 2), "dB")
print("  Lmax(relay_back<->gateway) =", round(link_max_loss("relay_back", "gateway"), 2), "dB")
gw = gateway_point(sc)
for a in sc.areas[:4]:
    p = (a["lon"], a["lat"], a["alt"] + 30.0)
    ok = link_available(sc, p, gw, "uav", "gateway")
    print(f"  {a['id']} 运输无人机(作业高度) 直连 G01: {'可用' if ok else '不可用'}")

# 充电
print("\n--- 充电时间 ---")
for s in (0.2, 0.5, 0.89, 0.95, 1.0):
    print(f"  s={s:.2f} -> t_chg={charge_time(s, 1800):7.1f} s (A型 Tfull=1800)")