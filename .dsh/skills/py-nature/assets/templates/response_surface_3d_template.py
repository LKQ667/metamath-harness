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
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d import proj3d
from matplotlib.colors import LinearSegmentedColormap
import os

# -------------------------------------------------------------
# 1. 学术排版与字体配置
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

# 渐变色卡: 极浅冰蓝-水青-深靛紫
colors = [
    (0.00, '#edf3fa'),  # 0.0: 极浅冰蓝
    (0.25, '#c5def5'),  # 0.25: 淡天蓝
    (0.50, '#65b9cd'),  # 0.5: 碧青
    (0.70, '#368abb'),  # 0.7: 湖蓝
    (0.85, '#3b4ea3'),  # 0.85: 蓝紫
    (1.00, '#431985')   # 1.0: 深靛紫
]
cmap = LinearSegmentedColormap.from_list('response_surf', [(p, c) for p, c in colors], N=64)

# -------------------------------------------------------------
# 2. 构造响应面网格与数学模型
# -------------------------------------------------------------
x = np.linspace(-3.0, 3.0, 70)
y = np.linspace(-3.0, 3.0, 70)
X, Y = np.meshgrid(x, y)

# 具有宽厚主峰与左侧侧翼隆起 (与原图形态 1:1 契合)
main_peak = 2.42 * np.exp(-0.16 * (X**2 + Y**2))
shoulder = 0.52 * np.exp(-1.1 * ((X + 1.6)**2 + (Y - 0.2)**2))
Z = main_peak + shoulder
Z = np.clip(Z, 0.0, 2.5)

# -------------------------------------------------------------
# 3. 3D 绘图与渲染
# -------------------------------------------------------------
fig = plt.figure(figsize=(9.2, 7.6), dpi=300)
ax = fig.add_subplot(111, projection='3d')

# 绘制 3D 响应面
surf = ax.plot_surface(X, Y, Z, cmap=cmap, rstride=1, cstride=1,
                       edgecolor='#829cb8', linewidth=0.22,
                       antialiased=True, alpha=0.88, shade=False, zorder=3)

# 底部 z=0 投影 2D 等高线
contour_levels = np.linspace(0.15, 2.35, 15)
ax.contour(X, Y, Z, zdir='z', offset=0.0, levels=contour_levels, 
           cmap=cmap, linewidths=0.85, zorder=2)

# -------------------------------------------------------------
# 4. 最优解 (Optimal solution) 标记与垂直垂线
# -------------------------------------------------------------
opt_x, opt_y = 0.0, 0.0
opt_z = 2.42

# 垂直垂线与投影基点
ax.plot([opt_x, opt_x], [opt_y, opt_y], [0.0, opt_z], color='black', linestyle='--', linewidth=1.0, zorder=8)
ax.scatter([opt_x], [opt_y], [0.0], s=16, color='black', zorder=9)

# 峰值白色圆点
ax.scatter([opt_x], [opt_y], [opt_z], s=42, facecolor='white', edgecolor='black', linewidth=1.2, zorder=12)

# -------------------------------------------------------------
# 5. 坐标轴、网格与视角定制
# -------------------------------------------------------------
ax.set_xlim(-3.0, 3.0)
ax.set_ylim(-3.0, 3.0)
ax.set_zlim(0.0, 2.5)

ax.set_xticks([-3, -2, -1, 0, 1, 2, 3])
ax.set_yticks([-3, -2, -1, 0, 1, 2, 3])
ax.set_zticks([0.0, 0.5, 1.0, 1.5, 2.0, 2.5])

ax.set_xlabel(r'$x_1$', fontsize=14, labelpad=6)
ax.set_ylabel(r'$x_2$', fontsize=14, labelpad=6)
ax.set_zlabel('Robustness index', fontsize=13, labelpad=8)

# 设定视角: 仰角 25度，方位角 -60度
ax.view_init(elev=25, azim=-60)

# 背景面板设定
ax.xaxis.pane.set_facecolor((0.98, 0.98, 0.98, 0.4))
ax.yaxis.pane.set_facecolor((0.98, 0.98, 0.98, 0.4))
ax.zaxis.pane.set_facecolor((0.98, 0.98, 0.98, 0.4))

ax.xaxis.pane.set_edgecolor('#d8e0e8')
ax.yaxis.pane.set_edgecolor('#d8e0e8')
ax.zaxis.pane.set_edgecolor('#d8e0e8')
ax.grid(color='#d8e0e8', linestyle='-', linewidth=0.5)

# -------------------------------------------------------------
# 6. 注释与箭头 (利用 2D 像素投射精准标注 Optimal solution)
# -------------------------------------------------------------
plt.draw()
# 获取 3D 点在 2D 画布上的投影坐标
x2, y2, _ = proj3d.proj_transform(opt_x, opt_y, opt_z, ax.get_proj())
# 将标准化坐标转换为像素坐标，并使用 annotate 绘制清晰箭头与文本
ax.annotate('Optimal solution',
            xy=(x2, y2), xycoords='data',
            xytext=(x2 + 0.12, y2 + 0.08), textcoords='data',
            fontsize=12, fontfamily='sans-serif',
            arrowprops=dict(facecolor='black', arrowstyle='->', lw=1.0),
            zorder=20)

# -------------------------------------------------------------
# 7. 独立颜色条排版
# -------------------------------------------------------------
cbar_ax = fig.add_axes([0.88, 0.18, 0.026, 0.64])
cbar = fig.colorbar(surf, cax=cbar_ax, ticks=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5])
cbar.ax.tick_params(labelsize=11, width=0.8, length=4)
cbar.set_label('Robustness index', fontsize=13, fontfamily='sans-serif', labelpad=10)
for spine in cbar.ax.spines.values():
    spine.set_linewidth(0.8)

save_py_nature_figure(fig, FilePath(_args.output_dir) / "response_surface_3d_template")



