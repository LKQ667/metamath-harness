"""问题一：2024~2030 年确定情形下的最优种植方案求解。"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
YEAR_COUNT = int(os.environ.get("CROP_YEARS", "7"))
YEARS = tuple(range(2024, 2024 + YEAR_COUNT))
LIMIT = int(os.environ.get("CROP_TIME_LIMIT", "600"))
LIMIT = LIMIT if LIMIT > 0 else None
sys.path.insert(0, str(BASE / "共享"))

import cropmodel as cm
import envdata as ed


def tables(data):
    yld = {}
    cst = {}
    for item in data["plots"]:
        name = item["plot"]
        kind = item["kind"]
        for crop_id in data["crops"]:
            if not ed.season_of(kind, crop_id):
                continue
            yld[(crop_id, name)] = ed.yield_by_plot(data, crop_id, kind)
            cst[(crop_id, name)] = ed.cost_of(data, crop_id, kind)
    return yld, cst


def solve_case(data, yld, cst, discount, label):
    cfg = {
        "data": data,
        "yield": yld,
        "cost": cst,
        "price": {crop_id: record["mid"] for crop_id, record in data["price_by_crop"].items()},
        "cap": dict(data["demand"]),
        "pen": 0.0,
        "discount": discount,
        "risk": 0.0,
        "plot_limit": 10,
        "years": YEARS,
    }
    started = time.time()
    model = cm.build(cfg)
    result = cm.solve(model, time_limit=LIMIT, gap=0.01)
    rows = cm.plan_rows(model)
    sales = cm.sales_rows(model)
    info = cm.summary(model, result)
    info["label"] = label
    info["discount"] = discount
    timing = {"wall_time": round(time.time() - started, 2), "runtime": info.pop("runtime", 0.0)}
    info.pop("wall_time", None)
    info["loss_yuan"] = round(
        sum(row["surplus_jin"] * row["price_yuan"] for row in sales) * (1.0 - discount), 2
    )
    return {"summary": info, "plan": rows, "sales": sales, "detail": cm.audit(model), "timing": timing}


def write_plan(path, rows):
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=["plot", "kind", "crop_id", "crop", "season", "year", "area"])
    frame = frame[["plot", "crop_id", "crop", "season", "year", "area"]]
    wide = frame.pivot_table(
        index=["plot", "crop_id", "crop", "season"],
        columns="year",
        values="area",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    wide.to_excel(path, index=False, engine="openpyxl")
    return wide


def main():
    data = ed.load_all()
    yld, cst = tables(data)
    out = {}
    timings = {}
    for key, discount, label, order in (
        ("case1", 0.0, "情形一_超产滞销", 1),
        ("case2", 0.5, "情形二_超产降价百分之五十", 2),
    ):
        payload = solve_case(data, yld, cst, discount, label)
        out[key] = payload["summary"]
        timings[key] = payload["timing"]
        cm.dump(BASE / "Q1" / f"q1_plan_{key}.json", payload["plan"])
        cm.dump(BASE / "Q1" / f"q1_sales_{key}.json", payload["sales"])
        cm.dump(BASE / "Q1" / f"q1_audit_{key}.json", payload["detail"])
        write_plan(BASE / "Q1" / f"q1_result{order}.xlsx", payload["plan"])
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    cm.dump(BASE / "Q1" / "q1_metrics.json", out)
    cm.dump(BASE / "Q1" / "q1_timing.json", timings)


if __name__ == "__main__":
    main()
