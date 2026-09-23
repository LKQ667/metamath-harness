# -*- coding: utf-8 -*-
"""D 题公共数据层：附件解析、DEM 读取、航段物理模型与通信链路判定。

本模块是全项目唯一的物理规则实现处，供 Q1-Q4、灵敏度分析与总控脚本复用。
所有原始参数一律从 赛题/数据/ 的官方附件读取，禁止硬编码覆盖附件值。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEM_DIR = os.path.join(PROJECT, "赛题")
DATA_DIR = os.path.join(PROBLEM_DIR, "数据")
BASIC_DIR = os.path.join(DATA_DIR, "无人机应急物资运输基础数据")
GEO_DIR = os.path.join(DATA_DIR, "镇龙乡地理空间数据", "镇龙乡及周边地理数据")
DERIVED_DIR = os.path.join(PROJECT, "data", "derived")
RESULTS_DIR = os.path.join(PROJECT, "results")

R_EARTH = 6371008.8  # 平均地球半径 (m)


# ---------------------------------------------------------------------------
# 官方附件读取
# ---------------------------------------------------------------------------
def _sheet(path: str, sheet=0):
    return pd.read_excel(path, sheet_name=sheet, header=None)


def read_centers() -> pd.DataFrame:
    """调度中心 O01；列: id, name, lon, lat, alt"""
    df = _sheet(os.path.join(BASIC_DIR, "调度中心与服务区.xlsx"))
    row = df.iloc[2]
    return pd.DataFrame([{
        "id": str(row[0]), "name": str(row[1]),
        "lon": float(row[2]), "lat": float(row[3]), "alt": float(row[4]),
    }])


def read_service_areas() -> pd.DataFrame:
    """15 个服务区；列: id, name, lon, lat, alt, pop"""
    df = _sheet(os.path.join(BASIC_DIR, "调度中心与服务区.xlsx"))
    rows = []
    for i in range(6, len(df)):
        r = df.iloc[i]
        if pd.isna(r[0]):
            continue
        rows.append({
            "id": str(r[0]), "name": str(r[1]),
            "lon": float(r[2]), "lat": float(r[3]), "alt": float(r[4]),
            "pop": float(r[5]),
        })
    return pd.DataFrame(rows)


def read_uav_types() -> pd.DataFrame:
    """三类运输机型参数（机型 A/B/C）。"""
    df = _sheet(os.path.join(BASIC_DIR, "运输无人机数据.xlsx"))
    cols = ["type_id", "type_name", "mass_empty", "q_max", "vol_max",
            "v_cruise", "range_empty", "range_full", "battery_energy",
            "reserve_ratio", "t_prepare", "t_load_per_box", "t_handover_base",
            "t_handover_per_box", "v_climb", "v_descend", "eta_climb", "eta_descend"]
    rows = []
    for i in range(2, 5):
        r = df.iloc[i]
        rows.append(dict(zip(cols, [r[j] for j in range(len(cols))])))
    out = pd.DataFrame(rows)
    out["type_id"] = out["type_id"].astype(str)
    for c in cols[2:]:
        out[c] = out[c].astype(float)
    # 附件中返航电量下限以百分数给出，统一折算为比例，避免与能量阈值口径混用。
    out["reserve_ratio"] = out["reserve_ratio"] / 100.0
    return out


def read_uav_fleet() -> pd.DataFrame:
    """8 架实体运输无人机；列: id, type_id, home"""
    df = _sheet(os.path.join(BASIC_DIR, "运输无人机数据.xlsx"))
    rows = []
    for i in range(8, 16):
        r = df.iloc[i]
        if pd.isna(r[0]):
            continue
        rows.append({"id": str(r[0]), "type_id": str(r[1]), "home": str(r[2])})
    return pd.DataFrame(rows)


def read_transport_batteries() -> pd.DataFrame:
    """共享电池库存；列: type_id, count, t_full"""
    df = _sheet(os.path.join(BASIC_DIR, "运输无人机数据.xlsx"))
    rows = []
    for i in range(19, len(df)):
        r = df.iloc[i]
        if pd.isna(r[0]):
            continue
        rows.append({"type_id": str(r[0]), "count": int(r[1]), "t_full": float(r[2])})
    return pd.DataFrame(rows)


def read_relay_type() -> dict:
    """中继机型 R 参数。"""
    df = _sheet(os.path.join(BASIC_DIR, "中继无人机数据.xlsx"))
    r = df.iloc[2]
    keys = ["type_id", "type_name", "mass_empty", "mass_comm", "mass_takeoff",
            "v_cruise", "p_cruise", "energy_component", "reserve_ratio",
            "t_prepare", "t_link", "t_turnaround", "v_climb", "v_descend",
            "eta_climb", "eta_descend", "p_hover", "p_comm_extra", "h_hover_max"]
    out = dict(zip(keys, [r[j] for j in range(len(keys))]))
    for k in keys[2:]:
        out[k] = float(out[k])
    out["type_id"] = str(out["type_id"])
    # 附件中返航电量下限以百分数给出，统一折算为比例。
    out["reserve_ratio"] = out["reserve_ratio"] / 100.0
    return out


def read_relay_fleet() -> pd.DataFrame:
    """2 架中继无人机 R01/R02。"""
    df = _sheet(os.path.join(BASIC_DIR, "中继无人机数据.xlsx"))
    rows = []
    for i in range(6, 9):
        r = df.iloc[i]
        if pd.isna(r[0]):
            continue
        rows.append({"id": str(r[0]), "type_id": str(r[1]), "home": str(r[2])})
    return pd.DataFrame(rows)


def read_relay_components() -> pd.DataFrame:
    """中继能源组件库存。"""
    df = _sheet(os.path.join(BASIC_DIR, "中继无人机数据.xlsx"))
    rows = []
    for i in range(11, len(df)):
        r = df.iloc[i]
        if pd.isna(r[0]):
            continue
        rows.append({"type_id": str(r[0]), "count": int(r[1]), "t_full": float(r[2])})
    return pd.DataFrame(rows)


def read_demand_boxes() -> pd.DataFrame:
    """80 个不可拆货箱逐箱清单。"""
    df = pd.read_excel(os.path.join(BASIC_DIR, "物资需求与配送时限.xlsx"),
                       sheet_name="逐箱货箱清单", header=0)
    df.columns = ["box_id", "area_id", "cargo", "mass", "volume",
                  "is_first_batch", "first_deadline", "expect_time", "priority"]
    df["is_first_batch"] = df["is_first_batch"].astype(str).str.strip().eq("是")
    return df


def read_demand_summary() -> pd.DataFrame:
    """按服务区-物资类型汇总的需求表。"""
    df = _sheet(os.path.join(BASIC_DIR, "物资需求与配送时限.xlsx"), sheet=0)
    rows = []
    for i in range(1, len(df)):
        r = df.iloc[i]
        if pd.isna(r[0]):
            continue
        rows.append({
            "area_id": str(r[0]), "cargo": str(r[1]),
            "n_boxes": int(r[2]), "n_first": int(r[3]),
            "box_mass": float(r[4]), "box_volume": float(r[5]),
            "priority": float(r[6]),
            "first_deadline": float(r[7]) if not pd.isna(r[7]) else None,
            "expect_time": float(r[8]) if not pd.isna(r[8]) else None,
        })
    return pd.DataFrame(rows)


def read_comm_params() -> dict:
    """通信链路参数。"""
    df = _sheet(os.path.join(BASIC_DIR, "通信链路参数.xlsx"))
    raw = {}
    for i in range(2, len(df)):
        r = df.iloc[i]
        if pd.isna(r[0]):
            continue
        raw[str(r[1]).strip()] = float(r[4])
    return {
        "freq_mhz": raw["载波频率（MHz）"],
        "L_sys": raw["系统损耗（dB）"],
        "L_obs": raw["地形遮挡附加损耗（dB）"],
        "P_sens": raw["接收灵敏度（dBm）"],
        "M_fade": raw["衰落裕量（dB）"],
        "t_uav_Pt": raw["发射功率（dBm）"],          # 运输无人机
        "t_uav_G": raw["天线增益（dBi）"],
        "relay_acc_Pt": raw["发射功率（dBm）"],       # 中继接入端（第二个 Pt 出现）
        "relay_acc_G": raw["天线增益（dBi）"],
        "gateway_h": raw["天线离地高度（m）"],
    }


def _comm_params_full() -> dict:
    """完整通信参数：按参数类别区分同名 Pt/G。"""
    df = _sheet(os.path.join(BASIC_DIR, "通信链路参数.xlsx"))
    out = {}
    for i in range(2, len(df)):
        r = df.iloc[i]
        cat = str(r[0]).strip()
        name = str(r[1]).strip()
        val = float(r[4])
        if cat == "传播参数":
            out[name] = val
        elif cat == "接收参数":
            out[name] = val
        else:
            out.setdefault(cat, {})[name] = val
    p = {
        "freq_mhz": out["载波频率（MHz）"],
        "L_sys": out["系统损耗（dB）"],
        "L_obs": out["地形遮挡附加损耗（dB）"],
        "P_sens": out["接收灵敏度（dBm）"],
        "M_fade": out["衰落裕量（dB）"],
    }
    for cat, key in (("运输无人机", "uav"), ("中继接入端", "relay_acc"),
                     ("中继回传端", "relay_back"), ("固定网关 G01", "gateway")):
        blk = out[cat]
        p[key] = {
            "Pt": blk.get("发射功率（dBm）"),
            "G": blk.get("天线增益（dBi）"),
            "h": blk.get("天线离地高度（m）", 0.0),
        }
    return p


COMM = _comm_params_full()


# ---------------------------------------------------------------------------
# 地理与 DEM
# ---------------------------------------------------------------------------
class DEM:
    """30 米 DEM 栅格读取与双线性插值。"""

    def __init__(self, tif_path: str):
        import rasterio  # 延迟导入，缺失时给出明确错误
        with rasterio.open(tif_path) as src:
            self.elev = src.read(1).astype(np.float64)
            self.transform = src.transform
            self.crs = src.crs
            self.nodata = src.nodata
            self.bounds = src.bounds
            self.res = (src.transform.a, -src.transform.e)
            self.origin = (src.transform.c, src.transform.f)
        if self.nodata is not None:
            self.elev = np.where(self.elev == self.nodata, np.nan, self.elev)

    def _rc(self, lon, lat):
        col = (np.asarray(lon) - self.origin[0]) / self.res[0]
        row = (self.origin[1] - np.asarray(lat)) / self.res[1]
        return row, col

    def sample(self, lon, lat):
        """双线性插值取高程；越界返回最近边界值。"""
        row, col = self._rc(lon, lat)
        nrow, ncol = self.elev.shape
        row = float(np.clip(row, 0, nrow - 1.001))
        col = float(np.clip(col, 0, ncol - 1.001))
        r0, c0 = int(math.floor(row)), int(math.floor(col))
        r1, c1 = min(r0 + 1, nrow - 1), min(c0 + 1, ncol - 1)
        dr, dc = row - r0, col - c0
        e = self.elev
        v = ((1 - dr) * ((1 - dc) * e[r0, c0] + dc * e[r0, c1])
             + dr * ((1 - dc) * e[r1, c0] + dc * e[r1, c1]))
        return float(v)

    def inside(self, lon, lat) -> bool:
        row, col = self._rc(lon, lat)
        nrow, ncol = self.elev.shape
        return bool(0 <= float(row) <= nrow - 1 and 0 <= float(col) <= ncol - 1)

    def max_elev_profile(self, lon1, lat1, lon2, lat2, n=400):
        """两节点连线沿途的 DEM 最高像元高程（用于巡航海拔与地形净空）。"""
        t = np.linspace(0.0, 1.0, n)
        lon = lon1 + (lon2 - lon1) * t
        lat = lat1 + (lat2 - lat1) * t
        row, col = self._rc(lon, lat)
        nrow, ncol = self.elev.shape
        ri = np.clip(np.round(row).astype(int), 0, nrow - 1)
        ci = np.clip(np.round(col).astype(int), 0, ncol - 1)
        return float(np.nanmax(self.elev[ri, ci]))

    def los_blocked(self, lon1, lat1, h1, lon2, lat2, h2, n=300) -> bool:
        """视线遮挡判定：端点高度 h1/h2 为海拔高度 (m)。"""
        t = np.linspace(0.0, 1.0, n)
        lon = lon1 + (lon2 - lon1) * t
        lat = lat1 + (lat2 - lat1) * t
        z = h1 + (h2 - h1) * t
        row, col = self._rc(lon, lat)
        nrow, ncol = self.elev.shape
        ri = np.clip(np.round(row).astype(int), 0, nrow - 1)
        ci = np.clip(np.round(col).astype(int), 0, ncol - 1)
        terr = self.elev[ri, ci]
        # 忽略端点附近（起降点本身在地面/近地面）
        inner = slice(3, n - 3)
        return bool(np.any(z[inner] < terr[inner] - 1e-9))


_DEM_CACHE: DEM | None = None


def get_dem() -> DEM:
    global _DEM_CACHE
    if _DEM_CACHE is None:
        _DEM_CACHE = DEM(os.path.join(GEO_DIR, "数字高程模型数据（DEM）", "镇龙乡及周边30米DEM.tif"))
    return _DEM_CACHE


# ---------------------------------------------------------------------------
# 平面距离
# ---------------------------------------------------------------------------
def haversine(lon1, lat1, lon2, lat2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def m_per_deg_lon(lat):
    return math.radians(1.0) * R_EARTH * math.cos(math.radians(lat))


def m_per_deg_lat():
    return math.radians(1.0) * R_EARTH


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------
@dataclass
class Scenario:
    center: dict
    areas: list
    types: dict
    fleet: list
    batteries: dict
    relay: dict
    relay_fleet: list
    relay_components: dict
    boxes: list
    comm: dict
    dem: DEM
    # 派生
    node_ground: dict = field(default_factory=dict)   # id -> 地面海拔
    node_xy: dict = field(default_factory=dict)       # id -> (lon, lat)
    cruise_alt: dict = field(default_factory=dict)    # (i,j) -> 巡航海拔
    seg_cache: dict = field(default_factory=dict)

    def area_ids(self):
        return [a["id"] for a in self.areas]


def build_scenario() -> Scenario:
    center = read_centers().iloc[0].to_dict()
    areas = read_service_areas().to_dict("records")
    types = {r["type_id"]: r for r in read_uav_types().to_dict("records")}
    fleet = read_uav_fleet().to_dict("records")
    bat = {r["type_id"]: r for r in read_transport_batteries().to_dict("records")}
    relay = read_relay_type()
    relay_fleet = read_relay_fleet().to_dict("records")
    rcomp = {r["type_id"]: r for r in read_relay_components().to_dict("records")}
    boxes = read_demand_boxes().to_dict("records")
    dem = get_dem()

    node_xy = {center["id"]: (center["lon"], center["lat"])}
    node_ground = {center["id"]: center["alt"]}
    for a in areas:
        node_xy[a["id"]] = (a["lon"], a["lat"])
        node_ground[a["id"]] = a["alt"]

    return Scenario(center=center, areas=areas, types=types, fleet=fleet,
                    batteries=bat, relay=relay, relay_fleet=relay_fleet,
                    relay_components=rcomp, boxes=boxes, comm=COMM, dem=dem,
                    node_ground=node_ground, node_xy=node_xy)


# ---------------------------------------------------------------------------
# 航段物理模型（附录 2）
# ---------------------------------------------------------------------------
def equivalent_range(t: dict, q: float) -> float:
    """机型 t 携带载荷 q 时的等效航程 L_g(q)，公式见附录 2。"""
    L0, LF, Q = t["range_empty"], t["range_full"], t["q_max"]
    if Q <= 0:
        return L0
    q = min(max(q, 0.0), Q)
    return L0 - (L0 - LF) * (q / Q) ** 1.5


def segment(seg_id, t: dict, q: float, h_mass: float | None = None):
    """返回航段字典：水平距离、爬升/下降高度、时间、能耗。

    seg_id: (i_id, j_id)；作业高度 O01=地面海拔, 服务区=地面海拔+30m。
    """
    return None  # 由 Scenario.segment 提供（需要 DEM）


def altitude_of(sc: Scenario, node_id: str) -> float:
    """作业高度：O01 取地面海拔；服务区取地面海拔以上 30 m。"""
    g = sc.node_ground[node_id]
    return g if node_id == sc.center["id"] else g + 30.0


def seg_geometry(sc: Scenario, i: str, j: str) -> dict:
    """航段几何：水平距离 dij、巡航海拔、爬升高度 hij+、下降高度 hij-。"""
    key = (i, j)
    if key in sc.seg_cache:
        return sc.seg_cache[key]
    lon1, lat1 = sc.node_xy[i]
    lon2, lat2 = sc.node_xy[j]
    d = haversine(lon1, lat1, lon2, lat2)
    ground_max = sc.dem.max_elev_profile(lon1, lat1, lon2, lat2)
    cruise = ground_max + 50.0
    h_up = altitude_of(sc, i)
    h_dn = altitude_of(sc, j)
    geom = {
        "d": d,
        "cruise_alt": cruise,
        "climb": max(cruise - h_up, 0.0),
        "descend": max(cruise - h_dn, 0.0),
    }
    sc.seg_cache[key] = geom
    return geom


def seg_time(sc: Scenario, t: dict, i: str, j: str) -> float:
    g = seg_geometry(sc, i, j)
    return (g["climb"] / t["v_climb"] + g["d"] / t["v_cruise"]
            + g["descend"] / t["v_descend"])


def seg_energy(sc: Scenario, t: dict, i: str, j: str, q: float) -> float:
    """航段能耗：水平航程能耗 + 爬升附加能耗，按等效航程线性折算。

    采用附录 2 给定的等效航程关系反推单位距离能耗：载荷 q 时等效航程 L(q) 对应
    满电可用能量 E_use，水平单位距离能耗 = E_use / L(q)。爬升附加能耗按势能/爬升效率折算。
    """
    g = seg_geometry(sc, i, j)
    L_q = equivalent_range(t, q)
    if L_q <= 0:
        return float("inf")
    e_hor = t["battery_energy"] * g["d"] / L_q
    m_total = t["mass_empty"] + q
    e_up = (m_total * 9.8 * g["climb"] / (3.6e6 * t["eta_climb"]))
    return e_hor + e_up


def mission_energy(sc: Scenario, t: dict, route: list, loads: dict) -> float:
    """架次总能耗：route 为节点序列 [O01, Sm, ..., O01]，loads[(i,j)] 为该段载荷。"""
    tot = 0.0
    for a, b in zip(route[:-1], route[1:]):
        tot += seg_energy(sc, t, a, b, loads.get((a, b), 0.0))
    return tot


# ---------------------------------------------------------------------------
# 通信链路（附录 3）
# ---------------------------------------------------------------------------
def link_max_loss(a_key: str, b_key: str) -> float:
    """双向链路门限 Lmax_{a<->b} = min(Lmax_{a->b}, Lmax_{b->a})。"""
    P = COMM
    th = P["P_sens"] + P["M_fade"]
    def one(src, dst):
        return (P[src]["Pt"] + P[src]["G"] + P[dst]["G"] - P["L_sys"] - th)
    return min(one(a_key, b_key), one(b_key, a_key))


def fspl(freq_mhz: float, d_km: float) -> float:
    return 32.45 + 20 * math.log10(freq_mhz) + 20 * math.log10(max(d_km, 1e-6))


def link_available(sc: Scenario, p1, p2, key1: str, key2: str) -> bool:
    """p1/p2 为 (lon, lat, alt_m)。"""
    blocked = sc.dem.los_blocked(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2])
    d3 = math.dist(p1, p2) if False else _d3(p1, p2)
    L = fspl(sc.comm["freq_mhz"], d3 / 1000.0) + (sc.comm["L_obs"] if blocked else 0.0)
    return L <= link_max_loss(key1, key2)


def _d3(p1, p2):
    """三维直线距离：水平用等距近似，垂直用海拔差。"""
    dh = haversine(p1[0], p1[1], p2[0], p2[1])
    dz = p2[2] - p1[2]
    return math.sqrt(dh * dh + dz * dz)


def gateway_point(sc: Scenario):
    c = sc.center
    return (c["lon"], c["lat"], c["alt"] + COMM["gateway"]["h"])


# ---------------------------------------------------------------------------
# 充电模型（附录 2）
# ---------------------------------------------------------------------------
def charge_time(soc: float, t_full: float) -> float:
    """两阶段等效充电模型：SOC=s 充至 100% 所需时间。"""
    s = min(max(soc, 0.0), 1.0)
    if s < 0.90:
        return t_full * (0.65 * (0.90 - s) / 0.90 + 0.35)
    return t_full * 0.35 * (1.0 - s) / 0.10


def remaining_soc(t: dict, energy_used: float) -> float:
    return max(0.0, 1.0 - energy_used / t["battery_energy"])


# ---------------------------------------------------------------------------
# 结果输出
# ---------------------------------------------------------------------------
def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=_json_default)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"not serializable: {type(o)}")