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
plt.rcParams['axes.linewidth'] = 0.9

fig = plt.figure(figsize=(11.5, 8.2), dpi=300)

# -------------------------------------------------------------
# 2. 模拟真实时变不确定性轨迹
# -------------------------------------------------------------
np.random.seed(101)
t = np.linspace(0, 50, 300)
n_trajs = 160

trajs = []
for _ in range(n_trajs):
    cluster_type = np.random.choice([1, 2, 3, 4], p=[0.28, 0.42, 0.18, 0.12])
    if cluster_type == 1:  # High growth
        drift = np.random.normal(0.12, 0.03)
        curve = 1.0 + drift * t + 0.0018 * t**2
    elif cluster_type == 2:  # Moderate growth
        drift = np.random.normal(0.065, 0.02)
        curve = 1.0 + drift * t + 0.0006 * t**2
    elif cluster_type == 3:  # Plateau
        curve = 1.0 + 1.8 * (1 - np.exp(-0.08 * t))
    else:  # Decline
        curve = 1.0 + (3.0 - 1.0) * np.exp(-0.02 * t) - 0.065 * t
        
    noise = np.cumsum(np.random.normal(0, 0.12, len(t))) * (0.05 + 0.05 * (t / 50.0)**1.2)
    trajs.append(curve + noise)

trajs = np.array(trajs)

# 分位数计算
p_median = np.median(trajs, axis=0)
p_25 = np.percentile(trajs, 25, axis=0)
p_75 = np.percentile(trajs, 75, axis=0)
p_15 = np.percentile(trajs, 15, axis=0)
p_85 = np.percentile(trajs, 85, axis=0)
p_05 = np.percentile(trajs, 5, axis=0)
p_95 = np.percentile(trajs, 95, axis=0)
p_025 = np.percentile(trajs, 2.5, axis=0)
p_975 = np.percentile(trajs, 97.5, axis=0)

# -------------------------------------------------------------
# 3. 绘制左侧主图
# -------------------------------------------------------------
# 主图位置: [left, bottom, width, height]
ax_main = fig.add_axes([0.08, 0.10, 0.64, 0.76])

# 3.1 绘制单条细线样本 (淡灰蓝)
for i in range(n_trajs):
    ax_main.plot(t, trajs[i], color='#c8d8e8', linewidth=0.55, alpha=0.45, zorder=1)

# 3.2 绘制由深至浅的预测区间带
ax_main.fill_between(t, p_025, p_975, color='#c2d9f2', alpha=0.75, zorder=2)
ax_main.fill_between(t, p_05, p_95, color='#92b8e3', alpha=0.75, zorder=3)
ax_main.fill_between(t, p_15, p_85, color='#588ecb', alpha=0.78, zorder=4)
ax_main.fill_between(t, p_25, p_75, color='#346ea8', alpha=0.85, zorder=5)

# 3.3 中位数主曲线
ax_main.plot(t, p_median, color='#0a1e3f', linewidth=2.4, zorder=6)

ax_main.set_xlim(0, 50)
ax_main.set_ylim(-2.0, 12.0)
ax_main.set_xticks([0, 10, 20, 30, 40, 50])
ax_main.set_yticks([-2, 0, 2, 4, 6, 8, 10, 12])
ax_main.set_xlabel('Time', fontsize=13.5, fontfamily='sans-serif', labelpad=6)
ax_main.set_ylabel('System output', fontsize=13.5, fontfamily='sans-serif', labelpad=6)
ax_main.tick_params(labelsize=11.5)

# 左上角图例
handles = [
    Line2D([0], [0], color='#0a1e3f', linewidth=2.4, label='Median forecast'),
    mpatches.Patch(facecolor='#346ea8', edgecolor='none', label='50% prediction interval'),
    mpatches.Patch(facecolor='#588ecb', edgecolor='none', label='70% prediction interval'),
    mpatches.Patch(facecolor='#92b8e3', edgecolor='none', label='90% prediction interval'),
    mpatches.Patch(facecolor='#c2d9f2', edgecolor='none', label='95% prediction interval'),
    Line2D([0], [0], color='#c8d8e8', linewidth=0.9, label='Simulated scenarios\n(individual trajectories)')
]
leg = ax_main.legend(handles=handles, loc='upper left', bbox_to_anchor=(0.02, 0.98),
                     frameon=True, framealpha=0.96, edgecolor='#b0bec5', fontsize=11, labelspacing=0.5)
leg.get_frame().set_linewidth(0.8)

# -------------------------------------------------------------
# 4. 右侧独立面板 (Scenario clusters)
# -------------------------------------------------------------
# 右侧外框与背景
box_left, box_bottom, box_width, box_height = 0.755, 0.065, 0.225, 0.81
rect = mpatches.Rectangle((box_left, box_bottom), box_width, box_height,
                         fill=False, edgecolor='#607d8b', linewidth=0.8, transform=fig.transFigure)
fig.patches.append(rect)

# 顶部面板标题
fig.text(box_left + box_width/2, box_bottom + box_height - 0.025,
         'Scenario clusters\n(representative trajectories)',
         ha='center', va='top', fontsize=11, fontfamily='sans-serif', color='black')

# 4 个小图的几何布局
sub_h = 0.105
sub_w = 0.175
sub_x = box_left + 0.025
y_starts = [0.65, 0.49, 0.33, 0.17]

clusters_info = [
    ('C1  High growth', '28%', '#0d47a1', '#bbdefb', 1.0 + 0.12 * t + 0.0006 * t**2, 0.9),
    ('C2  Moderate growth', '42%', '#e65100', '#ffe0b2', 1.0 + 0.06 * t + 0.0004 * t**2, 0.7),
    ('C3  Plateau', '18%', '#1b5e20', '#c8e6c9', 1.0 + 1.8 * (1 - np.exp(-0.08 * t)), 0.5),
    ('C4  Decline', '12%', '#b71c1c', '#ffcdd2', 3.8 - 0.06 * t, 0.4)
]

for idx, (title, pct, line_col, band_col, curve, spread) in enumerate(clusters_info):
    ax_sub = fig.add_axes([sub_x, y_starts[idx], sub_w, sub_h])
    
    # 绘制带状不确定性
    ax_sub.fill_between(t, curve - spread, curve + spread, color=band_col, alpha=0.55)
    ax_sub.plot(t, curve, color=line_col, linewidth=1.6)
    
    # 顶部文字
    fig.text(sub_x, y_starts[idx] + sub_h + 0.018, title,
             color=line_col, fontsize=9.5, fontweight='bold', fontfamily='sans-serif')
    fig.text(sub_x + 0.035, y_starts[idx] + sub_h + 0.004, pct,
             color='black', fontsize=9, fontfamily='sans-serif')
    
    ax_sub.set_xlim(0, 50)
    ax_sub.set_ylim(-0.5, 10.5)
    ax_sub.set_yticks([0, 5, 10])
    ax_sub.tick_params(labelsize=8.5, length=2.5)
    
    if idx == 3:
        ax_sub.set_xticks([0, 10, 20, 30, 40, 50])
        ax_sub.set_xlabel('Time', fontsize=9.5, fontfamily='sans-serif', labelpad=2)
    else:
        ax_sub.set_xticks([])

# 底部说明文本
fig.text(box_left + 0.015, box_bottom + 0.045,
         'Multiple plausible futures,\nquantified uncertainty,\ninterpretable scenario structure.',
         fontsize=9.2, fontstyle='italic', fontfamily='sans-serif', color='#263238', va='center')

# -------------------------------------------------------------
# 5. 顶部主标题与副标题
# -------------------------------------------------------------
fig.text(0.08, 0.945, 'Time-varying uncertainty and scenario clustering', 
         fontsize=16.5, fontweight='bold', fontfamily='sans-serif', ha='left')
fig.text(0.08, 0.915, 'Probabilistic forecast with prediction intervals and representative scenario groups', 
         fontsize=11.5, fontfamily='sans-serif', color='#37474f', ha='left')

save_py_nature_figure(fig, FilePath(_args.output_dir) / "forecast_uncertainty_scenarios_template")



