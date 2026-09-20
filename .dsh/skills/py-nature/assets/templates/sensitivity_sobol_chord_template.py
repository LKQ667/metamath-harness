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
from matplotlib.path import Path
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm, Normalize
import os

# -------------------------------------------------------------
# 1. 学术排版与色彩配置
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

# 5段分段色卡 (First-order Sobol index)
sobol_colors = ['#eaf2f8', '#bdd7ee', '#6baed6', '#3182bd', '#08519c']
cmap_sobol = LinearSegmentedColormap.from_list('sobol_discrete', sobol_colors, N=5)
bounds_sobol = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25]
norm_sobol = BoundaryNorm(bounds_sobol, cmap_sobol.N)

# 连续渐变色卡 (Interaction strength)
cmap_inter = LinearSegmentedColormap.from_list('inter_continuous', [
    (0.00, '#ffffff'),
    (0.20, '#dadaeb'),
    (0.45, '#9e9ac8'),
    (0.70, '#6a51a3'),
    (1.00, '#3f007d')
], N=256)
norm_inter = Normalize(vmin=0.00, vmax=0.20)

# -------------------------------------------------------------
# 2. 节点数据与角度配置
# -------------------------------------------------------------
vars_data = [
    (r'$x_1$', 0.24, 90, (0.0, 0.18), (0.03, 0.08)),
    (r'$x_2$', 0.12, 45, (0.13, 0.13), (0.11, 0.05)),
    (r'$x_3$', 0.18, 0, (0.18, 0.0), (0.12, -0.06)),
    (r'$x_4$', 0.08, 315, (0.13, -0.13), (0.12, -0.06)),
    (r'$x_5$', 0.15, 270, (0.0, -0.18), (0.0, -0.09)),
    (r'$x_6$', 0.07, 225, (-0.13, -0.13), (-0.11, -0.06)),
    (r'$x_7$', 0.11, 180, (-0.18, 0.0), (-0.13, -0.06)),
    (r'$x_8$', 0.05, 135, (-0.13, 0.13), (-0.11, 0.06))
]

n_vars = len(vars_data)
arc_span = 36.0  
r_inner = 0.98
r_mid = 1.03
r_outer = 1.09

# 交互作用强度定义
inter_data = [
    (0, 2, 0.18, '#54278f', 0.85),  # x1 - x3 强交互 (紫色)
    (0, 4, 0.10, '#3182bd', 0.45),  # x1 - x5
    (0, 5, 0.08, '#6baed6', 0.40),  # x1 - x6
    (0, 6, 0.07, '#9ecae1', 0.35),  # x1 - x7
    (1, 2, 0.06, '#3182bd', 0.35),  # x2 - x3
    (2, 5, 0.09, '#756bb1', 0.45),  # x3 - x6
    (3, 4, 0.08, '#3182bd', 0.40),  # x4 - x5
    (4, 7, 0.07, '#6baed6', 0.35),  # x5 - x8
    (5, 6, 0.05, '#9ecae1', 0.30),  # x6 - x7
    (1, 7, 0.05, '#c6dbef', 0.30)   # x2 - x8
]

# -------------------------------------------------------------
# 3. 几何路径生成
# -------------------------------------------------------------
def get_arc_path(theta1, theta2, r1, r2):
    t = np.linspace(np.radians(theta1), np.radians(theta2), 50)
    t_rev = t[::-1]
    x_outer = r2 * np.cos(t)
    y_outer = r2 * np.sin(t)
    x_inner = r1 * np.cos(t_rev)
    y_inner = r1 * np.sin(t_rev)
    verts = [(x_outer[0], y_outer[0])]
    for x, y in zip(x_outer[1:], y_outer[1:]):
        verts.append((x, y))
    for x, y in zip(x_inner, y_inner):
        verts.append((x, y))
    verts.append(verts[0])
    codes = [Path.MOVETO] + [Path.LINETO] * (len(verts) - 2) + [Path.CLOSEPOLY]
    return Path(verts, codes)

def get_chord_ribbon(t1_s, t1_e, t2_s, t2_e, r=r_inner):
    rad1_s, rad1_e = np.radians(t1_s), np.radians(t1_e)
    rad2_s, rad2_e = np.radians(t2_s), np.radians(t2_e)
    p1_s = (r * np.cos(rad1_s), r * np.sin(rad1_s))
    p1_e = (r * np.cos(rad1_e), r * np.sin(rad1_e))
    p2_s = (r * np.cos(rad2_s), r * np.sin(rad2_s))
    p2_e = (r * np.cos(rad2_e), r * np.sin(rad2_e))
    
    verts = [
        p1_s,
        (0.0, 0.0), p2_e, p2_e,
        p2_s,
        (0.0, 0.0), p1_e, p1_e,
        p1_s
    ]
    codes = [
        Path.MOVETO,
        Path.CURVE3, Path.CURVE3, Path.LINETO,
        Path.LINETO,
        Path.CURVE3, Path.CURVE3, Path.LINETO,
        Path.CLOSEPOLY
    ]
    return Path(verts, codes)

# -------------------------------------------------------------
# 4. 绘图与渲染
# -------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 9.5), dpi=300)
ax.set_aspect('equal')

# 4.1 绘制内部交互弦带
for i, j, strength, col, alpha in inter_data:
    deg1 = vars_data[i][2]
    deg2 = vars_data[j][2]
    w = strength * 85.0
    ribbon = get_chord_ribbon(deg1 - w/2, deg1 + w/2, deg2 - w/2, deg2 + w/2, r=r_inner)
    patch = mpatches.PathPatch(ribbon, facecolor=col, edgecolor=col, linewidth=0.3, alpha=alpha, zorder=3 if strength < 0.15 else 6)
    ax.add_patch(patch)

# 4.2 绘制双层外环与外延引线
for name, s_val, deg, offset_name, offset_val in vars_data:
    t_start = deg - arc_span / 2
    t_end = deg + arc_span / 2
    
    # 内层薄淡蓝环
    inner_arc = get_arc_path(t_start, t_end, r_inner, r_mid)
    ax.add_patch(mpatches.PathPatch(inner_arc, facecolor='#d9eaf7', edgecolor='#8cb6d9', linewidth=0.5, zorder=8))
    
    # 外层一阶 Sobol 色彩环
    outer_arc = get_arc_path(t_start, t_end, r_mid, r_outer)
    col = cmap_sobol(norm_sobol(s_val))
    ax.add_patch(mpatches.PathPatch(outer_arc, facecolor=col, edgecolor='#2b5c8f', linewidth=0.6, zorder=9))
    
    # 扇区两端径向分割线
    rad_s, rad_e = np.radians(t_start), np.radians(t_end)
    ax.plot([r_inner * np.cos(rad_s), (r_outer + 0.02) * np.cos(rad_s)],
            [r_inner * np.sin(rad_s), (r_outer + 0.02) * np.sin(rad_s)], color='#1a2b3c', linewidth=0.8, zorder=10)
    ax.plot([r_inner * np.cos(rad_e), (r_outer + 0.02) * np.cos(rad_e)],
            [r_inner * np.sin(rad_e), (r_outer + 0.02) * np.sin(rad_e)], color='#1a2b3c', linewidth=0.8, zorder=10)
    
    # 外围刻度指示引线
    rad_c = np.radians(deg)
    r_t1, r_t2 = r_outer + 0.015, r_outer + 0.075
    ax.plot([r_t1 * np.cos(rad_c), r_t2 * np.cos(rad_c)],
            [r_t1 * np.sin(rad_c), r_t2 * np.sin(rad_c)], color='#1a2b3c', linewidth=1.0, zorder=10)
    
    # 变量标题 (x1~x8)
    r_txt = r_outer + 0.17
    ax.text(r_txt * np.cos(rad_c), r_txt * np.sin(rad_c), name, 
            ha='center', va='center', fontsize=20, fontfamily='sans-serif', zorder=12)
    
    # 数值标注 (如 0.24, 0.12...)
    r_val_r = r_outer + 0.075
    val_rad = rad_c - 0.12 if deg in [90, 45, 0, 135] else rad_c + 0.12
    ax.text(r_val_r * np.cos(val_rad), r_val_r * np.sin(val_rad), f'{s_val:.2f}',
            ha='center', va='center', fontsize=11, fontfamily='sans-serif', color='#1a2b3c', zorder=12)

# 最内层极细参考虚线圆
theta_full = np.linspace(0, 2*np.pi, 300)
ax.plot(r_inner * np.cos(theta_full), r_inner * np.sin(theta_full), color='#a6bddb', linewidth=0.6, linestyle='--', zorder=4)

# -------------------------------------------------------------
# 5. 底部双颜色条
# -------------------------------------------------------------
# 左侧: First-order Sobol index S_i (分段)
cbar_ax1 = fig.add_axes([0.12, 0.07, 0.34, 0.024])
sm1 = plt.cm.ScalarMappable(cmap=cmap_sobol, norm=norm_sobol)
sm1.set_array([])
cbar1 = fig.colorbar(sm1, cax=cbar_ax1, orientation='horizontal', ticks=bounds_sobol)
cbar1.ax.tick_params(labelsize=10, width=0.8, length=3)
cbar1.ax.xaxis.set_label_position('top')
cbar1.set_label(r'First-order Sobol index  $S_i$', fontsize=11.5, fontfamily='sans-serif', labelpad=6)
for spine in cbar1.ax.spines.values():
    spine.set_linewidth(0.8)

# 右侧: Interaction strength S_ij (连续)
cbar_ax2 = fig.add_axes([0.56, 0.07, 0.34, 0.024])
sm2 = plt.cm.ScalarMappable(cmap=cmap_inter, norm=norm_inter)
sm2.set_array([])
cbar2 = fig.colorbar(sm2, cax=cbar_ax2, orientation='horizontal', ticks=[0.00, 0.05, 0.10, 0.15, 0.20])
cbar2.ax.tick_params(labelsize=10, width=0.8, length=3)
cbar2.ax.xaxis.set_label_position('top')
cbar2.set_label(r'Interaction strength  $S_{ij}$', fontsize=11.5, fontfamily='sans-serif', labelpad=6)
for spine in cbar2.ax.spines.values():
    spine.set_linewidth(0.8)

ax.set_xlim(-1.45, 1.45)
ax.set_ylim(-1.45, 1.45)
ax.axis('off')

save_py_nature_figure(fig, FilePath(_args.output_dir) / "sensitivity_sobol_chord_template")



