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
# 1. 学术排版与色彩配置
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

# 顶刊经典发散色卡: 深酒红 - 纯白 - 深海蓝 (RdBu_r 风格定制)
colors_div = [
    (0.00, '#67001f'),
    (0.15, '#b2182b'),
    (0.30, '#d6604d'),
    (0.42, '#f4a582'),
    (0.48, '#fddbc7'),
    (0.50, '#ffffff'),
    (0.52, '#d1e5f0'),
    (0.58, '#92c5de'),
    (0.70, '#4393c3'),
    (0.85, '#2166ac'),
    (1.00, '#053061')
]
cmap_corr = LinearSegmentedColormap.from_list('academic_rdbu', colors_div, N=256)

fig = plt.figure(figsize=(10.0, 9.8), dpi=300)

# -------------------------------------------------------------
# 2. 构造 12x12 相关性矩阵与显著性 P 值
# -------------------------------------------------------------
n_vars = 12
corr = np.eye(n_vars)

# 组内高正相关，组间负相关或弱相关
# 组1: x1~x4
g1 = [0, 1, 2, 3]
c1_vals = {
    (0, 1): (0.82, '***'), (0, 2): (0.76, '***'), (0, 3): (0.68, '***'),
    (1, 2): (0.71, '***'), (1, 3): (0.63, '**'),
    (2, 3): (0.59, '**')
}
for (i, j), (val, p) in c1_vals.items():
    corr[i, j] = corr[j, i] = val

# 组2: x5~x8
g2 = [4, 5, 6, 7]
c2_vals = {
    (4, 5): (0.81, '***'), (4, 6): (0.77, '***'), (4, 7): (0.69, '***'),
    (5, 6): (0.74, '***'), (5, 7): (0.66, '***'),
    (6, 7): (0.58, '**')
}
for (i, j), (val, p) in c2_vals.items():
    corr[i, j] = corr[j, i] = val

# 组3: x9~x12
g3 = [8, 9, 10, 11]
c3_vals = {
    (8, 9): (0.83, '***'), (8, 10): (0.79, '***'), (8, 11): (0.72, '***'),
    (9, 10): (0.76, '***'), (9, 11): (0.67, '***'),
    (10, 11): (0.61, '**')
}
for (i, j), (val, p) in c3_vals.items():
    corr[i, j] = corr[j, i] = val

# 组间负相关 (与原图数值 1:1 精确对应)
inter_neg = {
    (0, 10): (-0.42, '**'), (0, 11): (-0.38, '**'),
    (1, 11): (-0.36, '*'),
    (2, 11): (-0.33, '*'),
    (4, 11): (-0.45, '***'),
    (5, 10): (-0.40, '**'),
    (6, 11): (-0.37, '**'),
    (7, 11): (-0.34, '*')
}
for (i, j), (val, p) in inter_neg.items():
    corr[i, j] = corr[j, i] = val

# 填充微弱底噪
for i in range(n_vars):
    for j in range(i + 1, n_vars):
        if corr[i, j] == 0:
            val = np.random.uniform(-0.15, 0.22)
            corr[i, j] = corr[j, i] = val

# -------------------------------------------------------------
# 3. 布局定义 (热力图 + 顶部树状图 + 左侧树状图)
# -------------------------------------------------------------
# 热力图区域
hm_x, hm_y, hm_w, hm_h = 0.20, 0.10, 0.65, 0.65
ax_hm = fig.add_axes([hm_x, hm_y, hm_w, hm_h])

im = ax_hm.imshow(corr, cmap=cmap_corr, vmin=-1.0, vmax=1.0, aspect='equal', origin='upper')

# 绘制网格白线
for k in range(n_vars + 1):
    ax_hm.axhline(k - 0.5, color='white', linewidth=1.0)
    ax_hm.axvline(k - 0.5, color='white', linewidth=1.0)

# 上三角填入数值与显著性星号
all_labels = {**c1_vals, **c2_vals, **c3_vals, **inter_neg}
for (i, j), (val, p) in all_labels.items():
    ax_hm.text(j, i, f'{val:.2f}{p}', ha='center', va='center',
               fontsize=9.5, fontfamily='sans-serif', color='white' if abs(val) > 0.65 else 'black')

ax_hm.set_xticks(range(n_vars))
ax_hm.set_yticks(range(n_vars))
labels = [rf'$x_{{{i+1}}}$' for i in range(n_vars)]
ax_hm.set_xticklabels(labels, fontsize=12)
ax_hm.set_yticklabels(labels, fontsize=12)
ax_hm.tick_params(axis='both', which='both', length=4, width=0.8)

# -------------------------------------------------------------
# 4. 顶部与左侧聚类树状图 (Dendrogram)
# -------------------------------------------------------------
# 4.1 顶部树状图区域
ax_top = fig.add_axes([hm_x, hm_y + hm_h, hm_w, 0.16])
ax_top.axis('off')

# 3个聚类横向背景色块与标题
clusters_meta = [
    (0, 3.8, 'Cluster I\n($x_1, x_2, x_3, x_4$)', '#1e88e5', '#e3f2fd'),
    (3.9, 7.8, 'Cluster II\n($x_5, x_6, x_7, x_8$)', '#2e7d32', '#e8f5e9'),
    (7.9, 11.8, 'Cluster III\n($x_9, x_{10}, x_{11}, x_{12}$)', '#c62828', '#ffebee')
]

for x_start, x_end, title, border_col, bg_col in clusters_meta:
    rect = mpatches.Rectangle((x_start, 0.65), x_end - x_start, 0.35,
                             facecolor=bg_col, edgecolor=border_col, linewidth=0.8, alpha=0.9)
    ax_top.add_patch(rect)
    ax_top.text((x_start + x_end)/2, 0.82, title, ha='center', va='center',
                fontsize=9.5, fontfamily='sans-serif', color='black')

# 绘制顶部树状图折线
def draw_cluster_dendro_top(ax, xs, col):
    # xs: 4个自变量横坐标
    # 底部连接线
    ax.plot([xs[0], xs[0]], [0, 0.3], color=col, lw=1.2)
    ax.plot([xs[1], xs[1]], [0, 0.3], color=col, lw=1.2)
    ax.plot([xs[0], xs[1]], [0.3, 0.3], color=col, lw=1.2)
    m1 = (xs[0] + xs[1]) / 2
    
    ax.plot([xs[2], xs[2]], [0, 0.2], color=col, lw=1.2)
    ax.plot([xs[3], xs[3]], [0, 0.2], color=col, lw=1.2)
    ax.plot([xs[2], xs[3]], [0.2, 0.2], color=col, lw=1.2)
    m2 = (xs[2] + xs[3]) / 2
    
    ax.plot([m1, m1], [0.3, 0.45], color=col, lw=1.2)
    ax.plot([m2, m2], [0.2, 0.45], color=col, lw=1.2)
    ax.plot([m1, m2], [0.45, 0.45], color=col, lw=1.2)
    return (m1 + m2) / 2

c_top1 = draw_cluster_dendro_top(ax_top, [0, 1, 2, 3], '#1e88e5')
c_top2 = draw_cluster_dendro_top(ax_top, [4, 5, 6, 7], '#2e7d32')
c_top3 = draw_cluster_dendro_top(ax_top, [8, 9, 10, 11], '#c62828')

# 顶层黑线连接 3 大聚类
ax_top.plot([c_top1, c_top1], [0.45, 0.60], color='black', lw=1.2)
ax_top.plot([c_top2, c_top2], [0.45, 0.55], color='black', lw=1.2)
ax_top.plot([c_top3, c_top3], [0.45, 0.55], color='black', lw=1.2)
ax_top.plot([c_top2, c_top3], [0.55, 0.55], color='black', lw=1.2)
m23 = (c_top2 + c_top3) / 2
ax_top.plot([m23, m23], [0.55, 0.60], color='black', lw=1.2)
ax_top.plot([c_top1, m23], [0.60, 0.60], color='black', lw=1.2)

ax_top.set_xlim(-0.5, 11.5)
ax_top.set_ylim(0, 1.05)

# 4.2 左侧树状图区域
ax_left = fig.add_axes([0.05, hm_y, 0.14, hm_h])
ax_left.axis('off')

def draw_cluster_dendro_left(ax, ys, col):
    ax.plot([0, 0.3], [ys[0], ys[0]], color=col, lw=1.2)
    ax.plot([0, 0.3], [ys[1], ys[1]], color=col, lw=1.2)
    ax.plot([0.3, 0.3], [ys[0], ys[1]], color=col, lw=1.2)
    m1 = (ys[0] + ys[1]) / 2
    
    ax.plot([0, 0.2], [ys[2], ys[2]], color=col, lw=1.2)
    ax.plot([0, 0.2], [ys[3], ys[3]], color=col, lw=1.2)
    ax.plot([0.2, 0.2], [ys[2], ys[3]], color=col, lw=1.2)
    m2 = (ys[2] + ys[3]) / 2
    
    ax.plot([0.3, 0.45], [m1, m1], color=col, lw=1.2)
    ax.plot([0.2, 0.45], [m2, m2], color=col, lw=1.2)
    ax.plot([0.45, 0.45], [m1, m2], color=col, lw=1.2)
    return (m1 + m2) / 2

c_left1 = draw_cluster_dendro_left(ax_left, [0, 1, 2, 3], '#1e88e5')
c_left2 = draw_cluster_dendro_left(ax_left, [4, 5, 6, 7], '#2e7d32')
c_left3 = draw_cluster_dendro_left(ax_left, [8, 9, 10, 11], '#c62828')

ax_left.plot([0.45, 0.60], [c_left1, c_left1], color='black', lw=1.2)
ax_left.plot([0.45, 0.55], [c_left2, c_left2], color='black', lw=1.2)
ax_left.plot([0.45, 0.55], [c_left3, c_left3], color='black', lw=1.2)
ax_left.plot([0.55, 0.55], [c_left2, c_left3], color='black', lw=1.2)
m23_l = (c_left2 + c_left3) / 2
ax_left.plot([0.55, 0.60], [m23_l, m23_l], color='black', lw=1.2)
ax_left.plot([0.60, 0.60], [c_left1, m23_l], color='black', lw=1.2)

ax_left.set_ylim(11.5, -0.5)  # 与 origin='upper' 保持一致
ax_left.set_xlim(1.05, 0)

# -------------------------------------------------------------
# 5. 右侧独立颜色条
# -------------------------------------------------------------
cbar_ax = fig.add_axes([0.89, hm_y, 0.026, hm_h])
cbar = fig.colorbar(im, cax=cbar_ax, ticks=np.linspace(-1.0, 1.0, 11))
cbar.ax.tick_params(labelsize=11, width=0.8, length=4)
cbar_ax.text(0.5, 1.05, 'Correlation\ncoefficient', transform=cbar_ax.transAxes,
             ha='center', va='bottom', fontsize=11, fontfamily='sans-serif')
for spine in cbar.ax.spines.values():
    spine.set_linewidth(0.8)

# -------------------------------------------------------------
# 6. 顶部标题与底部学术说明
# -------------------------------------------------------------
fig.text(hm_x + hm_w/2, 0.965, 'Hierarchical Clustering of Variables and Correlation Structure',
         ha='center', va='top', fontsize=16, fontweight='bold', fontfamily='sans-serif')
fig.text(hm_x + hm_w/2, 0.935, '(Pearson correlation coefficients)',
         ha='center', va='top', fontsize=12, fontstyle='italic', fontfamily='sans-serif', color='#37474f')

fig.text(hm_x + hm_w/2, 0.035,
         r'Note: Values in the upper triangle are Pearson correlation coefficients.  $* \ p < 0.05, \ ** \ p < 0.01, \ *** \ p < 0.001.$',
         ha='center', va='center', fontsize=10.5, fontfamily='sans-serif')

save_py_nature_figure(fig, FilePath(_args.output_dir) / "hierarchical_correlation_template")



