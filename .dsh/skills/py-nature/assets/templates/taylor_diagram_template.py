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
import os

# -------------------------------------------------------------
# 1. 学术排版与字体配置
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

fig, ax = plt.subplots(figsize=(8.5, 8.5), dpi=300)
ax.set_aspect('equal')

# -------------------------------------------------------------
# 2. 坐标系与几何参数定义
# -------------------------------------------------------------
max_std = 2.0
obs_std = 1.0  # 观测真实值标准差基准

# 绘制外圈四分之一主圆弧 (标准差 = 2.0)
theta = np.linspace(0, np.pi / 2, 200)
ax.plot(max_std * np.cos(theta), max_std * np.sin(theta), color='#153564', linewidth=1.5, zorder=5)

# 绘制直角坐标主轴
ax.plot([0, max_std], [0, 0], color='#153564', linewidth=1.5, zorder=5)
ax.plot([0, 0], [0, max_std], color='#153564', linewidth=1.5, zorder=5)

# -------------------------------------------------------------
# 3. 绘制标准差 (Standard deviation) 同心参考圆弧 (0.5, 1.0, 1.5)
# -------------------------------------------------------------
std_levels = [0.5, 1.0, 1.5]
for s in std_levels:
    ax.plot(s * np.cos(theta), s * np.sin(theta), color='#9bb5c9', linestyle=':', linewidth=0.8, alpha=0.9, zorder=2)

# -------------------------------------------------------------
# 4. 绘制中心均方根误差 (Centered RMSD) 虚线弧 (圆心在 (obs_std, 0))
# -------------------------------------------------------------
rmsd_levels = [0.5, 1.0, 1.5]
phi = np.linspace(0, np.pi, 400)
for r_val in rmsd_levels:
    arc_x = obs_std + r_val * np.cos(phi)
    arc_y = r_val * np.sin(phi)
    # 裁剪在第一象限且不超过 max_std
    valid = (arc_x >= 0) & (arc_y >= 0) & (arc_x**2 + arc_y**2 <= max_std**2)
    ax.plot(arc_x[valid], arc_y[valid], color='#7d97aa', linestyle='--', linewidth=0.9, alpha=0.9, zorder=3)

# 标注 RMSD 刻度数字与文本
ax.text(0.10, 1.68, 'Centered RMSD', fontsize=12, fontstyle='italic', color='#7d97aa', ha='left', va='center')
ax.text(0.08, 1.54, '1.5', fontsize=11, fontstyle='italic', color='#7d97aa', ha='left', va='center')
ax.text(0.08, 1.04, '1.0', fontsize=11, fontstyle='italic', color='#7d97aa', ha='left', va='center')
ax.text(0.08, 0.54, '0.5', fontsize=11, fontstyle='italic', color='#7d97aa', ha='left', va='center')

# -------------------------------------------------------------
# 5. 绘制相关系数 (Correlation Coefficient) 辐射线、刻度与标注
# -------------------------------------------------------------
corr_ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.99, 1.0]
for r in corr_ticks:
    angle = np.arccos(r)
    # 原点发散的点线
    ax.plot([0, max_std * np.cos(angle)], [0, max_std * np.sin(angle)], 
            color='#9bb5c9', linestyle=':', linewidth=0.8, alpha=0.9, zorder=2)
    
    # 外圈短刻度线 (贯穿圆弧)
    tick_in = 0.02
    tick_out = 0.03
    x_in = (max_std - tick_in) * np.cos(angle)
    y_in = (max_std - tick_in) * np.sin(angle)
    x_out = (max_std + tick_out) * np.cos(angle)
    y_out = (max_std + tick_out) * np.sin(angle)
    ax.plot([x_in, x_out], [y_in, y_out], color='#153564', linewidth=1.2, zorder=6)
    
    # 刻度数字
    offset = 0.075
    tx = (max_std + offset) * np.cos(angle)
    ty = (max_std + offset) * np.sin(angle)
    label_str = f'{r:.2g}' if r in [0.95, 0.99] else f'{r:.1f}'
    ax.text(tx, ty, label_str, ha='center', va='center', fontsize=12, color='#0f2b4c')

# 弧线内侧文字 "Correlation coefficient" (斜向排布)
ax.text(1.48, 1.62, 'Correlation coefficient', rotation=-40, 
        ha='center', va='center', fontsize=13, color='#153564', fontfamily='sans-serif')

# -------------------------------------------------------------
# 6. 标准差主轴刻度与标签
# -------------------------------------------------------------
std_ticks = [0.0, 0.5, 1.0, 1.5, 2.0]
for st in std_ticks:
    # 横轴刻度
    ax.plot([st, st], [-0.025, 0.025], color='#153564', linewidth=1.2, zorder=6)
    ax.text(st, -0.08, f'{st:.1f}', ha='center', va='top', fontsize=12)
    
    # 纵轴刻度
    ax.plot([-0.025, 0.025], [st, st], color='#153564', linewidth=1.2, zorder=6)
    ax.text(-0.07, st, f'{st:.1f}', ha='right', va='center', fontsize=12)

ax.text(1.0, -0.16, 'Standard deviation', ha='center', va='top', fontsize=14)
ax.text(-0.16, 1.0, 'Standard deviation', ha='center', va='bottom', rotation=90, fontsize=14)

# -------------------------------------------------------------
# 7. 模型评估点精确位置匹配
# -------------------------------------------------------------
# 坐标严格复刻原图分布:
# Model A: std=0.74, R=0.78
# Model B: std=1.14, R=0.60
# Model C: std=0.71, R=0.50
# Model D: std=0.91, R=0.69
# Model E: std=0.61, R=0.92
# Model F: std=0.52, R=0.38
models = [
    ('Model A', 'o', '#10356e', 0.78, 0.74),
    ('Model B', 's', '#2677d9', 0.60, 1.14),
    ('Model C', '^', '#10808a', 0.50, 0.71),
    ('Model D', 'D', '#16a8c4', 0.69, 0.91),
    ('Model E', 'v', '#693cb7', 0.92, 0.61),
    ('Model F', '*', '#877acb', 0.38, 0.52)
]

for name, marker, color, r, s in models:
    ang = np.arccos(r)
    x = s * np.cos(ang)
    y = s * np.sin(ang)
    ms = 105 if marker != '*' else 160
    ax.scatter(x, y, marker=marker, color=color, s=ms, zorder=15, label=name)
    ax.text(x + 0.035, y, f'{name}', fontsize=11, color=color, va='center', zorder=16)

# 观测真值 (Observed): (1.0, 0.0)
ax.scatter(obs_std, 0.0, marker='o', facecolor='white', edgecolor='black', linewidth=1.8, s=85, zorder=20, label='Observed')
ax.text(obs_std, -0.055, 'Observed', ha='center', va='top', fontsize=10.5, color='black')

# -------------------------------------------------------------
# 8. 图例与排版
# -------------------------------------------------------------
legend = ax.legend(loc='upper right', bbox_to_anchor=(0.98, 0.98), frameon=True, 
                   framealpha=0.96, edgecolor='#cbd5e1', fontsize=11.5, 
                   handletextpad=0.8, borderpad=0.7, labelspacing=0.5)
legend.get_frame().set_linewidth(0.8)

ax.set_xlim(-0.25, 2.25)
ax.set_ylim(-0.25, 2.25)
ax.axis('off')

save_py_nature_figure(fig, FilePath(_args.output_dir) / "taylor_diagram_template")



