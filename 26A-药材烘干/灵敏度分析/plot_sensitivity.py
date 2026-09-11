"""灵敏度分析：关键参数对烘干时间的影响。

参数：对流传质系数 h_m、扩散系数整体倍数、对流换热系数 h、初始含水率 C0、烘房温度水平。
输出：tornado 图、二维响应热图与灵敏度数值结果。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ambient import ambient_functions, load_ambient  # noqa: E402
from drying_model import Properties, solve_cylinder  # noqa: E402
from plot_common import export, palette, prepare_style  # noqa: E402

FIG_DIR = PROJECT_ROOT / "灵敏度分析" / "figures"
OUT_DIR = PROJECT_ROOT / "灵敏度分析"
CMAP_TIME = LinearSegmentedColormap.from_list("timeseq", ["#F4F8FC", "#BBD6EC", "#5C93C6", "#2A5F9E", "#0F3D74"])

BASE_DT = 20.0
TARGET = 0.15
MAX_DAYS = 60.0


def make_props(scale_d: float = 1.0) -> Properties:
    def rho(c, t):
        return 650.0 + 128.0 * c

    def cp(c, t):
        return 1450.0 + 2736.0 * c / (c + 1.0)

    def k(c, t):
        return 0.21 + 0.38 * c / (c + 1.0)

    def d(c, t):
        tk = t + 273.15
        return scale_d * 2.4e-3 * np.exp(-0.45 / np.maximum(c, 1e-6)) * np.exp(-3850.0 / tk)

    return Properties(rho=rho, cp=cp, k=k, d=d)


def drying_time(
    h_m: float = 8e-7,
    h: float = 25.0,
    scale_d: float = 1.0,
    c0: float = 2.55,
    temp_offset: float = 0.0,
    dt: float = BASE_DT,
) -> float:
    t_air, c_air = ambient_functions()

    def t_air_shifted(t: float) -> float:
        return t_air(t) + temp_offset

    result = solve_cylinder(
        props=make_props(scale_d),
        radius=0.02,
        t_end=MAX_DAYS * 24 * 3600.0,
        dt=dt,
        n_cells=200,
        t_initial=28.0,
        c_initial=c0,
        t_air=t_air_shifted,
        c_air=c_air,
        h=h,
        h_m=h_m,
        record_every=1,
        stop_moisture=TARGET,
        keep_index=np.array([0]),
    )
    return float(result.meta["stop_time_s"]) / 3600.0


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    cache = OUT_DIR / "sensitivity_results.json"
    if cache.exists():
        payload = json.loads(cache.read_text(encoding="utf-8"))
        base = payload["基准烘干时间_h"]
        detail = payload["扰动设置"]
        grid = np.array(payload["网格"]["h_m_倍数"], dtype=float)
        matrix = np.array(payload["网格"]["烘干时间_h"], dtype=float)
        labels = [item["参数"] for item in detail]
        lows = [item["下界烘干时间_h"] for item in detail]
        highs = [item["上界烘干时间_h"] for item in detail]
    else:
        base = drying_time()
        specs = [
            ("对流传质系数 $h_m$", 0.8, 1.2, {"h_m": (8e-7 * 0.8, 8e-7 * 1.2)}),
            ("扩散系数倍数", 0.8, 1.2, {"scale_d": (0.8, 1.2)}),
            ("对流换热系数 $h$", 0.8, 1.2, {"h": (20.0, 30.0)}),
            ("初始含水率 $C_0$", 0.9, 1.1, {"c0": (2.295, 2.805)}),
            ("烘房温度偏移", -2.0, 2.0, {"temp_offset": (-2.0, 2.0)}),
        ]
        labels = []
        lows = []
        highs = []
        detail = []
        for label, low_factor, high_factor, kwargs in specs:
            low_value = drying_time(**{list(kwargs.keys())[0]: kwargs[list(kwargs.keys())[0]][0]})
            high_value = drying_time(**{list(kwargs.keys())[0]: kwargs[list(kwargs.keys())[0]][1]})
            labels.append(label)
            lows.append(low_value)
            highs.append(high_value)
            detail.append(
                {
                    "参数": label,
                    "下界取值": round(float(low_factor), 4),
                    "上界取值": round(float(high_factor), 4),
                    "下界烘干时间_h": round(low_value, 4),
                    "上界烘干时间_h": round(high_value, 4),
                    "影响幅度_h": round(abs(high_value - low_value), 4),
                }
            )

        grid = np.linspace(0.7, 1.3, 13)
        matrix = np.zeros((grid.size, grid.size))
        for i, hm_scale in enumerate(grid):
            for j, d_scale in enumerate(grid):
                matrix[i, j] = drying_time(h_m=8e-7 * hm_scale, scale_d=d_scale)

        payload = {
            "基准烘干时间_h": round(base, 4),
            "扰动设置": detail,
            "参数排序": sorted(detail, key=lambda item: item["影响幅度_h"], reverse=True),
            "网格": {
                "h_m_倍数": [round(float(v), 3) for v in grid],
                "扩散系数倍数": [round(float(v), 3) for v in grid],
                "烘干时间_h": [[round(float(v), 3) for v in row] for row in matrix],
            },
        }
        cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    colors = palette()
    prepare_style(font_size=8.5)

    order = np.argsort([abs(highs[i] - lows[i]) for i in range(len(labels))])
    fig = plt.figure(figsize=(183 / 25.4, 74 / 25.4))
    ax = fig.add_subplot(111)
    y = np.arange(len(order))
    for pos, idx in enumerate(order):
        left = min(lows[idx], highs[idx])
        right = max(lows[idx], highs[idx])
        ax.hlines(pos, left, right, color=colors["blue_main"], lw=6.0, alpha=0.85)
        ax.scatter([lows[idx], highs[idx]], [pos, pos], s=26, color=colors["blue_main"], zorder=3)
    ax.axvline(base, color=colors["red_strong"], lw=1.2, ls="--", label=f"基准工况 {base:.1f} h")
    ax.set_yticks(y)
    ax.set_yticklabels([labels[i] for i in order])
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.legend(fontsize=8, loc="lower left")
    ax.set_xlabel("烘干所需时间 / h")
    ax.set_title("参数 ±20% 扰动下的烘干时间变化", fontsize=9.4, pad=10)
    export(fig, FIG_DIR / "fig_sensitivity_tornado")

    fig = plt.figure(figsize=(183 / 25.4, 78 / 25.4))
    ax = fig.add_subplot(111)
    mesh = ax.pcolormesh(grid, grid, matrix, cmap=CMAP_TIME, shading="gouraud", rasterized=True)
    levels = np.linspace(float(matrix.min()), float(matrix.max()), 9)[1:-1]
    cs = ax.contour(grid, grid, matrix, levels=levels, colors="#FFFFFF", linewidths=0.6, alpha=0.8)
    ax.clabel(cs, inline=True, fontsize=6.6, fmt="%.1f")
    ax.scatter([1.0], [1.0], marker="*", s=150, color=colors["red_strong"], zorder=5)
    ax.annotate(
        f"基准工况 {base:.1f} h",
        xy=(1.0, 1.0),
        xytext=(12, 16),
        textcoords="offset points",
        fontsize=8.4,
        color=colors["red_strong"],
        arrowprops=dict(arrowstyle="->", color=colors["red_strong"], lw=0.9),
    )
    bar = fig.colorbar(mesh, ax=ax, pad=0.02)
    bar.set_label("烘干所需时间 / h", fontsize=8.5)
    bar.ax.tick_params(labelsize=7.5)
    ax.set_xlabel("对流传质系数 $h_m$ 的倍数")
    ax.set_ylabel("扩散系数 $D$ 的倍数")
    ax.set_title("烘干时间对扩散系数与传质系数的二维响应", fontsize=9.4, pad=8)
    export(fig, FIG_DIR / "fig_sensitivity_heatmap")

    print(json.dumps({"ok": True, "base_h": base, "worst": payload["参数排序"][0]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
