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

fig, ax = plt.subplots(figsize=(10.5, 7.8), dpi=300)

# -------------------------------------------------------------
# 2. 坐标轴定义与范围配置 (8 个维度)
# -------------------------------------------------------------
axes_info = [
    (r'$x_1$', 0.0, 1.0, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], '{:.1f}'),
    (r'$x_2$', -2.0, 2.0, [-2, -1, 0, 1, 2], '{:d}'),
    (r'$x_3$', -3.0, 3.0, [-3, -2, -1, 0, 1, 2, 3], '{:d}'),
    (r'$x_4$', 0.0, 2.0, [0.0, 0.5, 1.0, 1.5, 2.0], '{:.1f}'),
    (r'$x_5$', -1.0, 1.0, [-1.0, -0.5, 0.0, 0.5, 1.0], '{:.1f}'),
    ('Cost', 0.0, 100.0, [0, 20, 40, 60, 80, 100], '{:d}'),
    ('Risk', 0.0, 1.0, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], '{:.1f}'),
    ('Stability', 0.0, 1.0, [0.0, 0.2, 0.4, 0.6, 0.8, 1.0], '{:.1f}')
]

n_axes = len(axes_info)

def normalize(val, v_min, v_max):
    return (val - v_min) / (v_max - v_min)

# 经典平行坐标平滑 Bézier S-曲线生成
def bezier_curve(y_vals, n_pts=60):
    all_x = []
    all_y = []
    t = np.linspace(0, 1, n_pts)
    for i in range(len(y_vals) - 1):
        x0, y0 = i, y_vals[i]
        x3, y3 = i + 1, y_vals[i + 1]
        x1, y1 = i + 0.45, y0
        x2, y2 = i + 0.55, y3
        # 三次贝塞尔公式
        bx = (1 - t)**3 * x0 + 3 * (1 - t)**2 * t * x1 + 3 * (1 - t) * t**2 * x2 + t**3 * x3
        by = (1 - t)**3 * y0 + 3 * (1 - t)**2 * t * y1 + 3 * (1 - t) * t**2 * y2 + t**3 * y3
        all_x.extend(bx[:-1])
        all_y.extend(by[:-1])
    all_x.append(len(y_vals) - 1)
    all_y.append(y_vals[-1])
    return np.array(all_x), np.array(all_y)

# -------------------------------------------------------------
# 3. 构造背景解空间与显著最优解束
# -------------------------------------------------------------
np.random.seed(42)
n_samples = 480

norm_samples = []
for _ in range(n_samples):
    y_norm = np.zeros(n_axes)
    # 随机采样并赋予相关性
    y_norm[0] = np.random.uniform(0.05, 0.95)
    y_norm[1] = np.clip(0.5 * y_norm[0] + np.random.normal(0.2, 0.25), 0.05, 0.95)
    y_norm[2] = np.clip(0.9 - 0.7 * y_norm[1] + np.random.normal(0, 0.22), 0.05, 0.95)
    y_norm[3] = np.clip(0.6 * y_norm[0] + 0.3 * y_norm[1] + np.random.normal(0, 0.18), 0.05, 0.95)
    y_norm[4] = np.clip(0.5 - 0.3 * (y_norm[3] - 0.5) + np.random.normal(0, 0.2), 0.05, 0.95)
    y_norm[5] = np.clip(0.85 - 0.5 * y_norm[3] + np.random.normal(0, 0.2), 0.05, 0.95)
    y_norm[6] = np.clip(0.7 - 0.4 * y_norm[4] + np.random.normal(0, 0.2), 0.05, 0.95)
    y_norm[7] = np.clip(0.3 + 0.5 * (1.0 - y_norm[5]) + np.random.normal(0, 0.2), 0.05, 0.95)
    norm_samples.append(y_norm)

norm_samples = np.array(norm_samples)

# -------------------------------------------------------------
# 4. 绘制背景曲线
# -------------------------------------------------------------
for i in range(n_samples):
    bx, by = bezier_curve(norm_samples[i])
    if np.random.rand() > 0.4:
        c = '#cae9f7'  # 浅冰蓝
        alpha = 0.13
    else:
        c = '#dedcf7'  # 浅紫
        alpha = 0.11
    ax.plot(bx, by, color=c, linewidth=0.65, alpha=alpha, zorder=1)

# -------------------------------------------------------------
# 5. 绘制中层过渡带与 Pareto 最优解束
# -------------------------------------------------------------
# 目标最优解形态 (精准匹配原图高亮线条的纵坐标位置)
# x1~0.47, x2~0.68, x3~0.43, x4~0.63, x5~0.42, Cost~0.18, Risk~0.22, Stability~0.82
base_opt = np.array([0.47, 0.68, 0.43, 0.63, 0.42, 0.18, 0.22, 0.82])

# 中层青蓝半透明过渡带
for _ in range(75):
    noise = np.random.normal(0, 0.038, n_axes)
    y_band = np.clip(base_opt + noise, 0.02, 0.98)
    bx, by = bezier_curve(y_band)
    ax.plot(bx, by, color='#7ecae5', linewidth=1.1, alpha=0.18, zorder=2)

# 精选 5 条核心高亮 Pareto 曲线 (深墨绿青)
pareto_lines = [
    base_opt + np.array([-0.02, 0.015, 0.02, 0.01, -0.015, 0.015, -0.02, 0.02]),
    base_opt + np.array([0.015, -0.01, -0.015, 0.02, 0.01, -0.01, 0.015, -0.015]),
    base_opt + np.array([0.00, 0.00, 0.00, -0.015, -0.01, 0.00, 0.00, 0.00]),
    base_opt + np.array([-0.015, -0.02, 0.01, -0.01, 0.015, -0.015, 0.01, 0.03]),
    base_opt + np.array([0.02, 0.01, -0.02, 0.015, -0.02, 0.02, -0.015, -0.02])
]

for p_line in pareto_lines:
    bx, by = bezier_curve(p_line)
    ax.plot(bx, by, color='#0a4d61', linewidth=1.8, alpha=0.96, zorder=4)

# -------------------------------------------------------------
# 6. 绘制垂直轴、刻度线与标注
# -------------------------------------------------------------
for i, (name, v_min, v_max, ticks, fmt) in enumerate(axes_info):
    # 垂直主轴
    ax.plot([i, i], [0, 1], color='black', linewidth=1.2, zorder=6)
    
    # 顶部坐标标题
    ax.text(i, 1.035, name, ha='center', va='bottom', fontsize=13.5, fontfamily='sans-serif')
    
    # 刻度线与标签
    for t in ticks:
        norm_t = normalize(t, v_min, v_max)
        ax.plot([i - 0.045, i], [norm_t, norm_t], color='black', linewidth=1.0, zorder=6)
        label_text = fmt.format(t)
        ax.text(i - 0.07, norm_t, label_text, ha='right', va='center', fontsize=11, fontfamily='sans-serif')

# -------------------------------------------------------------
# 7. 排版与输出
# -------------------------------------------------------------
ax.set_xlim(-0.55, n_axes - 0.45)
ax.set_ylim(-0.04, 1.08)
ax.axis('off')

save_py_nature_figure(fig, FilePath(_args.output_dir) / "parallel_coordinates_template")



