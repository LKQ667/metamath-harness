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
from matplotlib.colors import LogNorm, LinearSegmentedColormap
import os

# -------------------------------------------------------------
# 1. 学术排版与全局字体
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

fig = plt.figure(figsize=(11.5, 8.8), dpi=300)

# -------------------------------------------------------------
# 2. 定制顶刊 TDA 渐变色系 (Cyan - Teal - Ocean - Midnight Navy)
# -------------------------------------------------------------
colors_pers = [
    (0.00, '#d1eeea'),
    (0.20, '#76b7c4'),
    (0.45, '#2e86ab'),
    (0.70, '#1c527a'),
    (1.00, '#082244')
]
cmap_pers = LinearSegmentedColormap.from_list('persistence_cmap', colors_pers, N=256)
norm_pers = LogNorm(vmin=1e-2, vmax=1.5e1)

# -------------------------------------------------------------
# 3. 几何与阈值参数
# -------------------------------------------------------------
x_min, x_max = 0.0, 3.1
tau = 2.12  # 拓扑稳定阈值 (位于 2.0 略偏右)
tau_band = (1.84, 2.28)

# -------------------------------------------------------------
# 4. Panel (a) 贝蒂数演化曲线
# -------------------------------------------------------------
# 位置调整为留出顶部充足空间，彻底避免文字重叠
ax_a = fig.add_axes([0.08, 0.56, 0.81, 0.28])

eps_a = np.array([
    0.00, 0.06, 0.12, 0.18, 0.24, 0.30, 0.36, 0.42, 0.48, 0.55, 0.62, 0.70,
    0.80, 0.86, 0.92, 0.98, 1.05, 1.12, 1.20, 1.28, 1.38, 1.44, 1.50, 1.56,
    1.68, 1.76, 1.82, 1.88, 1.94, 2.00, 2.06, 2.12, 2.20, 2.30, 2.40, 2.50,
    2.60, 2.70, 2.80, 2.90, 3.00, 3.10
])

# beta_0: 初始约 120 个分支，随过滤尺度增加合并，至 2.0 处稳定为 1
beta_0 = 1.0 + 119.0 / (1.0 + np.exp(3.8 * (eps_a - 0.46)))
beta_0[eps_a >= 1.98] = 1.0

# beta_1: 环状空洞，峰值在 0.92
beta_1_peak = 7.2 * np.exp(-((eps_a - 0.92) / 0.55)**2)
beta_1 = np.maximum(0.28, beta_1_peak + 0.6 * np.exp(-((eps_a - 0.2) / 0.3)**2))
beta_1[eps_a >= 1.92] = 0.28

# beta_2: 空腔，峰值在 1.00
beta_2_peak = 1.65 * np.exp(-((eps_a - 1.00) / 0.38)**2)
beta_2 = np.maximum(0.20, beta_2_peak + 0.05 * np.sin(eps_a * 3))
beta_2[eps_a >= 1.88] = 0.25

col_b0 = '#082a54'  # 藏青
col_b1 = '#137575'  # 墨绿/水鸭青
col_b2 = '#6ba0c7'  # 浅钢蓝

ax_a.plot(eps_a, beta_0, color=col_b0, lw=1.5, marker='o', markersize=4.2,
          markerfacecolor=col_b0, markeredgecolor=col_b0, label=r'$\beta_0$ (components)')
ax_a.plot(eps_a, beta_1, color=col_b1, lw=1.5, marker='o', markersize=4.2,
          markerfacecolor=col_b1, markeredgecolor=col_b1, label=r'$\beta_1$ (loops)')
ax_a.plot(eps_a, beta_2, color=col_b2, lw=1.5, marker='o', markersize=4.2,
          markerfacecolor=col_b2, markeredgecolor=col_b2, label=r'$\beta_2$ (voids)')

ax_a.set_yscale('log')
ax_a.set_ylim(0.08, 200)
ax_a.set_xlim(x_min, x_max)
ax_a.set_ylabel(r'Betti Number  $\beta_k$', fontsize=12, fontfamily='sans-serif')
ax_a.set_yticks([0.1, 1, 10, 100])
ax_a.set_yticklabels([r'$10^{-1}$', r'$10^0$', r'$10^1$', r'$10^2$'], fontsize=11)
ax_a.tick_params(axis='both', which='both', labelsize=11, width=0.8, length=4)
ax_a.legend(loc='upper right', frameon=False, fontsize=10.5, handlelength=2.2)

# 阈值灰度带与虚线
ax_a.axvspan(tau_band[0], tau_band[1], color='#d9e5ec', alpha=0.6, zorder=0)
ax_a.axvline(tau, color='#546e7a', linestyle='--', linewidth=0.9, zorder=1)

# Panel (a) 顶部阈值文本 (向上平移，绝不与副标题冲突)
ax_a.text(tau, 210, 'Persistence\nthreshold  ' + r'$\tau$', ha='center', va='bottom',
          fontsize=10.0, fontfamily='sans-serif', color='#263238')

# 文本与箭头: "Topological signal stabilizes for \epsilon \ge \tau"
ax_a.text(2.55, 3.8, r'Topological signal' + '\n' + r'stabilizes for $\epsilon \geq \tau$',
          ha='center', va='bottom', fontsize=9.5, fontfamily='sans-serif', color='#263238')
ax_a.annotate('', xy=(2.90, 2.2), xytext=(2.20, 2.2),
             arrowprops=dict(arrowstyle='->', lw=1.0, color='#263238'))

# Panel (a) 标题
ax_a.text(-0.06, 1.05, '(a)  Betti numbers', transform=ax_a.transAxes,
          fontsize=13.0, fontweight='semibold', fontfamily='sans-serif', va='bottom')

# -------------------------------------------------------------
# 5. Panel (b) 持续同调条形码 (Persistence Barcodes)
# -------------------------------------------------------------
box_h = 0.088
box_gap = 0.022
y_base = 0.09

fig.text(0.08, 0.48, '(b)  Persistence barcodes',
         fontsize=13.0, fontweight='semibold', fontfamily='sans-serif', va='bottom')

ax_h0 = fig.add_axes([0.08, y_base + 2 * (box_h + box_gap), 0.81, box_h])
ax_h1 = fig.add_axes([0.08, y_base + 1 * (box_h + box_gap), 0.81, box_h])
ax_h2 = fig.add_axes([0.08, y_base, 0.81, box_h])

barcode_axes = [ax_h0, ax_h1, ax_h2]
labels_b = [
    r'$H_0$' + '\n' + r'(components)',
    r'$H_1$' + '\n' + r'(loops)',
    r'$H_2$' + '\n' + r'(voids)'
]

for ax, lbl in zip(barcode_axes, labels_b):
    ax.set_xlim(x_min, 3.0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axvspan(tau_band[0], tau_band[1], color='#d9e5ec', alpha=0.6, zorder=0)
    ax.axvline(tau, color='#546e7a', linestyle='--', linewidth=0.9, zorder=1)
    ax.set_ylabel(lbl, fontsize=10.5, fontfamily='sans-serif', rotation=0, labelpad=35, va='center')
    for spine in ax.spines.values():
        spine.set_color('#37474f')
        spine.set_linewidth(0.8)

ax_h2.set_xticks(np.linspace(0.0, 3.0, 7))
ax_h2.tick_params(axis='x', which='both', labelsize=11, width=0.8, length=4)
ax_h2.set_xlabel(r'Filtration  $\epsilon$', fontsize=12, fontfamily='sans-serif', labelpad=8)

# 5.1 H_0 条形码
h0_bars = [
    (0.0, 0.18), (0.0, 0.24), (0.0, 0.32), (0.0, 0.38), (0.0, 0.45),
    (0.0, 0.35), (0.0, 0.28), (0.0, 0.52), (0.0, 0.58), (0.0, 0.65),
    (0.0, 0.82), (0.0, 1.10), (0.0, 0.60), (0.0, 0.62), (0.0, 0.33)
]
h0_main = (0.0, 2.95)

n_h0 = len(h0_bars) + 1
y_h0 = np.linspace(0.85, 0.15, n_h0)

for i, (b, d) in enumerate(h0_bars[:5]):
    pers = d - b
    col = cmap_pers(norm_pers(pers))
    ax_h0.plot([b, d], [y_h0[i], y_h0[i]], color=col, lw=1.6, solid_capstyle='butt')

mid_idx = 5
pers_main = h0_main[1] - h0_main[0]
col_main = cmap_pers(norm_pers(pers_main))
ax_h0.plot([h0_main[0], h0_main[1]], [y_h0[mid_idx], y_h0[mid_idx]], color=col_main, lw=2.0, solid_capstyle='butt')
ax_h0.plot(h0_main[1], y_h0[mid_idx], marker='o', markersize=4.5, markerfacecolor=col_main, markeredgecolor=col_main)

for i, (b, d) in enumerate(h0_bars[5:]):
    idx = i + 6
    pers = d - b
    col = cmap_pers(norm_pers(pers))
    ax_h0.plot([b, d], [y_h0[idx], y_h0[idx]], color=col, lw=1.6, solid_capstyle='butt')

# 5.2 H_1 条形码
h1_bars = [
    (0.33, 1.20, True),
    (0.48, 1.20, False),
    (0.62, 1.62, True),
    (0.55, 1.80, True),
    (0.52, 1.50, True),
    (0.65, 1.50, True),
    (0.70, 1.50, True),
    (0.80, 1.50, False),
    (0.82, 1.98, True),
    (0.88, 1.50, True),
    (0.92, 1.48, False),
    (0.65, 2.32, True)  # 跨越阈值的最长 loop
]
y_h1 = np.linspace(0.88, 0.12, len(h1_bars))
for i, (b, d, has_dot) in enumerate(h1_bars):
    pers = d - b
    col = cmap_pers(norm_pers(pers))
    ax_h1.plot([b, d], [y_h1[i], y_h1[i]], color=col, lw=1.5, solid_capstyle='butt')
    if has_dot:
        ax_h1.plot(d, y_h1[i], marker='o', markersize=4.0, markerfacecolor=col, markeredgecolor=col)

# 5.3 H_2 条形码
h2_bars = [
    (1.20, 1.68, True),
    (0.90, 1.50, True),
    (1.10, 1.50, False),
    (1.35, 1.80, True),
    (1.48, 1.82, True),
    (1.45, 1.90, True),
    (1.10, 1.95, True),
    (1.45, 2.24, True)
]
y_h2 = np.linspace(0.85, 0.15, len(h2_bars))
for i, (b, d, has_dot) in enumerate(h2_bars):
    pers = d - b
    col = cmap_pers(norm_pers(pers))
    ax_h2.plot([b, d], [y_h2[i], y_h2[i]], color=col, lw=1.5, solid_capstyle='butt')
    if has_dot:
        ax_h2.plot(d, y_h2[i], marker='o', markersize=4.0, markerfacecolor=col, markeredgecolor=col)

# -------------------------------------------------------------
# 6. 右侧独立颜色条 (Colorbar)
# -------------------------------------------------------------
cbar_ax = fig.add_axes([0.925, y_base, 0.016, 3 * box_h + 2 * box_gap])
cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm_pers, cmap=cmap_pers), cax=cbar_ax)
cbar.set_ticks([1e-2, 1e-1, 1e0, 1e1])
cbar.set_ticklabels([r'$10^{-2}$', r'$10^{-1}$', r'$10^0$', r'$10^1$'])
cbar.ax.tick_params(labelsize=10.5, width=0.8, length=4)
cbar_ax.text(0.5, 1.04, 'Persistence', transform=cbar_ax.transAxes,
             ha='center', va='bottom', fontsize=11, fontfamily='sans-serif')
for spine in cbar.ax.spines.values():
    spine.set_linewidth(0.8)

# -------------------------------------------------------------
# 7. 顶部大标题与副标题
# -------------------------------------------------------------
fig.text(0.49, 0.965, 'Topological Robustness of Model State Space',
         ha='center', va='top', fontsize=17, fontweight='bold', fontfamily='sans-serif', color='#102027')
fig.text(0.49, 0.932, 'Persistent Homology across a Filtration of the State Space',
         ha='center', va='top', fontsize=12, fontfamily='sans-serif', color='#37474f')

# -------------------------------------------------------------
# 8. 保存高质量成果图
# -------------------------------------------------------------
save_py_nature_figure(fig, FilePath(_args.output_dir) / "persistent_homology_template")



