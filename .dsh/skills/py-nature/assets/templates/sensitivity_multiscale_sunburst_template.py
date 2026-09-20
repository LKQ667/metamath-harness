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
from matplotlib.colors import LinearSegmentedColormap, Normalize
import os

# -------------------------------------------------------------
# 1. 学术排版与全局字体
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

fig = plt.figure(figsize=(12.0, 9.2), dpi=300)

# -------------------------------------------------------------
# 2. 定制顶刊海洋蓝渐变色系 (Sequential Ocean Blue)
# -------------------------------------------------------------
colors_ocean = [
    (0.00, '#f0f7fa'),
    (0.20, '#a3d1df'),
    (0.40, '#53a8c3'),
    (0.60, '#277a9e'),
    (0.80, '#124c75'),
    (1.00, '#0a233f')
]
cmap_sens = LinearSegmentedColormap.from_list('ocean_sens', colors_ocean, N=256)
norm = Normalize(vmin=0.0, vmax=1.0)

# -------------------------------------------------------------
# 3. 主极坐标 / 环形扇区几何参数
# -------------------------------------------------------------
theta_centers = np.array([90, 45, 0, 315, 270, 225, 180, 135])
d_theta = 45.0
half_d = d_theta / 2.0

R_hub = 1.35        # 中心总不确定性核心圆
R_unc_max = 1.75    # 不确定性贡献环外缘基准
R_stage_base = 1.78 # Stage 1 内径
stage_dr = 0.38     # 每个 Stage 环宽
stage_radii = [R_stage_base + i * stage_dr for i in range(7)]  # R_stage_base 到 R_stage_6_out (~4.06)
R_dots = stage_radii[-1] + 0.22                                # 显著性圆点所在半径 (~4.28)

# -------------------------------------------------------------
# 4. 8 参数与 6 阶段敏感性指数 & 显著性数据
# -------------------------------------------------------------
sens_data = np.array([
    # Stage 1, Stage 2, Stage 3, Stage 4, Stage 5, Stage 6
    [0.15, 0.32, 0.52, 0.70, 0.86, 0.96],  # theta_1 (Growth rate)
    [0.22, 0.38, 0.50, 0.65, 0.55, 0.42],  # theta_2 (Carrying capacity)
    [0.35, 0.58, 0.78, 0.95, 0.85, 0.68],  # theta_3 (Transmission rate)
    [0.25, 0.42, 0.55, 0.52, 0.62, 0.46],  # theta_4 (Recovery rate)
    [0.16, 0.26, 0.48, 0.58, 0.72, 0.82],  # theta_5 (Mortality rate)
    [0.20, 0.46, 0.68, 0.78, 0.88, 0.95],  # theta_6 (Contact rate)
    [0.68, 0.60, 0.50, 0.40, 0.30, 0.18],  # theta_7 (Environmental forcing)
    [0.52, 0.36, 0.24, 0.14, 0.08, 0.05]   # theta_8 (Initial condition)
])

# 显著性数据 (True: Significant p<0.05, False: Not significant)
# 顺时针排列: Stage 1 ~ Stage 6
sig_data = np.array([
    [False, True,  True,  True,  True,  True],   # theta_1
    [True,  True,  True,  False, False, True],   # theta_2
    [True,  True,  True,  True,  True,  True],   # theta_3
    [True,  True,  True,  False, True,  False],  # theta_4
    [True,  True,  True,  False, False, False],  # theta_5
    [False, True,  True,  True,  True,  True],   # theta_6
    [False, True,  False, True,  True,  True],   # theta_7
    [False, False, False, False, True,  True]    # theta_8
])

uncertainty_shares = np.array([0.18, 0.08, 0.22, 0.11, 0.07, 0.15, 0.13, 0.06])

# -------------------------------------------------------------
# 5. 绘制主图
# -------------------------------------------------------------
ax_main = fig.add_axes([0.04, 0.08, 0.76, 0.80])
ax_main.set_aspect('equal')
ax_main.axis('off')
ax_main.set_xlim(-6.0, 6.0)
ax_main.set_ylim(-5.6, 5.6)

# 5.1 绘制 Stage 1 ~ Stage 6 环形扇区
for p in range(8):
    th_c = theta_centers[p]
    th_start = th_c - half_d
    th_end = th_c + half_d
    
    for s in range(6):
        r_in = stage_radii[s]
        r_out = stage_radii[s + 1]
        val = sens_data[p, s]
        col = cmap_sens(norm(val))
        
        wedge = mpatches.Wedge(
            (0, 0), r_out, th_start, th_end, width=(r_out - r_in),
            facecolor=col, edgecolor='white', linewidth=1.5
        )
        ax_main.add_patch(wedge)

# 5.2 绘制顶部 theta_1 扇区内的 "Stage 1" ~ "Stage 6" 文字标签
for s in range(6):
    r_mid = (stage_radii[s] + stage_radii[s + 1]) / 2.0
    val = sens_data[0, s]
    text_col = 'white' if val > 0.45 else '#1a3038'
    ax_main.text(
        0, r_mid, f'Stage {s + 1}',
        ha='center', va='center', fontsize=9.5, fontfamily='sans-serif',
        color=text_col, fontweight='semibold'
    )

# 5.3 绘制不确定性贡献环 (内圈浅青色玫瑰扇区)
# 底衬参考圆环
circle_ref = mpatches.Circle(
    (0, 0), R_unc_max, facecolor='none', edgecolor='#cfd8dc', linewidth=0.8, linestyle=':'
)
ax_main.add_patch(circle_ref)

col_unc = '#80cbc4'
for p in range(8):
    th_c = theta_centers[p]
    th_start = th_c - half_d
    th_end = th_c + half_d
    share = uncertainty_shares[p]
    r_bar = R_hub + (R_unc_max - R_hub) * (share / 0.25)
    r_bar = min(r_bar, R_unc_max)
    
    w_unc = mpatches.Wedge(
        (0, 0), r_bar, th_start, th_end, width=(r_bar - R_hub),
        facecolor=col_unc, edgecolor='white', linewidth=1.5
    )
    ax_main.add_patch(w_unc)

# 5.4 中心核心圆 (Total Uncertainty Hub)
circle_hub = mpatches.Circle(
    (0, 0), R_hub, facecolor='white', edgecolor='#b0bec5', linewidth=1.4, zorder=10
)
ax_main.add_patch(circle_hub)

# 核心圆内小条形柱状图图标
bar_w = 0.08
bar_xs = [-0.15, -0.05, 0.05, 0.15]
bar_hs = [0.22, 0.40, 0.28, 0.16]
bar_cols = ['#78909c', '#455a64', '#546e7a', '#90a4ae']
for bx, bh, bc in zip(bar_xs, bar_hs, bar_cols):
    rect = mpatches.Rectangle((bx - bar_w/2, 0.20), bar_w, bh, facecolor=bc, edgecolor='none', zorder=12)
    ax_main.add_patch(rect)

# 核心圆内文字
ax_main.text(0, 0.02, 'Total uncertainty', ha='center', va='center',
             fontsize=10.5, fontweight='bold', fontfamily='sans-serif', color='#263238', zorder=12)
ax_main.text(0, -0.16, '(contribution to output variance)', ha='center', va='center',
             fontsize=8.0, fontfamily='sans-serif', color='#546e7a', zorder=12)
ax_main.text(0, -0.38, r'$\Sigma = 1.00$', ha='center', va='center',
             fontsize=11.5, fontweight='bold', fontfamily='sans-serif', color='#102027', zorder=12)

# 5.5 绘制外圈显著性圆点 (Significance Dots)
# 顺时针排列 (Stage 1 到 Stage 6)
for p in range(8):
    th_c = theta_centers[p]
    dot_offsets = np.linspace(13.0, -13.0, 6)
    for s in range(6):
        d_ang = th_c + dot_offsets[s]
        rad = np.radians(d_ang)
        x_dot = R_dots * np.cos(rad)
        y_dot = R_dots * np.sin(rad)
        
        is_sig = sig_data[p, s]
        if is_sig:
            ax_main.plot(x_dot, y_dot, marker='o', markersize=4.6,
                         markerfacecolor='#0a233f', markeredgecolor='#0a233f', zorder=15)
        else:
            ax_main.plot(x_dot, y_dot, marker='o', markersize=4.6,
                         markerfacecolor='white', markeredgecolor='#0a233f', markeredgewidth=1.0, zorder=15)

# 5.6 绘制参数组外延虚线分割线 (从 Stage 6 外径延伸至外围)
sep_angles = [112.5, 22.5, 292.5, 202.5, 157.5]
for ang in sep_angles:
    rad = np.radians(ang)
    x1, y1 = (stage_radii[-1] + 0.03) * np.cos(rad), (stage_radii[-1] + 0.03) * np.sin(rad)
    x2, y2 = 5.25 * np.cos(rad), 5.25 * np.sin(rad)
    ax_main.plot([x1, x2], [y1, y2], color='#78909c', linestyle='--', linewidth=1.1, zorder=8)

# 5.7 绘制外圈参数名称与物理含义标注
params_meta = [
    (0, r'Parameter' + '\n' + r'$\mathbf{\theta_1}$' + '\n' + r'(Growth rate)', 0.0, 4.75, 'center', 'bottom'),
    (1, r'$\mathbf{\theta_2}$' + '\n' + r'(Carrying' + '\n' + r'capacity)', 3.45, 3.45, 'center', 'center'),
    (2, r'$\mathbf{\theta_3}$' + '\n' + r'(Transmission' + '\n' + r'rate)', 4.75, 0.0, 'left', 'center'),
    (3, r'$\mathbf{\theta_4}$' + '\n' + r'(Recovery rate)', 3.45, -3.45, 'center', 'center'),
    (4, r'$\mathbf{\theta_5}$' + '\n' + r'(Mortality rate)', 0.0, -4.75, 'center', 'top'),
    (5, r'$\mathbf{\theta_6}$' + '\n' + r'(Contact rate)', -3.45, -3.45, 'center', 'center'),
    (6, r'$\mathbf{\theta_7}$' + '\n' + r'(Environmental' + '\n' + r'forcing)', -4.75, 0.0, 'right', 'center'),
    (7, r'$\mathbf{\theta_8}$' + '\n' + r'(Initial' + '\n' + r'condition)', -3.45, 3.45, 'center', 'center')
]

for p, label, x_lbl, y_lbl, ha, va in params_meta:
    ax_main.text(x_lbl, y_lbl, label, ha=ha, va=va,
                 fontsize=10.5, fontfamily='sans-serif', color='#102027', linespacing=1.2)

# 5.8 绘制 4 个过程领域的弧线支架与领域标题 (弧线位于最外圈)
def draw_group_arc(ax, th1, th2, r_arc, color, label, lbl_pos, ha='center', va='center'):
    angles = np.linspace(th1, th2, 100)
    xs = r_arc * np.cos(np.radians(angles))
    ys = r_arc * np.sin(np.radians(angles))
    ax.plot(xs, ys, color=color, linewidth=1.2, solid_capstyle='round')
    
    ax.text(lbl_pos[0], lbl_pos[1], label, ha=ha, va=va,
            fontsize=12.0, fontfamily='sans-serif', fontweight='bold', color=color, linespacing=1.2)

# 1. Population dynamics (右上)
draw_group_arc(ax_main, 25, 65, 5.45, '#00796b', 'Population\ndynamics', (4.1, 4.4), ha='left', va='bottom')

# 2. Epidemiological processes (右下)
draw_group_arc(ax_main, 295, 335, 5.45, '#1565c0', 'Epidemiological\nprocesses', (4.0, -4.4), ha='left', va='top')

# 3. Environmental & contact processes (左下)
draw_group_arc(ax_main, 205, 245, 5.45, '#0277bd', 'Environmental\n& contact processes', (-4.0, -4.4), ha='right', va='top')

# 4. Initial conditions & external drivers (左上)
draw_group_arc(ax_main, 115, 155, 5.45, '#0277bd', 'Initial conditions\n& external drivers', (-4.1, 4.4), ha='right', va='bottom')

# -------------------------------------------------------------
# 6. 右侧独立颜色条 (Colorbar)
# -------------------------------------------------------------
cbar_ax = fig.add_axes([0.87, 0.32, 0.026, 0.48])
cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap_sens), cax=cbar_ax,
                    ticks=np.linspace(0.0, 1.0, 6))
cbar.ax.tick_params(labelsize=11, width=0.8, length=4)
cbar_ax.text(0.5, 1.05, 'Sensitivity Index', transform=cbar_ax.transAxes,
             ha='center', va='bottom', fontsize=12, fontfamily='sans-serif', fontweight='semibold')
for spine in cbar.ax.spines.values():
    spine.set_linewidth(0.8)

# -------------------------------------------------------------
# 7. 右下角图例区 (Legend Box)
# -------------------------------------------------------------
ax_leg = fig.add_axes([0.79, 0.08, 0.18, 0.20])
ax_leg.axis('off')

rect_leg = mpatches.FancyBboxPatch(
    (0.0, 0.0), 1.0, 1.0, boxstyle="round,pad=0.04,rounding_size=0.03",
    facecolor='white', edgecolor='#cfd8dc', linewidth=1.0, transform=ax_leg.transAxes
)
ax_leg.add_patch(rect_leg)

ax_leg.text(0.10, 0.88, r'Significance ($p < 0.05$)', transform=ax_leg.transAxes,
            fontsize=10.0, fontweight='bold', fontfamily='sans-serif', color='#263238', va='top')

ax_leg.plot(0.18, 0.70, marker='o', markersize=5.5,
            markerfacecolor='#0a233f', markeredgecolor='#0a233f', transform=ax_leg.transAxes)
ax_leg.text(0.32, 0.70, 'Significant', transform=ax_leg.transAxes,
            fontsize=9.5, fontfamily='sans-serif', color='#37474f', va='center')

ax_leg.plot(0.18, 0.52, marker='o', markersize=5.5,
            markerfacecolor='white', markeredgecolor='#0a233f', markeredgewidth=1.0, transform=ax_leg.transAxes)
ax_leg.text(0.32, 0.52, 'Not significant', transform=ax_leg.transAxes,
            fontsize=9.5, fontfamily='sans-serif', color='#37474f', va='center')

ax_leg.plot([0.10, 0.26], [0.35, 0.35], color='#78909c', linestyle='--', linewidth=1.2, transform=ax_leg.transAxes)
ax_leg.text(0.32, 0.35, 'Parameter group separator', transform=ax_leg.transAxes,
            fontsize=8.5, fontfamily='sans-serif', color='#37474f', va='center')

rect_unc_sample = mpatches.Rectangle(
    (0.10, 0.12), 0.16, 0.14, facecolor=col_unc, edgecolor='none', transform=ax_leg.transAxes
)
ax_leg.add_patch(rect_unc_sample)
ax_leg.text(0.32, 0.19, 'Total uncertainty\n(relative contribution)', transform=ax_leg.transAxes,
            fontsize=8.5, fontfamily='sans-serif', color='#37474f', va='center', linespacing=1.1)

# -------------------------------------------------------------
# 8. 顶部主标题与底部说明
# -------------------------------------------------------------
fig.text(0.43, 0.965, 'Multiscale Global Sensitivity Structure',
         ha='center', va='top', fontsize=18, fontweight='bold', fontfamily='sans-serif', color='#102027')
fig.text(0.43, 0.932, 'Parameter influence across model stages with uncertainty and significance',
         ha='center', va='top', fontsize=12, fontstyle='italic', fontfamily='sans-serif', color='#546e7a')

fig.text(0.43, 0.035, 'Six stages  |  Eight parameters  |  Sobol total-order sensitivity index',
         ha='center', va='center', fontsize=11, fontfamily='sans-serif', color='#37474f')

# -------------------------------------------------------------
# 9. 保存高质量成果图
# -------------------------------------------------------------
save_py_nature_figure(fig, FilePath(_args.output_dir) / "sensitivity_multiscale_sunburst_template")



