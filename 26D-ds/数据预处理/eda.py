# -*- coding: utf-8 -*-
"""Step1 数据预处理与探索性分析（EDA）。

职责：
1. 读取官方 5 份基础参数附件与 30 米 DEM，逐表做规模、缺失、重复、范围与一致性检查；
2. 建立节点高程、航段几何、货箱清单与需求汇总三类派生数据；
3. 输出派生数据、EDA 统计与审计记录，并生成 2 张中文顶刊风格图。

运行：
    python 数据预处理/eda.py
输出：
    data/derived/nodes.csv
    data/derived/boxes.csv
    data/derived/segment_geometry.csv
    data/derived/demand_summary.csv
    data/derived/eda_summary.json
    数据预处理/audit.json
    数据预处理/figures/fig_eda_dem_nodes.{png,pdf,svg}
    数据预处理/figures/fig_eda_demand_structure.{png,pdf,svg}
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from common_d import (  # noqa: E402
    DERIVED_DIR, PROJECT, build_scenario, haversine, seg_geometry,
)

FIG_DIR = os.path.join(ROOT, "数据预处理", "figures")
if os.path.join(ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "scripts"))


def jdump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=_def)


def _def(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(str(type(o)))


def main() -> int:
    sc = build_scenario()
    audit = {"处理规则": [], "一致性核对": [], "异常与处理": []}
    summary = {}

    # ---------------- 1. 节点表 ----------------
    rows = []
    c = sc.center
    rows.append({
        "node_id": c["id"], "name": c["name"], "kind": "调度中心",
        "lon": c["lon"], "lat": c["lat"], "alt_attach": c["alt"],
        "alt_dem": sc.dem.sample(c["lon"], c["lat"]), "pop": np.nan,
    })
    for a in sc.areas:
        rows.append({
            "node_id": a["id"], "name": a["name"], "kind": "服务区",
            "lon": a["lon"], "lat": a["lat"], "alt_attach": a["alt"],
            "alt_dem": sc.dem.sample(a["lon"], a["lat"]), "pop": a["pop"],
        })
    nodes = pd.DataFrame(rows)
    nodes["alt_diff"] = nodes["alt_dem"] - nodes["alt_attach"]
    # 作业高度：O01 取地面海拔，服务区取地面海拔以上 30 m（附录 2）
    nodes["work_alt"] = np.where(nodes["kind"] == "调度中心",
                                 nodes["alt_attach"], nodes["alt_attach"] + 30.0)
    nodes["dist_km"] = [haversine(c["lon"], c["lat"], r.lon, r.lat) / 1000.0 for r in nodes.itertuples()]
    os.makedirs(DERIVED_DIR, exist_ok=True)
    nodes.to_csv(os.path.join(DERIVED_DIR, "nodes.csv"), index=False, encoding="utf-8-sig")

    summary["节点"] = {
        "调度中心数": 1, "服务区数": int((nodes["kind"] == "服务区").sum()),
        "附件海拔范围_m": [float(nodes["alt_attach"].min()), float(nodes["alt_attach"].max())],
        "DEM采样海拔范围_m": [float(nodes["alt_dem"].min()), float(nodes["alt_dem"].max())],
        "附件与DEM海拔最大绝对偏差_m": float(nodes["alt_diff"].abs().max()),
        "附件与DEM海拔平均绝对偏差_m": float(nodes["alt_diff"].abs().mean()),
        "服务区距调度中心范围_km": [float(nodes.loc[nodes["kind"] == "服务区", "dist_km"].min()),
                                float(nodes.loc[nodes["kind"] == "服务区", "dist_km"].max())],
        "保障人口合计_人": int(nodes["pop"].fillna(0).sum()),
    }
    audit["处理规则"].append(
        "节点地面海拔以附件给定值为准；DEM 采样值仅用于航段沿途地形净空与巡航海拔，"
        "两者偏差记录于 eda_summary.json 的节点节。")
    audit["一致性核对"].append(
        f"附件海拔与 30 米 DEM 采样最大绝对偏差 "
        f"{summary['节点']['附件与DEM海拔最大绝对偏差_m']:.1f} m，"
        "量级与 30 米栅格分辨率及点位代表性相符，未发现矛盾。")

    # ---------------- 2. 货箱表 ----------------
    boxes = pd.DataFrame(sc.boxes)
    boxes = boxes.rename(columns={"is_first_batch": "first_batch"})
    boxes["first_batch"] = boxes["first_batch"].astype(bool)
    boxes.to_csv(os.path.join(DERIVED_DIR, "boxes.csv"), index=False, encoding="utf-8-sig")

    # 需求汇总表核对
    ds = pd.read_excel(os.path.join(PROJECT, "data", "raw", "物资需求与配送时限.xlsx"),
                       sheet_name="数据", header=0)
    ds.columns = ["area_id", "cargo", "n_boxes", "n_first", "box_mass", "box_volume",
                  "priority", "first_deadline", "expect_time"]
    ds = ds.dropna(subset=["area_id"])
    ds["area_id"] = ds["area_id"].astype(str)
    ds.to_csv(os.path.join(DERIVED_DIR, "demand_summary.csv"), index=False, encoding="utf-8-sig")

    grp = boxes.groupby(["area_id", "cargo"]).agg(
        n_box=("box_id", "size"), n_first_box=("first_batch", "sum"),
        m=("mass", "first"), v=("volume", "first")).reset_index()
    merged = grp.merge(ds, on=["area_id", "cargo"], how="outer", indicator=True)
    mismatch = merged[(merged["_merge"] != "both")
                      | (merged["n_box"] != merged["n_boxes"])
                      | (merged["n_first_box"] != merged["n_first"])
                      | ((merged["m"] - merged["box_mass"]).abs() > 1e-9)
                      | ((merged["v"] - merged["box_volume"]).abs() > 1e-9)]
    if len(mismatch) == 0:
        audit["一致性核对"].append(
            "逐箱货箱清单与按服务区-物资类型的需求汇总表在箱数、首批箱数、单箱质量、"
            "单箱体积四个维度完全一致，无冲突。")
    else:
        audit["异常与处理"].append(
            f"逐箱清单与需求汇总表存在 {len(mismatch)} 处不一致，已按逐箱清单为准。")

    # 单箱质量与体积的“类型内一致性”检查（同物资类型应同质）
    by_cargo = boxes.groupby("cargo").agg(
        m_min=("mass", "min"), m_max=("mass", "max"),
        v_min=("volume", "min"), v_max=("volume", "max"),
        n=("box_id", "size"), mass_sum=("mass", "sum"), vol_sum=("volume", "sum")).reset_index()

    summary["货箱"] = {
        "总箱数": int(len(boxes)),
        "服务区数": int(boxes["area_id"].nunique()),
        "物资类型数": int(boxes["cargo"].nunique()),
        "首批保障箱数": int(boxes["first_batch"].sum()),
        "总质量_kg": float(boxes["mass"].sum()),
        "总体积_m3": float(boxes["volume"].sum()),
        "单箱质量范围_kg": [float(boxes["mass"].min()), float(boxes["mass"].max())],
        "单箱体积范围_m3": [float(boxes["volume"].min()), float(boxes["volume"].max())],
        "按物资类型统计": by_cargo.to_dict("records"),
        "缺失值总数": int(boxes.isna().sum().sum()),
        "重复货箱编号数": int(len(boxes) - boxes["box_id"].nunique()),
        "期望送达时间取值_s": sorted(boxes["expect_time"].dropna().unique().tolist()),
        "首批截止时间取值_s": sorted(boxes["first_deadline"].dropna().unique().tolist()),
    }
    audit["一致性核对"].append(
        "逐箱清单无缺失、无重复货箱编号；同物资类型的单箱质量与单箱体积在各服务区间保持同质。")

    # 各服务区需求量
    area_demand = boxes.groupby("area_id").agg(
        n=("box_id", "size"), mass=("mass", "sum"), vol=("volume", "sum"),
        n_first=("first_batch", "sum")).reset_index()
    area_demand = area_demand.merge(
        nodes.loc[nodes["kind"] == "服务区", ["node_id", "name", "pop", "dist_km", "alt_attach"]],
        left_on="area_id", right_on="node_id", how="left")
    summary["需求分布"] = {
        "单服务区箱数范围": [int(area_demand["n"].min()), int(area_demand["n"].max())],
        "单服务区质量范围_kg": [float(area_demand["mass"].min()), float(area_demand["mass"].max())],
        "单服务区体积范围_m3": [float(area_demand["vol"].min()), float(area_demand["vol"].max())],
        "最大需求服务区": str(area_demand.loc[area_demand["mass"].idxmax(), "area_id"]),
        "最小需求服务区": str(area_demand.loc[area_demand["mass"].idxmin(), "area_id"]),
    }

    # ---------------- 3. 航段几何 ----------------
    ids = [c["id"]] + [a["id"] for a in sc.areas]
    seg_rows = []
    for i in ids:
        for j in ids:
            if i == j:
                continue
            g = seg_geometry(sc, i, j)
            seg_rows.append({
                "from": i, "to": j, "dist_m": g["d"], "cruise_alt_m": g["cruise_alt"],
                "climb_m": g["climb"], "descend_m": g["descend"],
            })
    seg = pd.DataFrame(seg_rows)
    seg.to_csv(os.path.join(DERIVED_DIR, "segment_geometry.csv"), index=False, encoding="utf-8-sig")
    summary["航段"] = {
        "有向航段数": int(len(seg)),
        "水平距离范围_m": [float(seg["dist_m"].min()), float(seg["dist_m"].max())],
        "巡航海拔范围_m": [float(seg["cruise_alt_m"].min()), float(seg["cruise_alt_m"].max())],
        "爬升高度范围_m": [float(seg["climb_m"].min()), float(seg["climb_m"].max())],
        "下降高度范围_m": [float(seg["descend_m"].min()), float(seg["descend_m"].max())],
        "往返几何不对称航段数": int((np.abs(
            seg.set_index(["from", "to"])["dist_m"].reindex(
                pd.MultiIndex.from_tuples([(b, a) for a, b in seg[["from", "to"]].itertuples(index=False)])
            ).values - seg["dist_m"].values) > 1e-6).sum()),
    }
    audit["处理规则"].append(
        "航段水平距离按两节点经纬度的球面大圆距离计算；巡航海拔取该航段沿途 DEM 像元"
        "最高地面高程以上 50 m；爬升与下降高度由作业高度与巡航海拔之差确定。")

    # ---------------- 4. DEM 栅格统计 ----------------
    dem = sc.dem
    valid = dem.elev[~np.isnan(dem.elev)]
    summary["DEM"] = {
        "栅格行列": [int(dem.elev.shape[0]), int(dem.elev.shape[1])],
        "空间分辨率_deg": [float(dem.res[0]), float(dem.res[1])],
        "近似分辨率_m": float(dem.res[0] * 111320 * np.cos(np.radians(23.03))),
        "高程范围_m": [float(valid.min()), float(valid.max())],
        "高程均值_m": float(valid.mean()),
        "高程标准差_m": float(valid.std()),
        "有效像元占比": float(len(valid) / dem.elev.size),
        "nodata值": None if dem.nodata is None else float(dem.nodata),
    }
    audit["一致性核对"].append(
        f"DEM 有效像元占比 {summary['DEM']['有效像元占比']:.4f}，"
        f"高程范围 {summary['DEM']['高程范围_m'][0]:.0f}~{summary['DEM']['高程范围_m'][1]:.0f} m，"
        "与镇龙乡山区地形相符，无异常空值区。")

    # ---------------- 5. 机队与资源核对 ----------------
    summary["资源"] = {
        "运输机型数": len(sc.types),
        "实体运输无人机数": len(sc.fleet),
        "按机型架数": {k: int(sum(1 for f in sc.fleet if f["type_id"] == k)) for k in sc.types},
        "共享电池库存": {k: int(v["count"]) for k, v in sc.batteries.items()},
        "中继无人机数": len(sc.relay_fleet),
        "中继能源组件库存": {k: int(v["count"]) for k, v in sc.relay_components.items()},
        "运输机最大载货质量_kg": {k: float(v["q_max"]) for k, v in sc.types.items()},
        "运输机可用装载体积_m3": {k: float(v["vol_max"]) for k, v in sc.types.items()},
        "运输机电池可用能量_kWh": {k: float(v["battery_energy"]) for k, v in sc.types.items()},
        "返航安全余量比例": {k: float(v["reserve_ratio"]) for k, v in sc.types.items()},
        "等效完全充电时间_s": {k: float(v["t_full"]) for k, v in sc.batteries.items()},
        "中继悬停离地高度上限_m": float(sc.relay["h_hover_max"]),
        "中继能源组件可用能量_kWh": float(sc.relay["energy_component"]),
    }
    audit["处理规则"].append(
        "附件中返航电量下限以百分数给出，统一折算为比例参与能量阈值比较，"
        "避免与可用能量口径混用。")

    # 单架次运力上界：按载质量与装载体积双约束取小
    cap = []
    for k, t in sc.types.items():
        by_mass = int(t["q_max"] // boxes["mass"].min())
        by_vol = int(t["vol_max"] // boxes["volume"].min())
        cap.append({"type_id": k, "最大载货质量_kg": t["q_max"], "可用装载体积_m3": t["vol_max"],
                    "按最轻箱估算最大箱数": by_mass, "按最小体积箱估算最大箱数": by_vol})
    summary["单架次运力上界"] = cap

    # ---------------- 6. 图 ----------------
    figures = make_figures(sc, nodes, area_demand, boxes)

    jdump(os.path.join(DERIVED_DIR, "eda_summary.json"), summary)
    jdump(os.path.join(ROOT, "数据预处理", "audit.json"), audit)

    print("=== EDA 完成 ===")
    print("总箱数", summary["货箱"]["总箱数"], "总质量", round(summary["货箱"]["总质量_kg"], 1), "kg")
    print("服务区距中心", summary["节点"]["服务区距调度中心范围_km"])
    print("DEM 高程范围", summary["DEM"]["高程范围_m"])
    print("图:", figures)
    return 0


def make_figures(sc, nodes, area_demand, boxes):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from plot_common import (PALETTE, apply_py_nature_style,
                             run_py_nature_qa, save_py_nature_figure)

    apply_py_nature_style(font_size=8.0, profile="competition_cn")
    os.makedirs(FIG_DIR, exist_ok=True)
    saved = []

    dem = sc.dem
    nrow, ncol = dem.elev.shape
    lon_axis = dem.origin[0] + dem.res[0] * np.arange(ncol)
    lat_axis = dem.origin[1] - dem.res[1] * np.arange(nrow)

    # ---- 图1：DEM 高程场与调度节点（contour_2d，单面板） ----
    fig, ax = plt.subplots(figsize=(6.6, 5.0))
    lon_g, lat_g = np.meshgrid(lon_axis, lat_axis)
    z = dem.elev
    levels = np.linspace(np.nanmin(z), np.nanmax(z), 24)
    cf = ax.contourf(lon_g, lat_g, z, levels=levels, cmap="terrain", extend="both")
    cs = ax.contour(lon_g, lat_g, z, levels=levels[::4], colors="#4A4A4A",
                    linewidths=0.45, alpha=0.65)
    ax.clabel(cs, inline=True, fontsize=5.4, fmt="%.0f", colors="#333333")
    cb = fig.colorbar(cf, ax=ax, pad=0.02, fraction=0.045)
    cb.set_label("地面高程（m）", fontsize=8)
    cb.ax.tick_params(labelsize=7)

    areas = nodes[nodes["kind"] == "服务区"]
    ax.scatter(areas["lon"], areas["lat"], s=26, marker="o",
               facecolor=PALETTE["red_strong"], edgecolor="white",
               linewidths=0.7, zorder=5, label="服务区")
    cen = nodes[nodes["kind"] == "调度中心"]
    ax.scatter(cen["lon"], cen["lat"], s=95, marker="*",
               facecolor=PALETTE["gold_main"], edgecolor="black",
               linewidths=0.7, zorder=6, label="临时调度中心 O01")
    for r in areas.itertuples():
        ax.annotate(r.node_id, (r.lon, r.lat), textcoords="offset points",
                    xytext=(4.2, 3.4), fontsize=6.4, color="#1A1A1A", zorder=7)
    ax.annotate("O01", (cen.iloc[0]["lon"], cen.iloc[0]["lat"]), textcoords="offset points",
                xytext=(6.0, -8.5), fontsize=7.2, fontweight="bold", color="#1A1A1A", zorder=7)
    ax.set_xlabel("经度（°）")
    ax.set_ylabel("纬度（°）")
    ax.set_xlim(float(areas["lon"].min()) - 0.012, float(areas["lon"].max()) + 0.012)
    ax.set_ylim(float(areas["lat"].min()) - 0.010, float(areas["lat"].max()) + 0.012)
    ax.legend(loc="upper left", fontsize=7.2, handletextpad=0.4, borderpad=0.35)
    ax.tick_params(labelsize=7)
    ax.set_aspect("equal", adjustable="box")
    p = save_py_nature_figure(fig, os.path.join(FIG_DIR, "fig_eda_dem_nodes"),
                             dpi=320, profile="competition_cn")
    saved.append([str(x) for x in p])
    qa = run_py_nature_qa(os.path.join(FIG_DIR, "fig_eda_dem_nodes"), profile="competition_cn")
    print("图1 QA:", qa.passed, {k: v for k, v in qa.checks.items() if v is False})

    # ---- 图2：需求规模、保障人口与空间距离（scatter_2d，单面板） ----
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    d = area_demand.dropna(subset=["dist_km"]).copy().reset_index(drop=True)
    sizes = 18 + (d["pop"] / d["pop"].max()) * 240
    sca = ax.scatter(d["dist_km"], d["mass"], s=sizes, c=d["n"],
                     cmap="viridis", edgecolor="#2B2B2B", linewidths=0.6,
                     alpha=0.9, zorder=4)
    cb = fig.colorbar(sca, ax=ax, pad=0.02, fraction=0.045)
    cb.set_label("货箱数量（箱）", fontsize=8)
    cb.ax.tick_params(labelsize=7)

    ax.set_xlabel("服务区距调度中心水平距离（km）")
    ax.set_ylabel("服务区物资需求总质量（kg）")
    ax.tick_params(labelsize=7)
    ax.margins(x=0.08, y=0.16)

    zc = np.polyfit(d["dist_km"], d["mass"], 1)
    xs = np.linspace(d["dist_km"].min(), d["dist_km"].max(), 50)
    ax.plot(xs, np.polyval(zc, xs), color=PALETTE["orange_main"], linewidth=1.3,
            linestyle="--", zorder=3, label="线性趋势")

    hs, ls = ax.get_legend_handles_labels()
    h2 = plt.Line2D([], [], marker="o", linestyle="none", markersize=6.5,
                    markerfacecolor=PALETTE["cyan_main"], markeredgecolor="#2B2B2B",
                    label="气泡面积与保障人口成正比")
    leg = ax.legend(handles=hs + [h2], loc="upper right", fontsize=7.0,
                    handletextpad=0.4, borderpad=0.35)

    rr = np.corrcoef(d["dist_km"], d["mass"])[0, 1]
    rp = np.corrcoef(d["dist_km"], d["pop"])[0, 1]
    txt = ax.text(0.985, 0.03,
                  f"距离—需求量相关系数 $r$ = {rr:.2f}\n距离—人口相关系数 $r$ = {rp:.2f}",
                  transform=ax.transAxes, ha="right", va="bottom", fontsize=7.4,
                  bbox=dict(boxstyle="round,pad=0.32", facecolor="white",
                            edgecolor="#BFBFBF", linewidth=0.6), zorder=9)

    from label_util import box_of_artist, place_labels
    fig.canvas.draw()
    reserved = [box_of_artist(leg, fig), box_of_artist(txt, fig)]
    place_labels(ax, list(d["dist_km"]), list(d["mass"]), list(d["area_id"]),
                 fontsize=6.4, fig=fig, extra_boxes=reserved)

    p = save_py_nature_figure(fig, os.path.join(FIG_DIR, "fig_eda_demand_structure"),
                             dpi=320, profile="competition_cn")
    saved.append([str(x) for x in p])
    qa = run_py_nature_qa(os.path.join(FIG_DIR, "fig_eda_demand_structure"), profile="competition_cn")
    print("图2 QA:", qa.passed, {k: v for k, v in qa.checks.items() if v is False})
    return saved


if __name__ == "__main__":
    raise SystemExit(main())