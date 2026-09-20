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
from matplotlib.colors import LinearSegmentedColormap
import os

# -------------------------------------------------------------
# 1. 学术排版与全局字体
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

fig = plt.figure(figsize=(10.8, 9.2), dpi=300)

# -------------------------------------------------------------
# 2. 定制顶刊势能面色系 (Deep Blue to Ice White)
# -------------------------------------------------------------
colors_pot = [
    (0.00, '#08264d'),
    (0.18, '#12436d'),
    (0.35, '#246b9c'),
    (0.52, '#4d9bbd'),
    (0.70, '#8ec3d8'),
    (0.85, '#cfe5ee'),
    (1.00, '#f0f7fa')
]
cmap_pot = LinearSegmentedColormap.from_list('potential_cmap', colors_pot, N=256)

# -------------------------------------------------------------
# 3. 解析构建三吸引子势能函数 V(x1, x2) 与梯度流场
# -------------------------------------------------------------
p1 = np.array([-1.8, 1.4])    # A1
p2 = np.array([-1.3, -1.6])   # A2
p3 = np.array([1.8, 0.2])     # A3

def calc_potential_and_flow(X1, X2):
    # 三个高斯势阱深度与方差
    d1_sq = (X1 - p1[0])**2 + (X2 - p1[1])**2
    d2_sq = (X1 - p2[0])**2 + (X2 - p2[1])**2
    d3_sq = (X1 - p3[0])**2 + (X2 - p3[1])**2
    
    s1 = 1.35
    s2 = 1.35
    s3 = 1.35
    
    w1 = 3.65 * np.exp(-d1_sq / s1)
    w2 = 3.65 * np.exp(-d2_sq / s2)
    w3 = 3.65 * np.exp(-d3_sq / s3)
    
    # 全局二次约束势
    conf = 0.22 * (X1**2 + X2**2)
    
    # 鞍点 (0,0) 附近的双曲微扰
    saddle = 0.12 * (X1**2 - X2**2) - 0.08 * (X1 * X2)
    
    V = conf - w1 - w2 - w3 + saddle
    # 归一化/平移使鞍点 V(0,0) 约为 0.0
    V = V - V[(np.abs(X1) < 0.04) & (np.abs(X2) < 0.04)].mean()
    
    # 解析导数 dV/dx1 和 dV/dx2
    dV_dx1 = (
        0.44 * X1
        + (2 * (X1 - p1[0]) / s1) * w1
        + (2 * (X1 - p2[0]) / s2) * w2
        + (2 * (X1 - p3[0]) / s3) * w3
        + 0.24 * X1 - 0.08 * X2
    )
    dV_dx2 = (
        0.44 * X2
        + (2 * (X2 - p1[1]) / s1) * w1
        + (2 * (X2 - p2[1]) / s2) * w2
        + (2 * (X2 - p3[1]) / s3) * w3
        - 0.24 * X2 - 0.08 * X1
    )
    
    # 梯度流 + 微弱旋转耦合
    U = -dV_dx1 + 0.15 * dV_dx2
    W = -dV_dx2 - 0.15 * dV_dx1
    
    return V, U, W

# 网格划分
x1_grid = np.linspace(-3.0, 3.0, 350)
x2_grid = np.linspace(-3.0, 3.0, 350)
X1, X2 = np.meshgrid(x1_grid, x2_grid)
V, U, W = calc_potential_and_flow(X1, X2)

# -------------------------------------------------------------
# 4. 主图绘制
# -------------------------------------------------------------
ax = fig.add_axes([0.08, 0.08, 0.77, 0.85])
ax.set_aspect('equal')
ax.set_xlim(-3.0, 3.0)
ax.set_ylim(-3.0, 3.0)

# 4.1 绘制势能等高线填色底图 (平滑无边界溢出)
levels = np.linspace(-3.0, 3.0, 31)
im = ax.contourf(X1, X2, V, levels=levels, cmap=cmap_pot, extend='neither')
# 细等高线刻画势能起伏
ax.contour(X1, X2, V, levels=levels, colors='#244d70', linewidths=0.45, alpha=0.4)

# 4.2 绘制向量场流线 (Streamlines)
strm = ax.streamplot(x1_grid, x2_grid, U, W, color='#45667e', linewidth=0.6,
                     density=1.4, arrowsize=0.85, arrowstyle='->', zorder=4)

# 4.3 零斜线 (Nullclines) - 严格复现原图的拓扑形态
# \dot{x}_1 = 0: 近乎垂直的 S-形深蓝虚线
y_nc1 = np.linspace(-3.0, 3.0, 200)
x_nc1 = 0.14 + 0.14 * np.tanh(1.8 * y_nc1) - 0.28 * np.exp(-((y_nc1 - 0.8)/0.9)**2) + 0.15 * np.exp(-((y_nc1 + 1.8)/0.8)**2)
ax.plot(x_nc1, y_nc1, color='#0a1c30', linestyle='--', lw=1.8, zorder=6)

# \dot{x}_2 = 0: 近乎水平的水鸭青虚线
x_nc2 = np.linspace(-3.0, 3.0, 200)
y_nc2 = 0.02 + 0.36 * np.sin(x_nc2 / 1.1) * np.exp(-((x_nc2 + 0.8)/2.2)**2) - 0.12 * x_nc2
ax.plot(x_nc2, y_nc2, color='#00796b', linestyle='--', lw=1.8, zorder=6)

# 4.4 吸引盆分界线 (Separatrix / Basin Boundary, 紫色点线)
# 3 根分界线汇聚于鞍点 (0,0)
t_sep = np.linspace(0, 1, 150)
# 支 1: (0,0) -> (-3, -1)
sep1_x = -3.0 * t_sep
sep1_y = -1.0 * t_sep - 0.35 * np.sin(np.pi * t_sep) + 0.15 * np.sin(2 * np.pi * t_sep)
ax.plot(sep1_x, sep1_y, color='#7b1fa2', linestyle=':', lw=2.0, zorder=8)

# 支 2: (0,0) -> (0.8, 3)
sep2_x = 0.8 * t_sep + 0.38 * np.sin(np.pi * t_sep)
sep2_y = 3.0 * t_sep
ax.plot(sep2_x, sep2_y, color='#7b1fa2', linestyle=':', lw=2.0, zorder=8)

# 支 3: (0,0) -> (3, -3)
sep3_x = 3.0 * t_sep
sep3_y = -3.0 * t_sep + 0.55 * np.sin(np.pi * t_sep)
ax.plot(sep3_x, sep3_y, color='#7b1fa2', linestyle=':', lw=2.0, zorder=8)

# 4.5 轨迹束 (Trajectory Bundles) - 采用贝塞尔曲线簇严格呈现原图轨迹
def bezier_curve(p0, p1, p2, p3, n_points=100):
    t_b = np.linspace(0, 1, n_points)[:, None]
    return (1 - t_b)**3 * p0 + 3 * (1 - t_b)**2 * t_b * p1 + 3 * (1 - t_b) * t_b**2 * p2 + t_b**3 * p3

# (1) 流向 A1 轨迹束 (鲜明蓝色)
col_b1 = '#1976d2'
for i, offset in enumerate(np.linspace(-0.06, 0.06, 7)):
    p0 = np.array([0.0 + offset, 0.0 + offset])
    c1 = np.array([-0.35 + offset*1.5, 0.75 + offset])
    c2 = np.array([-1.1 + offset*0.8, 1.7 - offset])
    c3 = p1
    curve = bezier_curve(p0, c1, c2, c3)
    ax.plot(curve[:, 0], curve[:, 1], color=col_b1, lw=1.3, alpha=0.85, zorder=7)
    if i == 3:  # 中间主线加箭头
        ax.annotate('', xy=(curve[58, 0], curve[58, 1]), xytext=(curve[50, 0], curve[50, 1]),
                    arrowprops=dict(arrowstyle='->', lw=1.6, color=col_b1), zorder=9)

# (2) 流向 A2 轨迹束 (水鸭青绿)
col_b2 = '#00897b'
for i, offset in enumerate(np.linspace(-0.06, 0.06, 7)):
    p0 = np.array([0.0 + offset, 0.0 - offset])
    c1 = np.array([-0.3 + offset*1.2, -0.65 - offset])
    c2 = np.array([-0.8 + offset*0.8, -1.35 - offset*0.5])
    c3 = p2
    curve = bezier_curve(p0, c1, c2, c3)
    ax.plot(curve[:, 0], curve[:, 1], color=col_b2, lw=1.3, alpha=0.85, zorder=7)
    if i == 3:
        ax.annotate('', xy=(curve[58, 0], curve[58, 1]), xytext=(curve[50, 0], curve[50, 1]),
                    arrowprops=dict(arrowstyle='->', lw=1.6, color=col_b2), zorder=9)

# (3) 流向 A3 轨迹束 (淡冰蓝/天青)
col_b3 = '#80deea'
for i, offset in enumerate(np.linspace(-0.05, 0.05, 6)):
    p0 = np.array([0.0 + offset*0.5, 0.0 + offset])
    c1 = np.array([0.65 + offset*0.8, 0.12 + offset*1.2])
    c2 = np.array([1.25 + offset*0.5, 0.18 + offset*0.6])
    c3 = p3
    curve = bezier_curve(p0, c1, c2, c3)
    ax.plot(curve[:, 0], curve[:, 1], color=col_b3, lw=1.3, alpha=0.85, zorder=7)
    if i == 2:
        ax.annotate('', xy=(curve[58, 0], curve[58, 1]), xytext=(curve[50, 0], curve[50, 1]),
                    arrowprops=dict(arrowstyle='->', lw=1.6, color=col_b3), zorder=9)

# 4.6 样本随机轨迹 (Sample Trajectories, 细浅灰/淡蓝线流入吸引子)
sample_trajs = [
    # 进入 A1
    (np.array([-2.5, 2.6]), np.array([-2.2, 1.8]), np.array([-1.9, 1.6]), p1),
    (np.array([-1.0, 2.7]), np.array([-1.3, 2.1]), np.array([-1.6, 1.7]), p1),
    # 进入 A2
    (np.array([-2.5, -2.5]), np.array([-2.0, -2.1]), np.array([-1.6, -1.8]), p2),
    (np.array([-2.6, -0.6]), np.array([-2.1, -1.0]), np.array([-1.7, -1.4]), p2),
    # 进入 A3
    (np.array([2.6, 1.6]), np.array([2.3, 1.0]), np.array([2.0, 0.5]), p3),
    (np.array([2.6, -0.8]), np.array([2.3, -0.3]), np.array([2.0, 0.0]), p3)
]
for p0, c1, c2, c3 in sample_trajs:
    curve = bezier_curve(p0, c1, c2, c3)
    ax.plot(curve[:, 0], curve[:, 1], color='#b0bec5', lw=0.9, alpha=0.7, zorder=5)
    ax.annotate('', xy=(curve[60, 0], curve[60, 1]), xytext=(curve[50, 0], curve[50, 1]),
                arrowprops=dict(arrowstyle='->', lw=0.9, color='#b0bec5'), zorder=5)

# 4.7 稳定吸引子 (Stable Attractors) 标记
attractors = [
    (p1, r'$A_1$' + '\n' + r'$(-1.8, 1.4)$', 'left', 0.14, 0.0),
    (p2, r'$A_2$' + '\n' + r'$(-1.3, -1.6)$', 'left', 0.14, -0.05),
    (p3, r'$A_3$' + '\n' + r'$(1.8, 0.2)$', 'left', 0.14, -0.05)
]

for pt, lbl, ha, dx, dy in attractors:
    circle = mpatches.Circle((pt[0], pt[1]), 0.08, facecolor='#08264d',
                             edgecolor='white', linewidth=1.6, zorder=15)
    ax.add_patch(circle)
    ax.text(pt[0] + dx, pt[1] + dy, lbl, fontsize=11, fontfamily='sans-serif',
            color='white', fontweight='semibold', ha=ha, va='center', zorder=16)

# 4.8 不稳定鞍点 (Saddle Point) 标记
ax.plot(0.0, 0.0, marker='x', markersize=9.5, markeredgewidth=2.2,
        markeredgecolor='#c62828', zorder=16)
ax.text(0.12, 0.06, r'$S$' + '\n' + r'$(0.0, 0.0)$', fontsize=10.5, fontfamily='sans-serif',
        color='#c62828', fontweight='semibold', va='center', zorder=16)

# 4.9 吸引盆文字标注 (Basin of A1, A2, A3)
ax.text(-2.7, 2.6, r'Basin of $A_1$', fontsize=11.5, fontstyle='italic', fontfamily='sans-serif', color='#263238')
ax.text(-2.7, -2.7, r'Basin of $A_2$', fontsize=11.5, fontstyle='italic', fontfamily='sans-serif', color='#263238')
ax.text(1.8, -1.6, r'Basin of $A_3$', fontsize=11.5, fontstyle='italic', fontfamily='sans-serif', color='#263238')

# 4.10 坐标轴设置
ax.set_xticks(np.linspace(-3, 3, 7))
ax.set_yticks(np.linspace(-3, 3, 7))
ax.tick_params(axis='both', which='both', labelsize=11.5, width=0.8, length=4.5)
ax.set_xlabel(r'State $x_1$', fontsize=13, fontfamily='sans-serif', labelpad=6)
ax.set_ylabel(r'State $x_2$', fontsize=13, fontfamily='sans-serif', labelpad=6)

# -------------------------------------------------------------
# 5. 右上角图例与右下角方程卡片
# -------------------------------------------------------------
leg_elements = [
    plt.Line2D([0], [0], color='#45667e', lw=1.2, marker='>', markersize=5, label='Vector field (streamlines)'),
    plt.Line2D([0], [0], color='#0a1c30', lw=1.8, linestyle='--', label=r'Nullcline $\dot{x}_1 = 0$'),
    plt.Line2D([0], [0], color='#00796b', lw=1.8, linestyle='--', label=r'Nullcline $\dot{x}_2 = 0$'),
    plt.Line2D([0], [0], color='#b0bec5', lw=1.2, label='Trajectory (sample)'),
    plt.Line2D([0], [0], color=col_b1, lw=1.8, label='Trajectory bundle'),
    plt.Line2D([0], [0], marker='o', markersize=6.5, markerfacecolor='#08264d',
               markeredgecolor='white', markeredgewidth=1.2, linestyle='none', label='Stable fixed point (attractor)'),
    plt.Line2D([0], [0], marker='x', markersize=7.5, markeredgewidth=1.8,
               markeredgecolor='#c62828', linestyle='none', label='Unstable fixed point (saddle)'),
    plt.Line2D([0], [0], color='#7b1fa2', lw=1.8, linestyle=':', label='Basin boundary (separatrix)')
]

leg = ax.legend(handles=leg_elements, loc='upper right', frameon=True,
                facecolor='white', edgecolor='#cfd8dc', framealpha=0.92,
                fontsize=9.0, handlelength=2.2, labelspacing=0.5)

# 右下角动力学方程卡片
rect_eq = mpatches.FancyBboxPatch(
    (0.65, 0.04), 0.32, 0.09, boxstyle="round,pad=0.02,rounding_size=0.015",
    facecolor='white', edgecolor='#37474f', linewidth=0.9, transform=ax.transAxes, zorder=20
)
ax.add_patch(rect_eq)
ax.text(0.81, 0.095, r'$\dot{x} = -\nabla V(x_1, x_2)$', transform=ax.transAxes,
        fontsize=11.5, fontweight='bold', fontfamily='sans-serif', color='#102027', ha='center', va='center', zorder=21)
ax.text(0.81, 0.058, 'Gradient flow with multiple attractors', transform=ax.transAxes,
        fontsize=8.2, fontfamily='sans-serif', color='#455a64', ha='center', va='center', zorder=21)

# -------------------------------------------------------------
# 6. 右侧独立垂直颜色条 (Colorbar)
# -------------------------------------------------------------
cbar_ax = fig.add_axes([0.895, 0.08, 0.025, 0.85])
cbar = fig.colorbar(im, cax=cbar_ax, ticks=np.linspace(-3.0, 3.0, 7))
cbar.ax.tick_params(labelsize=11.5, width=0.8, length=4)
cbar.set_label(r'Potential  $V(x_1, x_2)$', fontsize=12.5, fontfamily='sans-serif', labelpad=8)
for spine in cbar.ax.spines.values():
    spine.set_linewidth(0.8)

# -------------------------------------------------------------
# 7. 顶部大标题
# -------------------------------------------------------------
fig.text(0.47, 0.965, 'Regime Transition Structure in Phase Space',
         ha='center', va='top', fontsize=17, fontweight='bold', fontfamily='sans-serif', color='#102027')

# -------------------------------------------------------------
# 8. 保存高质量成果图
# -------------------------------------------------------------
save_py_nature_figure(fig, FilePath(_args.output_dir) / "dynamics_multi_attractor_template")



