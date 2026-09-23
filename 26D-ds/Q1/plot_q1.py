# -*- coding: utf-8 -*-
"""问题一图表：载荷—返航余量响应、组批方案构成、三指标权衡前沿。

三张图均为单面板（panel_count=1），符合项目锁定的"禁用子图"策略。

运行：python Q1/plot_q1.py
输出：Q1/figures/fig_q1_*.{png,pdf,svg}
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402

from common_d import RESULTS_DIR, build_scenario  # noqa: E402
from solve_q1 import (  # noqa: E402
    build_caps, classify, max_safe_payload, solve_area,
)

FIGDIR = os.path.join(ROOT, "Q1", "figures")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def area_frontier(cats, counts, caps, n_cap):
    """返回 {N: (E, T)}：恰好用 N 个架次完成本服务区全部货箱时的最小 (E, T)。

    自底向上按架次层推进：第 n 层状态为"用 n 个架次后可剩余的数量向量"，
    层内按 (E, T) 字典序保留最优，故 zero 状态首次出现在第 N 层即为最少架次。
    """
    from solve_q1 import enumerate_patterns

    patterns = []
    for gid, cap in caps.items():
        for p in enumerate_patterns(cats, counts, cap["payload"], cap["volume"],
                                    cap["energy_of"], cap["time_of"]):
            patterns.append({**p, "type_id": gid})
    zero = tuple([0] * len(counts))
    layer = {tuple(counts): (0.0, 0.0)}
    out = {}
    for n in range(1, n_cap + 1):
        nxt_layer = {}
        for state, (e, t) in layer.items():
            for p in patterns:
                if any(p["vec"][k] > state[k] for k in range(len(state))):
                    continue
                ns = tuple(state[k] - p["vec"][k] for k in range(len(state)))
                cand = (e + p["energy"], t + p["time"])
                if ns not in nxt_layer or cand < nxt_layer[ns]:
                    nxt_layer[ns] = cand
        layer = nxt_layer
        if zero in layer:
            out[n] = layer[zero]
        if not layer:
            break
    return out


def combine_frontiers(frs):
    """把各服务区前沿按"总架次数"做背包式合并，返回 {N: (E, T)}。"""
    acc = {0: (0.0, 0.0)}
    for fr in frs:
        nxt = {}
        for n0, (e0, t0) in acc.items():
            for n1, (e1, t1) in fr.items():
                n = n0 + n1
                cand = (e0 + e1, t0 + t1)
                if n not in nxt or cand < nxt[n]:
                    nxt[n] = cand
        acc = nxt
    return acc


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from plot_common import (PALETTE, apply_py_nature_style, run_py_nature_qa,
                             save_py_nature_figure)
    from label_util import box_of_artist, place_labels

    os.makedirs(FIGDIR, exist_ok=True)
    apply_py_nature_style(font_size=8.0, profile="competition_cn")

    sc = build_scenario()
    areas = [a["id"] for a in sc.areas]
    by_area = {}
    for b in sc.boxes:
        by_area.setdefault(b["area_id"], []).append(b)
    cats, counts = {}, {}
    for a in areas:
        cats[a], counts[a] = classify(by_area[a])

    data = json.load(open(os.path.join(RESULTS_DIR, "q1_results.json"), encoding="utf-8"))
    sens = data["灵敏度_返航余量"]
    base = data["组批方案"]["N_E_T"]

    # 只在可行区间内绘制响应曲线
    feas = [r for r in sens if r.get("feasible")]
    rhos = np.array([r["rho"] for r in feas])
    colors = {"A": PALETTE["blue_main"], "B": PALETTE["teal_main"], "C": PALETTE["red_strong"]}

    # ---------------- 图3：最大安全载荷随返航安全余量变化 ----------------
    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    for gid in ("A", "B", "C"):
        arr = np.array([[r["payload"][gid][a] for a in areas] for r in feas])
        for j, a in enumerate(areas):
            ax.plot(rhos, arr[:, j], color=colors[gid], linewidth=0.5, alpha=0.30, zorder=3)
        ax.plot(rhos, arr.mean(axis=1), color=colors[gid], linewidth=1.9, zorder=5,
                marker="o", markersize=2.6, markevery=4,
                label=f"{gid} 型（15 区均值，细线为各服务区）")
        qmax = {"A": 25.0, "B": 30.0, "C": 80.0}[gid]
        ax.axhline(qmax, color=colors[gid], linewidth=0.7, linestyle=":", alpha=0.7, zorder=2)

    ax.axhline(14.0, color=PALETTE["neutral_dark"], linewidth=1.0, linestyle="--", zorder=4)
    ax.text(rhos[0] + 0.002, 15.2, "最重单箱 14 kg（饮用水）", fontsize=7.0,
            color=PALETTE["neutral_dark"], zorder=8)
    rho_crit = data.get("临界返航余量")
    if rho_crit:
        ax.axvline(rho_crit, color=PALETTE["orange_main"], linewidth=1.2,
                   linestyle="-.", zorder=4)
        ax.annotate(f"临界余量 ρ={rho_crit:.3f}\n超过后 S008 的 14 kg 货箱\n"
                    f"超出所有机型安全载荷",
                    xy=(rho_crit, 46), xytext=(rho_crit - 0.075, 52),
                    fontsize=6.8, color=PALETTE["orange_main"], zorder=9,
                    arrowprops=dict(arrowstyle="->", color=PALETTE["orange_main"],
                                    linewidth=0.9, shrinkA=0, shrinkB=2))
    ax.set_xlabel("返航安全余量比例 $\\rho$")
    ax.set_ylabel("最大安全载荷 $q^{*}$（kg）")
    ax.set_xlim(rhos[0], 0.40)
    ax.set_ylim(0, 88)
    ax.tick_params(labelsize=7)
    leg = ax.legend(loc="upper right", fontsize=7.0, handletextpad=0.5, borderpad=0.4)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q1_payload_rho"),
                             dpi=320, profile="competition_cn")
    print("图3 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q1_payload_rho"),
                                    profile="competition_cn").passed)

    # ---------------- 图4：组批方案机型构成（棒棒糖，不使用柱形 API） ----------------
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    order = sorted(areas, key=lambda a: -base["per_area"][a]["E"])
    ypos = np.arange(len(order))
    tot_e = np.array([base["per_area"][a]["E"] for a in order])
    seg_colors = {"A": PALETTE["blue_main"], "B": PALETTE["teal_main"],
                  "C": PALETTE["red_strong"]}
    # 灰色基线（架次总能耗）
    ax.hlines(ypos, 0, tot_e, color=PALETTE["neutral_mid"], linewidth=1.5, zorder=3)
    # 按机型分层画出各机型贡献的能耗区间
    lane = {"A": 0.19, "B": 0.0, "C": -0.19}
    for gid in ("A", "B", "C"):
        starts, ends = [], []
        for a in order:
            seg = [s for s in base["per_area"][a]["plan"] if s["type_id"] == gid]
            starts.append(sum(s["energy"] for s in seg))
            ends.append(sum(x["energy"] for x in base["per_area"][a]["plan"]))
        # 该机型贡献从"其他机型之和"到"总量"的区间
        others = [tot_e[i] - starts[i] for i in range(len(order))]
        for i in range(len(order)):
            if starts[i] <= 1e-9:
                continue
            ax.hlines(ypos[i] + lane[gid], others[i], tot_e[i], color=seg_colors[gid],
                      linewidth=3.0, zorder=5, capstyle="butt")
    # 棒棒糖端点
    for gid in ("A", "B", "C"):
        xs, ys = [], []
        for i, a in enumerate(order):
            if any(s["type_id"] == gid for s in base["per_area"][a]["plan"]):
                xs.append(tot_e[i])
                ys.append(ypos[i])
        ax.scatter(xs, ys, s=26, marker="o", facecolor="white",
                   edgecolor=PALETTE["black"], linewidths=0.8, zorder=7)
    for i, a in enumerate(order):
        ax.annotate(f"{base['per_area'][a]['N']} 架次", (tot_e[i], ypos[i]),
                    textcoords="offset points", xytext=(7, -2.6),
                    fontsize=6.6, color=PALETTE["black"], zorder=8)
    from matplotlib.lines import Line2D
    used = [g for g in ("A", "B", "C")
            if any(any(s["type_id"] == g for s in base["per_area"][a]["plan"]) for a in order)]
    handles = [Line2D([], [], color=seg_colors[g], linewidth=3.0, label=f"{g} 型架次")
               for g in used]
    handles.append(Line2D([], [], color=PALETTE["neutral_mid"], linewidth=1.5,
                          label="本区总能耗"))
    ax.set_yticks(ypos)
    ax.set_yticklabels(order, fontsize=7)
    ax.set_xlabel("本服务区单点往返总运输能耗（kWh）")
    ax.set_ylabel("服务区")
    ax.set_xlim(0, max(tot_e) * 1.20)
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.tick_params(labelsize=7)
    ax.legend(handles=handles, loc="upper right", fontsize=7.0,
              handletextpad=0.5, borderpad=0.4, ncol=2)
    ax.text(0.985, 0.60, "A 型未进入最优组批\n（载质量与装载体积\n均被 B 型支配）",
            transform=ax.transAxes, ha="right", va="top", fontsize=6.7,
            color=PALETTE["neutral_dark"], zorder=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=PALETTE["neutral_light"], linewidth=0.7))
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q1_batching"),
                             dpi=320, profile="competition_cn")
    print("图4 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q1_batching"),
                                    profile="competition_cn").passed)

    # ---------------- 图5：三指标权衡前沿 ----------------
    frs = []
    for a in areas:
        caps = build_caps(sc, a, data["最大安全载荷_kg"][a])
        n_min = base["per_area"][a]["N"]
        frs.append(area_frontier(cats[a], counts[a], caps, n_min + 6))
    glob = combine_frontiers(frs)
    allN = sorted(glob)
    n_lo, n_hi = allN[0], min(allN[0] + 12, allN[-1])
    Ns = [n for n in allN if n_lo <= n <= n_hi]
    Es = [glob[n][0] for n in Ns]
    Ts = [glob[n][1] for n in Ns]
    # 真实 Pareto 集：在 (N, E, T) 上互不支配的解
    pareto = []
    for n in allN:
        e, t = glob[n]
        if not any((m <= n and glob[m][0] <= e and glob[m][1] <= t
                    and (m, glob[m][0], glob[m][1]) != (n, e, t)) for m in allN):
            pareto.append(n)
    print("  决策窗口内前沿点 (N, E, T):")
    for n in Ns:
        mark = "  ←Pareto" if n in pareto else ""
        print(f"    N={n:3d}  E={glob[n][0]:8.3f} kWh  T={glob[n][1]:9.1f} s{mark}")
    print(f"  真实 Pareto 架次数集合: {pareto}")

    fig, ax = plt.subplots(figsize=(6.6, 4.5))
    dom_from = max(pareto) + 1
    ax.axvspan(dom_from - 0.5, n_hi + 0.5, color=PALETTE["neutral_light"],
               alpha=0.42, zorder=1)
    ax.text((dom_from + n_hi) / 2, max(Es) * 0.995,
            "受支配区：架次更多且能耗与\n作业时间均不优于前沿解",
            fontsize=6.8, color=PALETTE["neutral_dark"], ha="center", va="top", zorder=8)
    ax.plot(Ns, Es, color=PALETTE["blue_main"], linewidth=1.9, marker="o",
            markersize=4.2, markerfacecolor="white", markeredgewidth=1.1,
            zorder=5, label="总运输能耗（左轴）")
    ax.scatter([n for n in Ns if n in pareto], [glob[n][0] for n in Ns if n in pareto],
               s=58, marker="D", facecolor=PALETTE["gold_main"], edgecolor=PALETTE["black"],
               linewidths=0.8, zorder=9, label="Pareto 最优解")
    ax.set_xlabel("往返架次数 $N$（架次）")
    ax.set_ylabel("总运输能耗 $E$（kWh）", color=PALETTE["blue_main"])
    ax.tick_params(axis="y", labelcolor=PALETTE["blue_main"], labelsize=7)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_xticks(Ns)

    ax2 = ax.twinx()
    ax2.plot(Ns, Ts, color=PALETTE["orange_main"], linewidth=1.9, linestyle="--",
             marker="s", markersize=3.8, markerfacecolor="white", markeredgewidth=1.1,
             zorder=4, label="累计作业时间（右轴）")
    ax2.set_ylabel("累计作业时间 $T$（s）", color=PALETTE["orange_main"])
    ax2.tick_params(axis="y", labelcolor=PALETTE["orange_main"], labelsize=7)
    ax2.spines["right"].set_visible(True)

    kmin = int(np.argmin(Es))
    ax.text(0.025, 0.965,
            "Pareto 最优解\n"
            f"$N$={Ns[0]}：$E$={Es[0]:.3f} kWh，$T$={Ts[0]:.1f} s\n"
            f"$N$={Ns[kmin]}：$E$={Es[kmin]:.3f} kWh，$T$={Ts[kmin]:.1f} s\n"
            "增加 1 个架次换取 0.098 kWh 节能",
            transform=ax.transAxes, ha="left", va="top", fontsize=6.9,
            color=PALETTE["black"], zorder=10,
            bbox=dict(boxstyle="round,pad=0.34", facecolor="white",
                      edgecolor=PALETTE["gold_main"], linewidth=0.9))
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower right", fontsize=7.0,
              handletextpad=0.5, borderpad=0.4)
    ax.margins(x=0.05)
    p = save_py_nature_figure(fig, os.path.join(FIGDIR, "fig_q1_tradeoff"),
                             dpi=320, profile="competition_cn")
    print("图5 QA:", run_py_nature_qa(os.path.join(FIGDIR, "fig_q1_tradeoff"),
                                    profile="competition_cn").passed)

    json.dump({"frontier": [{"N": int(n), "E": float(e), "T": float(t)}
                            for n, e, t in zip(Ns, Es, Ts)]},
              open(os.path.join(RESULTS_DIR, "q1_frontier.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())