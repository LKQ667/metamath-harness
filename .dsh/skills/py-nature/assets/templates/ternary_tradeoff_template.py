from __future__ import annotations

import argparse
import sys
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from py_nature_core import apply_py_nature_style, save_py_nature_figure

_parser = argparse.ArgumentParser()
_parser.add_argument("--output-dir", default=".")
_args, _unknown = _parser.parse_known_args()
apply_py_nature_style(profile="competition_cn")
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import matplotlib.path as mpath
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import os

# -------------------------------------------------------------
# 1. 学术排版与字体设置
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['axes.linewidth'] = 1.2

# 顶刊经典色卡: 深紫青绿渐变 (匹配原图 1:1)
colors = [
    (0.00, '#210b39'),  # 0.0: 深暗紫
    (0.12, '#2f1958'),  # 0.12: 靛青紫
    (0.25, '#233d7b'),  # 0.25: 深宝蓝
    (0.40, '#1c6d9d'),  # 0.4: 蔚蓝
    (0.55, '#2ba4a7'),  # 0.55: 青绿
    (0.70, '#5dc5a0'),  # 0.7: 薄荷绿
    (0.85, '#a4dfa4'),  # 0.85: 浅葱绿
    (1.00, '#e5f6b8')   # 1.0: 淡柠檬黄绿
]
cmap = LinearSegmentedColormap.from_list('ternary_academic', [(p, c) for p, c in colors], N=256)

# -------------------------------------------------------------
# 2. 三元坐标投影数学转换
# -------------------------------------------------------------
# A (Top): Cost weight (1, 0, 0)
# B (Bottom-Left): Efficiency weight (0, 1, 0)
# C (Bottom-Right): Reliability weight (0, 0, 1)
def ternary_to_cartesian(a, b, c):
    total = a + b + c
    a, b, c = a / total, b / total, c / total
    x = c + 0.5 * a
    y = (np.sqrt(3) / 2.0) * a
    return x, y

# -------------------------------------------------------------
# 3. 构造网格与多目标综合效用流形
# -------------------------------------------------------------
n_grid = 400
coords = []
for i in range(n_grid + 1):
    for j in range(n_grid + 1 - i):
        k = n_grid - i - j
        coords.append((i / n_grid, j / n_grid, k / n_grid))
coords = np.array(coords)
a, b, c = coords[:, 0], coords[:, 1], coords[:, 2]
x_mesh, y_mesh = ternary_to_cartesian(a, b, c)

# 构造符合顶刊原图等高线形态的综合效用函数
# 最优平衡点位于 (a=0.33, b=0.28, c=0.39)
a0, b0, c0 = 0.33, 0.28, 0.39
d1 = (a - a0)**2 / 0.08 + (b - b0)**2 / 0.07 + (c - c0)**2 / 0.075
d2 = (a - 0.7)**2 / 0.15 + (b - 0.15)**2 / 0.2 + (c - 0.15)**2 / 0.2
score = 1.0 * np.exp(-d1 * 2.2) + 0.35 * np.exp(-d2 * 3.0) + 0.05 * (a + 0.5 * c)
score = (score - score.min()) / (score.max() - score.min())
score = np.clip(score, 0.0, 1.0)

# 三角网格剖分
triang = tri.Triangulation(x_mesh, y_mesh)

# -------------------------------------------------------------
# 4. 绘图与渲染
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.8, 8.8), dpi=300)
ax.set_aspect('equal')

# 正三角形裁剪区域
triangle_verts = [(0.0, 0.0), (1.0, 0.0), (0.5, np.sqrt(3) / 2.0), (0.0, 0.0)]
triangle_path = mpath.Path(triangle_verts)
clip_patch = mpatches.PathPatch(triangle_path, transform=ax.transData, facecolor='none', edgecolor='none')
ax.add_patch(clip_patch)

# 绘制等高线填充与等高线边线
levels = np.linspace(0.0, 1.0, 51)
contourf = ax.tricontourf(triang, score, levels=levels, cmap=cmap, extend='neither')
contourf.set_clip_path(clip_patch)

contour_lines = ax.tricontour(triang, score, levels=np.linspace(0.08, 0.95, 18),
                             colors='#1a334f', linewidths=0.5, alpha=0.55)
contour_lines.set_clip_path(clip_patch)

# 绘制内部三元网格虚线
grid_vals = [0.2, 0.4, 0.6, 0.8]
for v in grid_vals:
    # 恒定 a (平行底边)
    x1, y1 = ternary_to_cartesian(v, 1.0 - v, 0.0)
    x2, y2 = ternary_to_cartesian(v, 0.0, 1.0 - v)
    ax.plot([x1, x2], [y1, y2], color='#8898a6', linestyle='--', linewidth=0.6, alpha=0.6)

    # 恒定 b
    x1, y1 = ternary_to_cartesian(1.0 - v, v, 0.0)
    x2, y2 = ternary_to_cartesian(0.0, v, 1.0 - v)
    ax.plot([x1, x2], [y1, y2], color='#8898a6', linestyle='--', linewidth=0.6, alpha=0.6)

    # 恒定 c
    x1, y1 = ternary_to_cartesian(1.0 - v, 0.0, v)
    x2, y2 = ternary_to_cartesian(0.0, 1.0 - v, v)
    ax.plot([x1, x2], [y1, y2], color='#8898a6', linestyle='--', linewidth=0.6, alpha=0.6)

# 黑色三角形边框
ax.plot([0, 1, 0.5, 0], [0, 0, np.sqrt(3)/2, 0], color='black', linewidth=1.5, zorder=10)

# 刻度线与刻度标注 (严格匹配原图刻度位置)
tick_len = 0.016
# 底边刻度: 0.2, 0.4, 0.6, 0.8
for v in [0.2, 0.4, 0.6, 0.8]:
    xb, yb = v, 0.0
    ax.plot([xb, xb], [yb, yb - tick_len], color='black', linewidth=1.2, zorder=11)
    ax.text(xb, -0.045, f'{v:.1f}', ha='center', va='top', fontsize=12, fontfamily='sans-serif')

# 右斜边刻度: 0.2, 0.4, 0.6, 0.8
for v in [0.2, 0.4, 0.6, 0.8]:
    xr, yr = ternary_to_cartesian(1.0 - v, 0.0, v)
    dx, dy = tick_len * np.sqrt(3)/2, tick_len * 0.5
    ax.plot([xr, xr + dx], [yr, yr + dy], color='black', linewidth=1.2, zorder=11)
    ax.text(xr + 2.0 * dx, yr + 1.8 * dy, f'{v:.1f}', ha='left', va='center', fontsize=12, fontfamily='sans-serif')

# 左斜边刻度: 0.4, 0.6, 0.8 (原图中左侧标注 0.4, 0.6, 0.8)
for v in [0.4, 0.6, 0.8]:
    xl, yl = ternary_to_cartesian(v, 1.0 - v, 0.0)
    dx_l, dy_l = -tick_len * np.sqrt(3)/2, tick_len * 0.5
    ax.plot([xl, xl + dx_l], [yl, yl + dy_l], color='black', linewidth=1.2, zorder=11)
    ax.text(xl + 1.8 * dx_l, yl + 1.8 * dy_l, f'{v:.1f}', ha='right', va='center', fontsize=12, fontfamily='sans-serif')

# 顶点黑色圆点
ax.scatter([0.5, 0.0, 1.0], [np.sqrt(3)/2, 0.0, 0.0], color='black', s=45, zorder=12)

# 顶点标注
ax.text(0.5, np.sqrt(3)/2 + 0.065, 'Cost weight\n(1, 0, 0)', ha='center', va='bottom', fontsize=14, fontfamily='sans-serif')
ax.text(-0.02, -0.075, '(0, 1, 0)\nEfficiency weight', ha='center', va='top', fontsize=14, fontfamily='sans-serif')
ax.text(0.98, -0.075, '(0, 0, 1)\nReliability weight', ha='center', va='top', fontsize=14, fontfamily='sans-serif')

# -------------------------------------------------------------
# 5. 候选样本散点与最佳折中点 (Best compromise)
# -------------------------------------------------------------
np.random.seed(101)
# 在整个三元空间中均匀及集中采样点
pts = []
while len(pts) < 45:
    p = np.random.exponential(scale=1.0, size=3)
    p = p / p.sum()
    pts.append(p)
pts = np.array(pts)
sx, sy = ternary_to_cartesian(pts[:, 0], pts[:, 1], pts[:, 2])

ax.scatter(sx, sy, s=32, facecolor='#d6edf7', edgecolor='#1d2b38', linewidth=0.8, zorder=15, alpha=0.95)

# 最佳折中点 (黄色五角星)
bx, by = ternary_to_cartesian(a0, b0, c0)
ax.scatter(bx, by, marker='*', s=230, facecolor='#f8b32b', edgecolor='black', linewidth=1.2, zorder=20)
ax.text(bx + 0.022, by, 'Best compromise', ha='left', va='center', fontsize=11, fontfamily='sans-serif', zorder=20)

# -------------------------------------------------------------
# 6. 排版与独立颜色条
# -------------------------------------------------------------
ax.set_xlim(-0.16, 1.16)
ax.set_ylim(-0.16, 1.02)
ax.axis('off')

# 调整颜色条位置避免重叠
cbar_ax = fig.add_axes([0.89, 0.14, 0.028, 0.72])
cbar = fig.colorbar(contourf, cax=cbar_ax, ticks=np.linspace(0.0, 1.0, 6))
cbar.ax.tick_params(labelsize=12, width=1.0, length=4)
cbar.set_label('Composite score', fontsize=13, fontfamily='sans-serif', labelpad=10)
for spine in cbar.ax.spines.values():
    spine.set_linewidth(1.0)

save_py_nature_figure(fig, FilePath(_args.output_dir) / "ternary_tradeoff_template")



