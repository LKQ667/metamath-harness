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
from scipy.ndimage import gaussian_filter
import os

# -------------------------------------------------------------
# 1. 学术排版与全局字体
# -------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'

fig = plt.figure(figsize=(11.8, 8.8), dpi=300)

# -------------------------------------------------------------
# 2. 定制顶刊小波相干谱色系 (Deep Blue - Ocean - Aqua - Warm Light Yellow)
# -------------------------------------------------------------
colors_wc = [
    (0.00, '#061a38'),
    (0.18, '#0b3c6d'),
    (0.35, '#196b99'),
    (0.52, '#35a4b7'),
    (0.70, '#75cfa7'),
    (0.85, '#c5e89b'),
    (1.00, '#ffffe0')
]
cmap_wc = LinearSegmentedColormap.from_list('wavelet_coherence', colors_wc, N=256)

# -------------------------------------------------------------
# 3. 构建时间-周期时频相干网格
# -------------------------------------------------------------
t = np.linspace(0, 260, 450)
log_p = np.linspace(-1.0, 2.0, 350)
T, LOG_P = np.meshgrid(t, log_p)
P = 10**LOG_P

# 3.1 主相干脊线 (Dominant Ridge) 物理中心轨迹
t_ridge = np.linspace(15, 245, 33)
log_p_ridge = (
    0.00
    - 0.04 * np.sin((t_ridge - 15) / 30)
    + 0.32 * np.sin(np.pi * (t_ridge - 25) / 165)**2
    - 0.08 * np.exp(-((t_ridge - 195) / 28)**2)
)

# 3.2 生成小波相干谱连续场
np.random.seed(42)
coherence = np.zeros_like(T)

# (1) 基础低频与微观湍流场 (高斯平滑连续底噪)
raw_noise = np.random.randn(*T.shape)
smooth_noise = gaussian_filter(raw_noise, sigma=[10, 14])
smooth_noise = (smooth_noise - smooth_noise.min()) / (smooth_noise.max() - smooth_noise.min())
coherence += 0.32 * smooth_noise

# (2) 沿主脊线的高相干带 (平滑窗过渡，杜绝截断阶跃)
interp_ridge = np.interp(t, t_ridge, log_p_ridge)
dist_to_ridge = np.abs(LOG_P - interp_ridge[None, :])
# 平滑 Hann 渐变窗
window_t = np.sin(np.pi * np.clip((t - 10.0) / 240.0, 0.0, 1.0))**0.5
ridge_envelope = window_t[None, :] * np.exp(- (dist_to_ridge / 0.22)**2)
ridge_amp = 0.90 + 0.06 * np.sin(T / 28)
coherence += ridge_amp * ridge_envelope

# (3) 局部特定物理特征岛屿
# 特征 A: 亚年尺度高相干区 (t~35, log_p~ -0.35, period~ 0.45)
island_a = np.exp(- ((T - 35.0)/8.5)**2 - ((LOG_P - (-0.35))/0.14)**2 )
coherence += 0.78 * island_a

# 特征 B: 瞬态高相干事件 (t~146, log_p~ 1.0, period~ 10.0)
island_b = np.exp(- ((T - 146.0)/16.0)**2 - ((LOG_P - 1.0)/0.20)**2 )
coherence += 0.88 * island_b

# 特征 C: 顶部与底部次级相干斑块
coherence += 0.52 * np.exp(- ((T - 132)/8)**2 - ((LOG_P - (-0.2))/0.15)**2 )
coherence += 0.48 * np.exp(- ((T - 22)/10)**2 - ((LOG_P - 0.7)/0.18)**2 )
coherence += 0.45 * np.exp(- ((T - 235)/12)**2 - ((LOG_P - 1.3)/0.18)**2 )
coherence += 0.40 * np.exp(- ((T - 162)/15)**2 - ((LOG_P - 1.5)/0.15)**2 )

# 限制至理论相干系数区间 [0.0, 1.0]
coherence = np.clip(coherence, 0.0, 1.0)

# -------------------------------------------------------------
# 4. 主图绘制
# -------------------------------------------------------------
ax = fig.add_axes([0.08, 0.22, 0.89, 0.66])

# 4.1 相干谱背景热力图
im = ax.pcolormesh(T, P, coherence, cmap=cmap_wc, vmin=0.0, vmax=1.0,
                   shading='gouraud', rasterized=True)

# 4.2 统计显著性等高线
cs_05 = ax.contour(T, P, coherence, levels=[0.76], colors='white',
                   linewidths=1.2, linestyles='solid')
cs_10 = ax.contour(T, P, coherence, levels=[0.60], colors='white',
                   linewidths=0.9, linestyles='dotted')

# 4.3 绘制主相干脊线 (Dominant Ridge)
p_ridge_vals = 10**log_p_ridge
ax.plot(t_ridge, p_ridge_vals, color='#ffee58', lw=2.4, zorder=10)
ax.plot(t_ridge, p_ridge_vals, marker='o', markersize=4.6, linestyle='none',
        markerfacecolor='#ffee58', markeredgecolor='#f57f17', markeredgewidth=0.8, zorder=11)

# -------------------------------------------------------------
# 5. 影响锥 (Cone of Influence, COI) - 平滑抛物线下凹曲线
# -------------------------------------------------------------
t_coi = np.linspace(0, 260, 500)
coi_p = np.full_like(t_coi, 150.0)

# 左侧支: t从 0 到 100，周期从 0.9 迅速上升到 100
mask_l = t_coi <= 96
# 物理 COI 在对数尺度下的平滑下凹曲线: 采用更高幂次使中高频保持通畅
coi_p[mask_l] = 0.9 * 10**(2.05 * (t_coi[mask_l] / 96.0)**2.6)

# 右侧支: t从 164 到 260
mask_r = t_coi >= 164
coi_p[mask_r] = 0.9 * 10**(2.05 * ((260.0 - t_coi[mask_r]) / 96.0)**2.6)

# 绘制 COI 白色虚线边界
ax.plot(t_coi[mask_l], coi_p[mask_l], color='white', linestyle='--', linewidth=1.4, zorder=12)
ax.plot(t_coi[mask_r], coi_p[mask_r], color='white', linestyle='--', linewidth=1.4, zorder=12)

# COI 阴影遮罩 (遮蔽边界效应区域)
ax.fill_between(t_coi, coi_p, 100, where=mask_l,
                color='#081426', alpha=0.58, zorder=9)
ax.fill_between(t_coi, coi_p, 100, where=mask_r,
                color='#081426', alpha=0.58, zorder=9)

# COI 文本标签
ax.text(15, 65, 'COI', color='#90a4ae', fontsize=11, fontfamily='sans-serif', ha='center', va='center')
ax.text(245, 65, 'COI', color='#90a4ae', fontsize=11, fontfamily='sans-serif', ha='center', va='center')

# -------------------------------------------------------------
# 6. 坐标轴与倒转对数刻度
# -------------------------------------------------------------
ax.set_yscale('log')
ax.set_ylim(100, 0.1)  # 倒转 Y 轴: 小周期在上方，大周期在下方
ax.set_xlim(0, 260)

ax.set_yticks([0.1, 1.0, 10.0, 100.0])
ax.set_yticklabels([r'$10^{-1}$', r'$10^0$', r'$10^1$', r'$10^2$'], fontsize=12)
ax.set_xticks(np.linspace(0, 250, 6))
ax.tick_params(axis='both', which='both', labelsize=12, width=0.8, length=4.5)

ax.set_xlabel('Time', fontsize=13, fontfamily='sans-serif', labelpad=6)
ax.set_ylabel('Period\n(same units as time)', fontsize=12, fontfamily='sans-serif', labelpad=8)

# -------------------------------------------------------------
# 7. 文字标注与指示箭头 (Annotations)
# -------------------------------------------------------------
# 1. 亚年尺度增强耦合
ax.annotate('Enhanced coupling\nat sub-annual scales',
            xy=(35, 0.45), xytext=(35, 0.22),
            arrowprops=dict(arrowstyle='->', lw=1.0, color='white'),
            fontsize=10.0, fontfamily='sans-serif', color='white', ha='center', va='bottom')

# 2. 年际尺度持续耦合
ax.annotate('Persistent coupling\nat inter-annual scales',
            xy=(195, 1.15), xytext=(185, 0.35),
            arrowprops=dict(arrowstyle='->', lw=1.0, color='white'),
            fontsize=10.0, fontfamily='sans-serif', color='white', ha='center', va='bottom')

# 3. 瞬态高相干事件
ax.annotate('Transient high coherence\nevent',
            xy=(156, 10.2), xytext=(168, 12.0),
            arrowprops=dict(arrowstyle='->', lw=1.0, color='white'),
            fontsize=10.0, fontfamily='sans-serif', color='white', ha='left', va='center')

# -------------------------------------------------------------
# 8. 图例区 (右上角半透明图例卡片)
# -------------------------------------------------------------
leg_elements = [
    plt.Line2D([0], [0], color='white', lw=1.2, linestyle='-', label=r'Significant ($p < 0.05$)'),
    plt.Line2D([0], [0], color='white', lw=1.0, linestyle=':', label=r'Significant ($p < 0.10$)'),
    plt.Line2D([0], [0], color='#ffee58', lw=2.2, marker='o', markersize=4.8,
               markerfacecolor='#ffee58', markeredgecolor='#f57f17', label='Dominant ridge'),
    plt.Line2D([0], [0], color='white', lw=1.2, linestyle='--', label='Cone of influence')
]
leg = ax.legend(handles=leg_elements, loc='upper right', frameon=True,
                facecolor='#061a38', edgecolor='#37474f', framealpha=0.85,
                fontsize=10.0, handlelength=2.5)
for text in leg.get_texts():
    text.set_color('white')

# -------------------------------------------------------------
# 9. 底部独立水平颜色条 (Colorbar)
# -------------------------------------------------------------
cbar_ax = fig.add_axes([0.08, 0.08, 0.89, 0.032])
cbar = fig.colorbar(im, cax=cbar_ax, orientation='horizontal',
                    ticks=np.linspace(0.0, 1.0, 6))
cbar.ax.tick_params(labelsize=11.5, width=0.8, length=4)
cbar_ax.set_xlabel('Wavelet Coherence', fontsize=12.5, fontfamily='sans-serif', labelpad=5)
for spine in cbar.ax.spines.values():
    spine.set_linewidth(0.8)

# -------------------------------------------------------------
# 10. 顶部主标题与副标题
# -------------------------------------------------------------
fig.text(0.525, 0.965, 'Time-Frequency Coupling Between Key Drivers and Response',
         ha='center', va='top', fontsize=17, fontweight='bold', fontfamily='sans-serif', color='#102027')
fig.text(0.525, 0.932, 'Wavelet Coherence with Significance Contours and Dominant Ridge',
         ha='center', va='top', fontsize=12, fontfamily='sans-serif', color='#37474f')

# -------------------------------------------------------------
# 11. 保存高质量成果图
# -------------------------------------------------------------
save_py_nature_figure(fig, FilePath(_args.output_dir) / "wavelet_coherence_template")



