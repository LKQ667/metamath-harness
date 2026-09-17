"""灵敏度分析：关键参数扰动对七年利润与种植结构的影响。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "共享"))

import cropmodel as cm
import envdata as ed

YEAR_COUNT = int(os.environ.get("CROP_YEARS", "7"))
YEARS = tuple(range(2024, 2024 + YEAR_COUNT))
LIMIT = int(os.environ.get("CROP_TIME_LIMIT", "180"))
LIMIT = LIMIT if LIMIT > 0 else None
LEVELS = (-0.2, 0.0, 0.2) if os.environ.get("CROP_FAST") == "1" else (-0.2, -0.1, 0.0, 0.1, 0.2)
FACTORS = ("yield", "cost", "price", "demand")


def tables(data):
    yld = {}
    cst = {}
    for item in data["plots"]:
        for crop_id in data["crops"]:
            if not ed.season_of(item["kind"], crop_id):
                continue
            yld[(crop_id, item["plot"])] = ed.yield_by_plot(data, crop_id, item["kind"])
            cst[(crop_id, item["plot"])] = ed.cost_of(data, crop_id, item["kind"])
    return yld, cst


def scaled_table(factor, level, crops, years):
    table = {factor: {}}
    for year in years:
        table[factor][year] = {crop_id: 1.0 + level for crop_id in crops}
    return table


def run(data, yld, cst, factor, level):
    coef = scaled_table(factor, level, sorted(data["crops"]), YEARS) if level else {}
    cfg = {
        "data": data,
        "yield": yld,
        "cost": cst,
        "price": {crop_id: record["mid"] for crop_id, record in data["price_by_crop"].items()},
        "cap": dict(data["demand"]),
        "pen": 1.0,
        "discount": 0.5,
        "coef": coef,
        "risk": 0.0,
        "plot_limit": 10,
    }
    model = cm.build(cfg)
    result = cm.solve(model, time_limit=LIMIT, gap=0.02)
    info = cm.summary(model, result)
    rows = cm.plan_rows(model)
    families = {}
    crops_table = {int(k): v for k, v in pd_read_crops().items()}
    for row in rows:
        name = crops_table.get(row["crop_id"], "粮食")
        families[name] = families.get(name, 0.0) + row["area"]
    total = sum(families.values()) or 1.0
    return {
        "factor": factor,
        "level": level,
        "profit": info["profit_value_yuan"],
        "plant_area": info["plant_area"],
        "crop_count": info["crop_count"],
        "status": info["status"],
        "share": {key: round(value / total, 4) for key, value in families.items()},
    }


def pd_read_crops():
    import csv

    with (BASE / "data" / "派生" / "crops.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["crop_id"]: row["family"] for row in csv.DictReader(handle)}


def main():
    data = ed.load_all()
    yld, cst = tables(data)
    out = {"levels": list(LEVELS), "factors": list(FACTORS), "cases": []}
    for factor in FACTORS:
        for level in LEVELS:
            item = run(data, yld, cst, factor, level)
            out["cases"].append(item)
            print(json.dumps(item, ensure_ascii=False))
    base_profit = next(item["profit"] for item in out["cases"] if item["level"] == 0.0 and item["factor"] == "yield")
    out["base_profit"] = base_profit
    cm.dump(BASE / "灵敏度分析" / "sensitivity_metrics.json", out)
    print("sensitivity done", base_profit)


if __name__ == "__main__":
    main()
