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
from matplotlib.lines import Line2D
import os

# -------------------------------------------------------------
# 1. 学术排版与字体配置
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['axes.linewidth'] = 1.0

fig, ax = plt.subplots(figsize=(9.8, 7.6), dpi=300)

# -------------------------------------------------------------
# 2. 生成多代种群解散点云与 Pareto 前沿曲线
# -------------------------------------------------------------
np.random.seed(42)

# 4 个关键阶段的前沿线 (精确拟合原图几何走势)
f_gen10_x = np.linspace(0.05, 1.50, 14)
f_gen10_y = 0.12 + 0.30 / (f_gen10_x + 0.13)

f_gen50_x = np.linspace(0.03, 1.53, 15)
f_gen50_y = 0.07 + 0.18 / (f_gen50_x + 0.10)

f_gen200_x = np.linspace(0.02, 1.48, 16)
f_gen200_y = 0.05 + 0.11 / (f_gen200_x + 0.07)

f_final_x = np.linspace(0.03, 1.48, 16)
f_final_y = 0.04 + 0.065 / (f_final_x + 0.03)

# 采样各代种群散点
def sample_cloud(fn, n_pts, scale):
    pts_x = np.random.uniform(0.03, 1.75, n_pts)
    y_base = fn(pts_x)
    pts_y = y_base + np.random.exponential(scale=scale, size=n_pts)
    valid = (pts_x <= 1.85) & (pts_y <= 1.95) & (pts_y >= 0.05)
    return pts_x[valid], pts_y[valid]

early_x, early_y = sample_cloud(lambda x: 0.12 + 0.30 / (x + 0.13), 850, 0.28)
mid_x, mid_y = sample_cloud(lambda x: 0.07 + 0.18 / (x + 0.10), 1100, 0.15)
late_x, late_y = sample_cloud(lambda x: 0.05 + 0.11 / (x + 0.07), 1300, 0.08)

# -------------------------------------------------------------
# 3. 绘制种群散点
# -------------------------------------------------------------
ax.scatter(early_x, early_y, s=15, color='#a8c8e8', alpha=0.55, edgecolors='none', zorder=2)
ax.scatter(mid_x, mid_y, s=15, color='#fbc48d', alpha=0.55, edgecolors='none', zorder=3)
ax.scatter(late_x, late_y, s=15, color='#f49b95', alpha=0.55, edgecolors='none', zorder=4)

# -------------------------------------------------------------
# 4. 绘制前沿曲线与特征数据点
# -------------------------------------------------------------
# Gen 10
ax.plot(f_gen10_x, f_gen10_y, linestyle='--', color='#1976d2', linewidth=1.6, 
        marker='o', markersize=4.8, zorder=6)

# Gen 50
ax.plot(f_gen50_x, f_gen50_y, linestyle='--', color='#f57c00', linewidth=1.6, 
        marker='o', markersize=4.8, zorder=7)

# Gen 200
ax.plot(f_gen200_x, f_gen200_y, linestyle='--', color='#d32f2f', linewidth=1.6, 
        marker='o', markersize=4.8, zorder=8)

# Final Gen 500
ax.plot(f_final_x, f_final_y, linestyle='-', color='black', linewidth=1.8, 
        marker='o', markersize=4.8, markerfacecolor='black', markeredgecolor='black', zorder=9)

# -------------------------------------------------------------
# 5. 文字标注与指示箭头 (精确匹配原图位置)
# -------------------------------------------------------------
ax.annotate('Gen 10', xy=(0.69, f_gen10_y[6]), xytext=(0.83, f_gen10_y[6] + 0.15),
            color='#0d47a1', fontsize=11, fontfamily='sans-serif',
            arrowprops=dict(arrowstyle='->', color='black', lw=0.9), zorder=12)

ax.annotate('Gen 50', xy=(0.44, f_gen50_y[4]), xytext=(0.53, f_gen50_y[4] + 0.14),
            color='#bf360c', fontsize=11, fontfamily='sans-serif',
            arrowprops=dict(arrowstyle='->', color='black', lw=0.9), zorder=12)

ax.annotate('Gen 200', xy=(0.34, f_gen200_y[4]), xytext=(0.42, f_gen200_y[4] + 0.13),
            color='#b71c1c', fontsize=11, fontfamily='sans-serif',
            arrowprops=dict(arrowstyle='->', color='black', lw=0.9), zorder=12)

ax.annotate('Final Pareto front\n(Gen 500)', xy=(0.28, f_final_y[4]), xytext=(0.11, f_final_y[4] - 0.22),
            color='black', fontsize=11, fontfamily='sans-serif',
            arrowprops=dict(arrowstyle='->', color='black', lw=0.9), zorder=12)

# -------------------------------------------------------------
# 6. 主图坐标轴与排版
# -------------------------------------------------------------
ax.set_xlim(0.0, 2.0)
ax.set_ylim(0.0, 2.0)
ax.set_xticks(np.linspace(0.0, 2.0, 11))
ax.set_yticks(np.linspace(0.0, 2.0, 11))
ax.set_xlabel('Objective 1 (min)', fontsize=13, fontfamily='sans-serif', labelpad=6)
ax.set_ylabel('Objective 2 (min)', fontsize=13, fontfamily='sans-serif', labelpad=6)
ax.set_title('Evolution of Pareto Front in Multi-Objective Optimization', fontsize=15, fontfamily='sans-serif', pad=15)
ax.tick_params(labelsize=11)

# 自定义高质量图例
legend_elements = [
    Line2D([0], [0], marker='o', color='w', label='Early generations\n(1 – 20)', markerfacecolor='#a8c8e8', markersize=10),
    Line2D([0], [0], marker='o', color='w', label='Middle generations\n(21 – 100)', markerfacecolor='#fbc48d', markersize=10),
    Line2D([0], [0], marker='o', color='w', label='Late generations\n(101 – 300)', markerfacecolor='#f49b95', markersize=10),
    Line2D([0], [0], color='#1976d2', linestyle='--', marker='o', markersize=5, label='Pareto front (Gen 10)'),
    Line2D([0], [0], color='#f57c00', linestyle='--', marker='o', markersize=5, label='Pareto front (Gen 50)'),
    Line2D([0], [0], color='#d32f2f', linestyle='--', marker='o', markersize=5, label='Pareto front (Gen 200)'),
    Line2D([0], [0], color='black', linestyle='-', marker='o', markersize=5, label='Final Pareto front (Gen 500)')
]

leg = ax.legend(handles=legend_elements, loc='lower right', bbox_to_anchor=(0.98, 0.26), 
                frameon=True, framealpha=0.96, edgecolor='#b0bec5', fontsize=10.5, labelspacing=0.55)
leg.get_frame().set_linewidth(0.8)

# -------------------------------------------------------------
# 7. 右上角内嵌子图 (Inset: Hypervolume Progression)
# -------------------------------------------------------------
inset_ax = ax.inset_axes([0.65, 0.65, 0.32, 0.31])

iters = np.logspace(0, 3, 200)
# 超体积理论收敛曲线
hv_mean = 0.70 * (1 - np.exp(-0.0035 * iters**1.12))
hv_std = 0.025 * np.exp(-0.0012 * iters)

inset_ax.plot(iters, hv_mean, color='black', linewidth=1.5)
inset_ax.fill_between(iters, hv_mean - hv_std, hv_mean + hv_std, color='#b0bec5', alpha=0.45)

inset_ax.set_xscale('log')
inset_ax.set_xlim(1.0, 1000)
inset_ax.set_ylim(0.0, 0.82)
inset_ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8])
inset_ax.set_xlabel('Iteration Number', fontsize=9.5, fontfamily='sans-serif', labelpad=2)
inset_ax.set_ylabel('Hypervolume', fontsize=9.5, fontfamily='sans-serif', labelpad=2)
inset_ax.set_title('Hypervolume Progression', fontsize=10.5, fontfamily='sans-serif', pad=4)
inset_ax.tick_params(labelsize=9)
inset_ax.set_facecolor('white')

# -------------------------------------------------------------
# 8. 保存图像
# -------------------------------------------------------------
save_py_nature_figure(fig, FilePath(_args.output_dir) / "optimization_pareto_evolution_template")



