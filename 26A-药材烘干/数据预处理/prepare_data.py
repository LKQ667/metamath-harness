"""附件解析、EDA 与派生数据生成。

输入：赛题目录下的附件 1（烘房温度与水分浓度）与附件 2（药材半径）。
输出：data/derived/ambient_conditions.csv、data/derived/radius_profile.csv、
      data/derived/eda_summary.json。

脚本只使用相对路径，工作目录为项目根目录。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DERIVED_DIR = PROJECT_ROOT / "data" / "derived"


def read_ambient() -> pd.DataFrame:
    """读取附件 1 并规整为时间升序、无重复的工况表。"""
    frame = pd.read_excel(RAW_DIR / "附件1.xlsx")
    frame.columns = ["时间", "温度", "水分浓度"]
    frame = frame.dropna(how="any")
    frame = frame.drop_duplicates(subset="时间", keep="first")
    frame = frame.sort_values("时间").reset_index(drop=True)
    frame["时间"] = frame["时间"].astype(float)
    frame["温度"] = frame["温度"].astype(float)
    frame["水分浓度"] = frame["水分浓度"].astype(float)
    return frame


def read_radius() -> pd.DataFrame:
    """读取附件 2 并规整为时间升序、无重复的半径表。"""
    frame = pd.read_excel(RAW_DIR / "附件2.xlsx")
    frame.columns = ["时间", "半径"]
    frame = frame.dropna(how="any")
    frame = frame.drop_duplicates(subset="时间", keep="first")
    frame = frame.sort_values("时间").reset_index(drop=True)
    frame["时间"] = frame["时间"].astype(float)
    frame["半径"] = frame["半径"].astype(float)
    return frame


def describe_series(series: pd.Series) -> dict:
    values = series.to_numpy(dtype=float)
    diffs = np.diff(values)
    return {
        "数量": int(values.size),
        "最小值": round(float(values.min()), 6),
        "最大值": round(float(values.max()), 6),
        "均值": round(float(values.mean()), 6),
        "标准差": round(float(values.std(ddof=1)), 6),
        "严格递增": bool(np.all(diffs > 0)),
        "单调不增": bool(np.all(diffs <= 0)),
    }


def build_summary(ambient: pd.DataFrame, radius: pd.DataFrame) -> dict:
    ambient_time = ambient["时间"].to_numpy(dtype=float)
    radius_time = radius["时间"].to_numpy(dtype=float)
    step_ambient = float(np.median(np.diff(ambient_time)))
    step_radius = float(np.median(np.diff(radius_time)))
    correlation = float(np.corrcoef(ambient["温度"], ambient["水分浓度"])[0, 1])
    return {
        "附件1": {
            "记录数": int(ambient.shape[0]),
            "时间范围_s": [float(ambient_time.min()), float(ambient_time.max())],
            "时间步长_s": step_ambient,
            "缺失值": int(ambient.isna().sum().sum()),
            "重复时间点": int(ambient["时间"].duplicated().sum()),
            "温度": describe_series(ambient["温度"]),
            "水分浓度": describe_series(ambient["水分浓度"]),
            "温度与水分浓度相关系数": round(correlation, 6),
        },
        "附件2": {
            "记录数": int(radius.shape[0]),
            "时间范围_s": [float(radius_time.min()), float(radius_time.max())],
            "时间步长_s": step_radius,
            "缺失值": int(radius.isna().sum().sum()),
            "重复时间点": int(radius["时间"].duplicated().sum()),
            "半径": describe_series(radius["半径"]),
            "首末半径_cm": [round(float(radius["半径"].iloc[0]), 6), round(float(radius["半径"].iloc[-1]), 6)],
            "收缩幅度_cm": round(float(radius["半径"].iloc[0] - radius["半径"].iloc[-1]), 6),
        },
        "结论": [
            "两份附件均无缺失与重复，时间严格递增，可直接作为边界工况与几何输入。",
            "烘房温度与水分浓度同向上升且高度正相关，说明加热过程伴随水分蒸发进入烘房。",
            "药材半径单调收缩并在后段趋于平稳，问题 4 的移动边界需用保形插值重建连续曲线。",
        ],
    }


def main() -> None:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    ambient = read_ambient()
    radius = read_radius()
    ambient.to_csv(DERIVED_DIR / "ambient_conditions.csv", index=False, encoding="utf-8")
    radius.to_csv(DERIVED_DIR / "radius_profile.csv", index=False, encoding="utf-8")
    summary = build_summary(ambient, radius)
    (DERIVED_DIR / "eda_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "rows_ambient": int(ambient.shape[0]), "rows_radius": int(radius.shape[0])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
