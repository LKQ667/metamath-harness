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
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import os

# -------------------------------------------------------------
# 1. 学术排版与字体配置
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['axes.linewidth'] = 1.0

fig, ax = plt.subplots(figsize=(10.0, 7.8), dpi=300)

# -------------------------------------------------------------
# 2. 目标函数与等高线网格构造
# -------------------------------------------------------------
# min f(x1, x2) = (x1 - 1.5)^2 + (x2 + 1.5)^2
x1_vals = np.linspace(-3.0, 4.0, 350)
x2_vals = np.linspace(-3.0, 3.0, 350)
X1, X2 = np.meshgrid(x1_vals, x2_vals)

Z = (X1 - 1.5)**2 + (X2 + 1.5)**2

# 目标函数等高线填充与色卡 (Viridis)
cmap_obj = plt.cm.viridis
levels = np.linspace(0, 20, 51)
cf = ax.contourf(X1, X2, Z, levels=levels, cmap=cmap_obj, alpha=0.92, extend='neither', zorder=1)
cl = ax.contour(X1, X2, Z, levels=np.linspace(1, 19, 19), colors='#1a2a3a', linewidths=0.35, alpha=0.45, zorder=2)

# -------------------------------------------------------------
# 3. 约束条件与可行域/不可行域着色
# -------------------------------------------------------------
# 约束 1: x1^2 + x2^2 <= 4
c1 = (X1**2 + X2**2 <= 4.0)
# 约束 2: x2 >= 0.5 * x1 - 1.0
c2 = (X2 >= 0.5 * X1 - 1.0)
# 约束 3: x1 + 2 * x2 <= 3.0
c3 = (X1 + 2.0 * X2 <= 3.0)
# 约束 4: (x1 - 1)^2 + (x2 + 1)^2 >= 1.0
c4 = ((X1 - 1.0)**2 + (X2 + 1.0)**2 >= 1.0)

feasible_mask = c1 & c2 & c3 & c4
infeasible_mask = ~feasible_mask

# 可行域覆膜: 浅绿透明度
ax.contourf(X1, X2, feasible_mask.astype(float), levels=[0.5, 1.5],
            colors=['#a1d99b'], alpha=0.34, zorder=3)

# 不可行域覆膜: 浅红/淡桃粉透明度
ax.contourf(X1, X2, infeasible_mask.astype(float), levels=[0.5, 1.5],
            colors=['#fcbba1'], alpha=0.28, zorder=3)

# -------------------------------------------------------------
# 4. 绘制约束边界线条
# -------------------------------------------------------------
# 约束 1: 圆 x1^2 + x2^2 = 4 (黑色实线)
theta = np.linspace(0, 2*np.pi, 300)
ax.plot(2.0 * np.cos(theta), 2.0 * np.sin(theta), color='black', linewidth=1.6, zorder=5)

# 约束 2: x2 = 0.5 * x1 - 1.0 (蓝色虚线)
x_line = np.linspace(-3.0, 4.0, 200)
ax.plot(x_line, 0.5 * x_line - 1.0, color='#0022ff', linestyle='--', linewidth=1.6, zorder=5)

# 约束 3: x1 + 2 * x2 = 3.0 (红色点划线)
ax.plot(x_line, 0.5 * (3.0 - x_line), color='#ff0000', linestyle='-.', linewidth=1.6, zorder=5)

# 约束 4: 禁区圆 (x1 - 1)^2 + (x2 + 1)^2 = 1.0 (紫色点线)
ax.plot(1.0 + 1.0 * np.cos(theta), -1.0 + 1.0 * np.sin(theta), color='#800080', linestyle=':', linewidth=1.8, zorder=5)

# -------------------------------------------------------------
# 5. 绘制优化迭代轨迹
# -------------------------------------------------------------
traj_pts = np.array([
    [-1.85, 0.74],    # Starting point
    [-1.40, 0.43],    # Intermediate 1
    [-0.85, 0.05],    # Intermediate 2
    [-0.30, 0.05],    # Local optimum
    [0.05, -0.25],    # Intermediate 3
    [0.25, -0.50],    # Intermediate 4
    [0.40, -0.85],    # Intermediate 5
    [0.60, -1.15],    # Intermediate 6
    [1.05, -1.30],    # Intermediate 7
    [1.65, -1.42]     # Global optimum
])

for i in range(len(traj_pts) - 1):
    p1 = traj_pts[i]
    p2 = traj_pts[i+1]
    ax.annotate('', xy=(p2[0], p2[1]), xytext=(p1[0], p1[1]),
                arrowprops=dict(arrowstyle='->', color='black', lw=1.5, shrinkA=3, shrinkB=3), zorder=8)

ax.scatter(traj_pts[1:-1, 0], traj_pts[1:-1, 1], s=38, facecolor='white', edgecolor='black', linewidth=1.2, zorder=9)
ax.scatter([traj_pts[0, 0]], [traj_pts[0, 1]], s=65, facecolor='#ff0000', edgecolor='black', linewidth=1.2, zorder=10)
ax.scatter([traj_pts[3, 0]], [traj_pts[3, 1]], s=65, facecolor='#ff9900', edgecolor='black', linewidth=1.2, zorder=10)
ax.scatter([traj_pts[-1, 0]], [traj_pts[-1, 1]], s=65, facecolor='#00cc00', edgecolor='black', linewidth=1.2, zorder=10)

# -------------------------------------------------------------
# 6. 文字标注与指示引线
# -------------------------------------------------------------
# Starting point
ax.annotate('Initial point\n($-2.0, 2.0$)', xy=(traj_pts[0, 0], traj_pts[0, 1]), xytext=(-1.7, 1.15),
            fontsize=10, fontfamily='sans-serif', ha='center',
            arrowprops=dict(arrowstyle='->', color='black', lw=0.9), zorder=12)

# Local optimum
ax.annotate('Local optimum\n($-0.3, 0.1$)', xy=(traj_pts[3, 0], traj_pts[3, 1]), xytext=(-0.3, 0.70),
            fontsize=10, fontfamily='sans-serif', ha='center',
            arrowprops=dict(arrowstyle='->', color='black', lw=0.9), zorder=12)

# Global optimum
ax.annotate('Global optimum\n($1.6, -1.4$)', xy=(traj_pts[-1, 0], traj_pts[-1, 1]), xytext=(2.6, -1.25),
            fontsize=10.5, fontfamily='sans-serif', ha='left', va='center', color='white',
            arrowprops=dict(arrowstyle='->', color='white', lw=1.1), zorder=12)

# 右下角目标函数说明框
ax.text(0.95, 0.05, r'$\min \ f(x_1, x_2) = (x_1 - 1.5)^2 + (x_2 + 1.5)^2$',
        transform=ax.transAxes, fontsize=11.5, fontfamily='sans-serif',
        ha='right', va='bottom', bbox=dict(boxstyle='round,pad=0.5', facecolor='#8eb8d6', edgecolor='#1a334f', alpha=0.9),
        zorder=15)

# -------------------------------------------------------------
# 7. 图例排版 (紧凑左上角)
# -------------------------------------------------------------
legend_elements = [
    mpatches.Patch(facecolor='#a1d99b', edgecolor='none', alpha=0.5, label='Feasible region'),
    mpatches.Patch(facecolor='#fcbba1', edgecolor='none', alpha=0.5, label='Infeasible region'),
    Line2D([0], [0], color='black', linestyle='-', linewidth=1.4, label=r'Constraint 1: $x_1^2 + x_2^2 \leq 4$'),
    Line2D([0], [0], color='#0022ff', linestyle='--', linewidth=1.4, label=r'Constraint 2: $x_2 \geq 0.5x_1 - 1$'),
    Line2D([0], [0], color='#ff0000', linestyle='-.', linewidth=1.4, label=r'Constraint 3: $x_1 + 2x_2 \leq 3$'),
    Line2D([0], [0], color='#800080', linestyle=':', linewidth=1.6, label=r'Constraint 4: $(x_1 - 1)^2 + (x_2 + 1)^2 \geq 1$'),
    Line2D([0], [0], color='black', marker='>', markersize=6, linewidth=1.4, label='Optimization trajectory'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='white', markeredgecolor='black', markersize=5.5, label='Iterate (intermediate)'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#ff0000', markeredgecolor='black', markersize=6.5, label='Starting point'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#ff9900', markeredgecolor='black', markersize=6.5, label='Local optimum'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='#00cc00', markeredgecolor='black', markersize=6.5, label='Global optimum')
]

leg = ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(0.015, 0.99),
                frameon=True, framealpha=0.96, edgecolor='#b0bec5', fontsize=8.8, labelspacing=0.28)
leg.get_frame().set_linewidth(0.8)

# -------------------------------------------------------------
# 8. 坐标轴与独立颜色条
# -------------------------------------------------------------
ax.set_xlim(-3.0, 4.0)
ax.set_ylim(-3.0, 3.0)
ax.set_xticks(np.arange(-3, 5))
ax.set_yticks(np.arange(-3, 4))
ax.set_xlabel(r'$x_1$', fontsize=14, fontfamily='sans-serif', labelpad=4)
ax.set_ylabel(r'$x_2$', fontsize=14, fontfamily='sans-serif', labelpad=4)
ax.tick_params(labelsize=11)

cbar_ax = fig.add_axes([0.90, 0.11, 0.024, 0.77])
cbar = fig.colorbar(cf, cax=cbar_ax, ticks=np.linspace(0, 20, 11))
cbar.ax.tick_params(labelsize=11, width=0.8, length=4)
cbar.set_label('Objective value', fontsize=12.5, fontfamily='sans-serif', labelpad=8)
for spine in cbar.ax.spines.values():
    spine.set_linewidth(0.8)

save_py_nature_figure(fig, FilePath(_args.output_dir) / "constrained_optimization_landscape_template")



