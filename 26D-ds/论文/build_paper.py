# -*- coding: utf-8 -*-
"""论文构建脚本：生成唯一结果源、回填附录数据表、内联附录代码。

运行：python 论文/build_paper.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
PAPER = os.path.join(ROOT, "论文")
MAIN = os.path.join(PAPER, "main.tex")
SKILL = os.environ.get("DSH_SKILL_HUAWEI") or os.path.join(
    os.environ.get("DSH_HOME", os.path.expanduser("~/.dsh")),
    "skills", "math-paper-huawei")

APPENDIX_FILES = [
    ("scripts/common_d.py", "论文/附录代码/common_d.py", "common_d"),
    ("数据预处理/eda.py", "论文/附录代码/eda.py", "eda"),
    ("Q1/solve_q1.py", "论文/附录代码/solve_q1.py", "solve_q1"),
    ("Q2/solve_q2.py", "论文/附录代码/solve_q2.py", "solve_q2"),
    ("Q3/solve_q3.py", "论文/附录代码/solve_q3.py", "solve_q3"),
    ("Q4/solve_q4.py", "论文/附录代码/solve_q4.py", "solve_q4"),
    ("灵敏度分析/sensitivity.py", "论文/附录代码/sensitivity.py", "sensitivity"),
]


def jload(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as fh:
        return json.load(fh)


def build_final_results():
    q1 = jload("q1_results.json")
    q2 = jload("q2_results.json")
    q3 = jload("q3_results.json")
    q4 = jload("q4_results.json")
    sens = jload("sensitivity_results.json")

    p1 = q1["最大安全载荷_kg"]
    base = q1["组批方案"]["N_E_T"]["totals"]
    eopt = q1["组批方案"]["E_N_T"]["totals"]
    q2m = q2["指标"]
    q2p = q2["方案集"]
    q3m = q3["指标"]
    a2 = q4["分区结果"]["2组"]["合计"]
    a3 = q4["分区结果"]["3组"]["合计"]

    results = {
        "问题一_最大安全载荷_A型最小值_kg": min(p1[a]["A"] for a in p1),
        "问题一_最大安全载荷_B型最小值_kg": round(min(p1[a]["B"] for a in p1), 2),
        "问题一_最大安全载荷_C型最小值_kg": round(min(p1[a]["C"] for a in p1), 2),
        "问题一_最少架次_结果_架次": base["N"],
        "问题一_总运输能耗_结果_kWh": round(base["E"], 3),
        "问题一_累计作业时间_结果_s": round(base["T"], 1),
        "问题一_最低能耗方案_结果_kWh": round(eopt["E"], 3),
        "问题一_最低能耗方案_架次": eopt["N"],
        "问题一_临界返航安全余量_结果": q1["临界返航余量"],
        "问题二_主方案_完成时间_结果_s": round(q2m["makespan"], 1),
        "问题二_主方案_运输能耗_结果_kWh": round(q2m["energy"], 3),
        "问题二_主方案_架次数_结果": q2m["n_sorties"],
        "问题二_主方案_加权总延误_结果": round(q2m["tardy"], 1),
        "问题二_首批超时_结果_s": round(q2m["first_violation"], 1),
        "问题二_及时性优先_完成时间_s": round(q2p["及时性优先"]["makespan"], 1),
        "问题二_完成时间优先_完成时间_s": round(q2p["完成时间优先"]["makespan"], 1),
        "问题三_通信缺口占比_结果": round(100.0 * 3536 / 9022, 2),
        "问题三_中继总能耗_结果_kWh": round(q3m["energy_relay"], 3),
        "问题三_联合总能耗_结果_kWh": round(q3m["energy_total"], 3),
        "问题三_联合完成时间_结果_s": round(q3m["makespan"], 1),
        "问题三_中继架次数_结果": q3m["n_sorties_relay"],
        "问题四_2组运输无人机需求_结果": a2["运输无人机"],
        "问题四_2组共享电池需求_结果": a2["共享电池"],
        "问题四_3组运输无人机需求_结果": a3["运输无人机"],
        "问题四_3组共享电池需求_结果": a3["共享电池"],
        "问题四_2组完成时间_结果_s": round(a2["完成时间"], 1),
        "问题四_3组完成时间_结果_s": round(a3["完成时间"], 1),
        "问题四_2组质量不均衡_结果": round(a2["质量不均衡"], 3),
        "问题四_3组质量不均衡_结果": round(a3["质量不均衡"], 3),
        "灵敏度_可行点最少架次_结果": sens["可行点架次数范围"][0],
        "灵敏度_可行点最多架次_结果": sens["可行点架次数范围"][1],
        "灵敏度_不可行点占比_结果": round(100.0 * sens["不可行点数"] / sens["网格总数"], 1),
    }
    ranges = {
        "问题一_最少架次": {"min": 1, "max": 200},
        "问题一_总运输能耗": {"min": 0.0, "max": 1000.0},
        "问题一_临界返航安全余量": {"min": 0.0, "max": 1.0},
        "问题二_主方案_完成时间": {"min": 0.0, "max": 200000.0},
        "问题三_联合总能耗": {"min": 0.0, "max": 1000.0},
        "问题四_2组运输无人机需求": {"min": 0, "max": 100},
        "灵敏度_不可行点占比": {"min": 0.0, "max": 100.0},
    }
    payload = {
        "schema": "mathmodel.final_results/v1",
        "note": "全文唯一结果源；论文正文、摘要、各问 result.md 与支撑材料只引用本文件的关键数值。",
        "results": results,
        "ranges": ranges,
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "final_results.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"final_results.json 写出 {len(results)} 个关键数值")
    return payload


def build_appendix_rows():
    q2 = jload("q2_results.json")
    q3 = jload("q3_results.json")
    q4 = jload("q4_results.json")
    rows2 = []
    for k, r in enumerate(sorted(q2["架次明细"], key=lambda x: x["start"]), 1):
        rows2.append(
            f"  {k} & {r['type_id']} & {r['uav']} & {'→'.join(r['route'])} & "
            f"{r['load_mass']:.1f} & {r['energy']:.3f} & {r['end']:.1f} \\\\")
    rows3 = []
    for h in q3["选中悬停"]:
        fl = h["flight"]
        rows3.append(
            f"  {h['tag']} & {h['lon']:.6f} & {h['lat']:.6f} & {h['hover_h']:.0f} & "
            f"{h['alt']:.1f} & {fl['t_flight']:.1f} \\\\")
    rows4 = []
    for key in ("2组", "3组"):
        for d in q4["分区结果"][key]["组明细"]:
            u = d["运输无人机需求"]
            b = d["共享电池需求"]
            rows4.append(
                f"  {key} & {d['组']} & {d['运输架次']} & "
                f"{u['A'] + u['B'] + u['C']} & {b['A'] + b['B'] + b['C']} & "
                f"{d['中继无人机需求']} & {d['中继能源组件需求']} \\\\")
    return rows2, rows3, rows4


def build_appendix_config():
    files = [{"source": s, "appendix": a} for s, a, _k in APPENDIX_FILES]
    runs = []
    for _s, a, key in APPENDIX_FILES:
        runs.append({
            "name": f"equivalence-{key}",
            "command": ["python", "scripts/verify_equivalence.py",
                        "--module", key,
                        "--out", f"检查结果/equivalence/{key}.json"],
            "cwd": ".",
            "files": [a],
            "outputs": [{"path": f"检查结果/equivalence/{key}.json", "type": "json"}],
            "timeout": 1800,
        })
    cfg = {
        "note": "附录 Python 代码等价净化副本的回归配置。",
        "tolerance": {"abs": 1e-9, "rel": 1e-9},
        "files": files,
        "runs": runs,
    }
    os.makedirs(os.path.join(ROOT, "检查结果"), exist_ok=True)
    with open(os.path.join(ROOT, "检查结果", "附录代码复核.json"), "w",
              encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
    print("附录代码复核.json 写出")


def run_appendix_tool():
    tool = os.path.join(SKILL, "scripts", "prepare_appendix_code.py")
    if not os.path.isfile(tool):
        raise SystemExit(f"未找到附录代码工具: {tool}")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run([sys.executable, tool, "--project", ROOT],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    print(proc.stdout.strip()[-2000:])
    if proc.returncode != 0:
        print(proc.stderr.strip()[-4000:])
        raise SystemExit(f"附录代码净化失败，退出码 {proc.returncode}")


def splice(rows2, rows3, rows4):
    with open(MAIN, encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("  APPQ2ROWS\n", "\n".join(rows2) + "\n")
    text = text.replace("  APPQ3ROWS\n", "\n".join(rows3) + "\n")
    text = text.replace("  APPQ4ROWS\n", "\n".join(rows4) + "\n")

    code_dir = os.path.join(PAPER, "附录代码")
    blocks = []
    for _s, _a, key in APPENDIX_FILES:
        name = f"{key}.py"
        path = os.path.join(code_dir, name)
        if not os.path.isfile(path):
            raise SystemExit(f"缺少净化副本: {path}")
        with open(path, encoding="utf-8") as fh:
            body = fh.read().rstrip("\n")
        texname = name.replace("_", "\\_")
        blocks.append(
            f"\\subsection{{{texname}}}\n\n"
            f"\\begin{{Python}}{{{texname}}}\n{body}\n\\end{{Python}}\n")
    text = text.replace("APPENDIXCODE\n", "\n".join(blocks))
    with open(MAIN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"main.tex 回填：附录表 {len(rows2)}/{len(rows3)}/{len(rows4)} 行，"
          f"代码块 {len(blocks)} 个")


def main() -> int:
    build_final_results()
    rows2, rows3, rows4 = build_appendix_rows()
    build_appendix_config()
    run_appendix_tool()
    splice(rows2, rows3, rows4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())