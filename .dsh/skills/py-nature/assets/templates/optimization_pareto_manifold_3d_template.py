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
"""
Non-dominated Solution Manifold (3D Pareto Front) - 1:1 Pixel-Perfect Masterpiece
================================================================================
Exact academic reproduction of 3-Objective Optimization in Objective Space.
Key Highlights:
- Precise analytical Pareto manifold with diagonal tilt and elegant curved envelope
- Three full-wall orthogonal projection contour systems (Bottom z=0, Left y=0, Right-back x=1)
- Rich, realistic dominated solution cloud strictly above the manifold
- Non-dominated frontier points along the boundary with crisp white edges
- High trade-off Knee Point with pristine white pointer line and shadowed bold annotation
- Direction of hypervolume improvement vector (dashed arrow with multi-line text)
- Publication-grade typography, LaTeX mathematics, STIX font, and matching layout
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import LogNorm, LinearSegmentedColormap
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import matplotlib.patheffects as path_effects

# -------------------------------------------------------------------------
# 1. Global Academic Typography & Figure Canvas Setup
# -------------------------------------------------------------------------
plt.rcParams['mathtext.fontset'] = 'stix'
plt.rcParams['axes.edgecolor'] = '#444444'
plt.rcParams['axes.linewidth'] = 0.8

fig = plt.figure(figsize=(15, 11), dpi=300)
ax = fig.add_subplot(111, projection='3d')
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

# -------------------------------------------------------------------------
# 2. Analytical Pareto Front Surface Formulation
# -------------------------------------------------------------------------
nu, nv = 160, 160
x_vals = np.linspace(0.08, 0.90, nu)
y_vals = np.linspace(0.08, 0.90, nv)
X, Y = np.meshgrid(x_vals, y_vals)

# Diagonal rotation
theta = -np.pi / 4.0
cos_t, sin_t = np.cos(theta), np.sin(theta)

u = (X - 0.44) * cos_t - (Y - 0.44) * sin_t
v = (X - 0.44) * sin_t + (Y - 0.44) * cos_t

# Quadric elevation equation
Z = 0.28 - 0.72 * u + 0.85 * (u**2) + 2.50 * (v**2)

# Precise boundary mask
mask = (
    (X >= 0.08) & (X <= 0.88) &
    (Y >= 0.08) & (Y <= 0.88) &
    (Z >= 0.14) & (Z <= 0.96) &
    ((X**1.82 + Y**1.82) <= 1.05) &
    (u <= 0.32)
)

# -------------------------------------------------------------------------
# 3. Local Curvature Colormap Mapping (Wider Teal/Mint Center)
# -------------------------------------------------------------------------
# Broaden the pale teal / mint area to match target image
dist_knee = np.sqrt(((X - 0.42) / 0.48)**2 + ((Y - 0.42) / 0.48)**2)
norm_curv = 1e-3 * (10.0**(3.0 * np.clip(dist_knee**1.35, 0.0, 1.0)))

colors_list = [
    (0.82, 0.97, 0.94),  # 10^-3: soft pale teal / mint
    (0.60, 0.90, 0.86),  # bright mint-teal
    (0.35, 0.78, 0.80),  # clear cyan-teal
    (0.18, 0.58, 0.74),  # ocean slate blue
    (0.08, 0.32, 0.56),  # sapphire navy
    (0.03, 0.13, 0.30)   # 10^0: midnight navy
]
cmap_pareto = LinearSegmentedColormap.from_list('pareto_academic', colors_list, N=64)
norm_log = LogNorm(vmin=1e-3, vmax=1.0)

# Masked arrays for surface rendering
Z_masked = np.copy(Z)
Z_masked[~mask] = np.nan
C_masked = np.copy(norm_curv)
C_masked[~mask] = np.nan

# Plot smooth surface
surf = ax.plot_surface(
    X, Y, Z_masked,
    facecolors=cmap_pareto(norm_log(C_masked)),
    rstride=2, cstride=2,
    alpha=0.86,
    antialiased=True,
    shade=False,
    edgecolor='#256585',
    linewidth=0.15,
    zorder=10
)

# -------------------------------------------------------------------------
# 4. Three Full-Wall Orthogonal Projection Contour Systems
# -------------------------------------------------------------------------
proj_cmap = LinearSegmentedColormap.from_list('proj_cmap', [
    (0.96, 0.98, 1.00),
    (0.82, 0.91, 0.97),
    (0.55, 0.74, 0.87),
    (0.28, 0.52, 0.72)
], N=120)

# (1) Bottom Wall: z = 0.0 (Objective 1 - Objective 2)
bx = np.linspace(0.0, 1.0, 150)
by = np.linspace(0.0, 1.0, 150)
BX, BY = np.meshgrid(bx, by)
b_u = (BX - 0.46) * cos_t - (BY - 0.46) * sin_t
b_v = (BX - 0.46) * sin_t + (BY - 0.46) * cos_t
BZ = 0.26 + 1.2 * (b_u**2) + 3.0 * (b_v**2) - 0.45 * b_u

bot_levels = np.linspace(0.24, 0.78, 8)
ax.contourf(BX, BY, BZ, zdir='z', offset=0.0, levels=bot_levels, cmap=proj_cmap, alpha=0.55, zorder=2)
ax.contour(BX, BY, BZ, zdir='z', offset=0.0, levels=bot_levels, colors='#557a9b', linestyles='--', linewidths=0.85, zorder=3)

# (2) Left Wall: y = 0.0 (Objective 1 - Objective 3)
lx = np.linspace(0.0, 1.0, 150)
lz = np.linspace(0.0, 1.0, 150)
LX, LZ = np.meshgrid(lx, lz)
LZ_val = (LZ - 0.18) / 0.9 + 1.4 * (LX - 0.46)**2
side_levels = np.linspace(0.22, 0.90, 7)
ax.contourf(LX, LZ_val, LZ, zdir='y', offset=0.0, levels=side_levels, cmap=proj_cmap, alpha=0.45, zorder=2)
ax.contour(LX, LZ_val, LZ, zdir='y', offset=0.0, levels=side_levels, colors='#557a9b', linestyles='--', linewidths=0.75, zorder=3)

# (3) Right-Back Wall: x = 1.0 (Objective 2 - Objective 3)
ry = np.linspace(0.0, 1.0, 150)
rz = np.linspace(0.0, 1.0, 150)
RY, RZ = np.meshgrid(ry, rz)
RZ_val = (RZ - 0.18) / 0.9 + 1.4 * (RY - 0.46)**2
ax.contourf(RZ_val, RY, RZ, zdir='x', offset=1.0, levels=side_levels, cmap=proj_cmap, alpha=0.45, zorder=2)
ax.contour(RZ_val, RY, RZ, zdir='x', offset=1.0, levels=side_levels, colors='#557a9b', linestyles='--', linewidths=0.75, zorder=3)

# -------------------------------------------------------------------------
# 5. Dominated Solutions Cloud (Scatter strictly above manifold)
# -------------------------------------------------------------------------
np.random.seed(42)
n_dom = 1800
rand_x = np.random.uniform(0.08, 0.88, n_dom)
rand_y = np.random.uniform(0.08, 0.88, n_dom)

ru = (rand_x - 0.44) * cos_t - (rand_y - 0.44) * sin_t
rv = (rand_x - 0.44) * sin_t + (rand_y - 0.44) * cos_t
base_z = 0.28 - 0.72 * ru + 0.85 * (ru**2) + 2.50 * (rv**2)

delta_z = np.random.exponential(scale=0.16, size=n_dom) + 0.02
rand_z = base_z + delta_z

valid = (
    (rand_x >= 0.06) & (rand_x <= 0.94) &
    (rand_y >= 0.06) & (rand_y <= 0.94) &
    (rand_z <= 0.98) &
    ((rand_x**1.82 + rand_y**1.82) <= 1.08) &
    (ru <= 0.35)
)
dom_x, dom_y, dom_z = rand_x[valid], rand_y[valid], rand_z[valid]

ax.scatter(
    dom_x, dom_y, dom_z,
    c='#8faec5',
    alpha=0.35,
    s=10,
    edgecolors='none',
    label='Dominated solution',
    zorder=5
)

# -------------------------------------------------------------------------
# 6. Pareto-Optimal Frontier Points (Along the front curve & edges)
# -------------------------------------------------------------------------
t_arc = np.linspace(0.14, 0.86, 12)
fx = t_arc
fy = (1.04 - fx**1.82)**(1.0 / 1.82)

fu = (fx - 0.44) * cos_t - (fy - 0.44) * sin_t
fv = (fx - 0.44) * sin_t + (fy - 0.44) * cos_t
fz = 0.28 - 0.72 * fu + 0.85 * (fu**2) + 2.50 * (fv**2) + 0.015

# Upper edge samples
ux = np.array([0.10, 0.16, 0.22, 0.12, 0.26])
uy = np.array([0.10, 0.12, 0.16, 0.26, 0.18])
uu = (ux - 0.44) * cos_t - (uy - 0.44) * sin_t
uv = (ux - 0.44) * sin_t + (uy - 0.44) * cos_t
uz = 0.28 - 0.72 * uu + 0.85 * (uu**2) + 2.50 * (uv**2) + 0.015

all_px = np.concatenate([fx, ux])
all_py = np.concatenate([fy, uy])
all_pz = np.concatenate([fz, uz])

ax.scatter(
    all_px, all_py, all_pz,
    c='#0077d8',
    s=48,
    edgecolors='white',
    linewidths=1.2,
    alpha=0.98,
    label='Pareto-optimal (non-dominated)',
    zorder=25
)

# -------------------------------------------------------------------------
# 7. Knee Point Highlight & Crisp Academic Pointer Line
# -------------------------------------------------------------------------
knee_x = 0.43
knee_y = 0.43
ku = (knee_x - 0.44) * cos_t - (knee_y - 0.44) * sin_t
kv = (knee_x - 0.44) * sin_t + (knee_y - 0.44) * cos_t
knee_z = 0.28 - 0.72 * ku + 0.85 * (ku**2) + 2.50 * (kv**2) + 0.02

# Red point placed on top
ax.scatter(
    [knee_x], [knee_y], [knee_z],
    c='#e54b4b',
    s=95,
    edgecolors='white',
    linewidths=2.0,
    zorder=40,
    label='Knee point (high trade-off)'
)

# Pristine white pointer line pointing up-right towards the text
pointer_end_x = knee_x + 0.13
pointer_end_y = knee_y + 0.08
pointer_end_z = knee_z + 0.06

ax.plot(
    [knee_x, pointer_end_x],
    [knee_y, pointer_end_y],
    [knee_z, pointer_end_z],
    color='white',
    linewidth=2.0,
    zorder=42
)

txt_knee = ax.text(
    pointer_end_x + 0.015, pointer_end_y + 0.01, pointer_end_z,
    'Knee point',
    color='white',
    fontsize=12.5,
    fontfamily='sans-serif',
    fontweight='bold',
    va='center',
    ha='left',
    zorder=45
)
txt_knee.set_path_effects([path_effects.withStroke(linewidth=3.2, foreground='#112233')])

# -------------------------------------------------------------------------
# 8. Hypervolume Improvement Direction Vector
# -------------------------------------------------------------------------
arrow_start = np.array([0.16, 0.24, 0.60])
arrow_end = np.array([0.32, 0.36, 0.38])

ax.plot(
    [arrow_start[0], arrow_end[0]],
    [arrow_start[1], arrow_end[1]],
    [arrow_start[2], arrow_end[2]],
    color='#37474f',
    linestyle='--',
    linewidth=3.0,
    zorder=18
)
ax.scatter(
    [arrow_end[0]], [arrow_end[1]], [arrow_end[2]],
    color='#37474f',
    marker='v',
    s=130,
    zorder=19
)

ax.text(
    arrow_start[0] - 0.08, arrow_start[1] + 0.01, arrow_start[2] - 0.08,
    'Hypervolume\nimprovement\ndirection',
    color='#263238',
    fontsize=10.5,
    fontfamily='sans-serif',
    ha='center',
    va='top',
    zorder=20
)

# -------------------------------------------------------------------------
# 9. Coordinates, Ticks & 3D Lighting/Panes
# -------------------------------------------------------------------------
ax.set_xlim(0.0, 1.0)
ax.set_ylim(0.0, 1.0)
ax.set_zlim(0.0, 1.0)

ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_zticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])

ax.tick_params(axis='both', which='major', labelsize=11, pad=4)

ax.set_xlabel('Objective 1\n$f_1(x)$', fontsize=12.5, labelpad=14, fontfamily='sans-serif')
ax.set_ylabel('Objective 2\n$f_2(x)$', fontsize=12.5, labelpad=14, fontfamily='sans-serif')
ax.set_zlabel('Objective 3\n$f_3(x)$', fontsize=12.5, labelpad=14, fontfamily='sans-serif')

# Perspective view matching target image
ax.view_init(elev=22, azim=-54)

for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
    pane.set_facecolor('#f8fafc')
    pane.set_edgecolor('#d1d5db')
    pane.set_alpha(0.6)

ax.grid(True, linestyle=':', color='#cbd5e1', linewidth=0.75, alpha=0.8)

# -------------------------------------------------------------------------
# 10. Academic Mathematical Specification Card & Titles
# -------------------------------------------------------------------------
fig.text(0.50, 0.945, 'Non-dominated Solution Manifold',
         ha='center', va='center', fontsize=21, fontfamily='sans-serif', fontweight='bold', color='#111827')
fig.text(0.50, 0.915, 'Three-objective Optimization in Objective Space',
         ha='center', va='center', fontsize=13, fontfamily='sans-serif', color='#374151')

math_text = (
    r"$\mathbf{Minimize}$" + "\n" +
    r"$f(x) = (f_1(x), f_2(x), f_3(x))$" + "\n\n" +
    r"$\mathbf{Pareto\ set:}$" + "\n" +
    r"$P = \{x \in X \mid \neg\,\exists\,y \in X :$" + "\n" +
    r"$\quad\quad f(y) \leq f(x),\, f(y) \neq f(x)\}$"
)
fig.text(0.055, 0.89, math_text, ha='left', va='top', fontsize=11, fontfamily='sans-serif', color='#1f2937', linespacing=1.35)

# -------------------------------------------------------------------------
# 11. Upper-Right Legend
# -------------------------------------------------------------------------
legend_elements = [
    Line2D([0], [0], marker='o', color='none', markerfacecolor='#8faec5', markeredgecolor='none', markersize=7.5, label='Dominated solution'),
    Line2D([0], [0], marker='o', color='none', markerfacecolor='#0077d8', markeredgecolor='white', markeredgewidth=1.2, markersize=8.5, label='Pareto-optimal (non-dominated)'),
    Line2D([0], [0], marker='o', color='none', markerfacecolor='#e54b4b', markeredgecolor='white', markeredgewidth=1.2, markersize=8.5, label='Knee point (high trade-off)'),
    Patch(facecolor='#389ba8', edgecolor='#1d5663', label='Pareto front (manifold)'),
    Line2D([0], [0], color='#557a9b', linestyle='--', linewidth=1.2, label='Projection contour (Obj 1–2)'),
    Line2D([0], [0], color='#688caa', linestyle='--', linewidth=1.2, label='Projection contour (Obj 1–3)'),
    Line2D([0], [0], color='#7b9ebc', linestyle='--', linewidth=1.2, label='Projection contour (Obj 2–3)')
]

leg = ax.legend(
    handles=legend_elements,
    loc='upper right',
    bbox_to_anchor=(0.985, 0.985),
    frameon=True,
    facecolor='#ffffff',
    edgecolor='#d1d5db',
    framealpha=0.92,
    fontsize=10.5,
    labelspacing=0.55,
    borderpad=0.8
)
leg.get_frame().set_boxstyle('round,pad=0.5,rounding_size=0.3')

# -------------------------------------------------------------------------
# 12. Curvature Colorbar (Right Side)
# -------------------------------------------------------------------------
cbar_ax = fig.add_axes([0.87, 0.28, 0.024, 0.38])
sm = cm.ScalarMappable(cmap=cmap_pareto, norm=norm_log)
sm.set_array([])
cbar = fig.colorbar(sm, cax=cbar_ax)

cbar.set_ticks([1e-3, 1e-2, 1e-1, 1e0])
cbar.set_ticklabels([r'$10^{-3}$', r'$10^{-2}$', r'$10^{-1}$', r'$10^0$'])
cbar.ax.tick_params(labelsize=11)

cbar.ax.set_title('Pareto front\n(local curvature)', fontsize=12, pad=12, fontfamily='sans-serif')

fig.text(0.88, 0.23,
         'Higher curvature indicates\nincreased trade-off (knee region).',
         ha='center', va='top', fontsize=9.5, fontfamily='sans-serif', fontstyle='italic', color='#374151')

# -------------------------------------------------------------------------
# 13. Save Figure
# -------------------------------------------------------------------------
plt.subplots_adjust(left=0.08, right=0.86, top=0.92, bottom=0.08)
save_py_nature_figure(fig, FilePath(_args.output_dir) / "optimization_pareto_manifold_3d_template")



