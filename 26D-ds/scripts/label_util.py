# -*- coding: utf-8 -*-
"""论文图注标签排布工具：贪心避让，消除标签之间与标签对数据点的遮挡。

所有绘图脚本共用，保证图内文字不重叠、不被裁切。核心做法是在显示坐标系下
对候选偏移逐一试放，用文本包围盒与已放置包围盒、数据点包围盒做相交判定。
"""
from __future__ import annotations

# 8 个候选偏移方向（点），按“右上、左上、右下、左下、正右、正左、正上、正下”排序
DEFAULT_OFFSETS = (
    (7.0, 4.0), (-7.0, 4.0), (7.0, -8.0), (-7.0, -8.0),
    (9.0, -2.0), (-9.0, -2.0), (0.0, 9.0), (0.0, -13.0),
)


def _bbox_overlap(a, b, pad=0.0):
    return not (a.x1 + pad <= b.x0 or b.x1 + pad <= a.x0
                or a.y1 + pad <= b.y0 or b.y1 + pad <= a.y0)


def place_labels(ax, xs, ys, texts, *, fontsize=6.3, color="#1A1A1A",
                 offsets=DEFAULT_OFFSETS, avoid_points=True, point_radius_px=4.0,
                 extra_boxes=(), fig=None, max_tries=None):
    """在 ax 上为每个 (x, y) 放置一个不重叠的文本标签。

    返回实际使用的偏移列表，便于复核。extra_boxes 为需要额外避让的
    显示坐标包围盒（例如图例、统计框）。
    """
    fig = fig or ax.figure
    renderer = fig.canvas.get_renderer() if hasattr(fig.canvas, "get_renderer") else None
    if renderer is None:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

    placed = list(extra_boxes)
    point_boxes = []
    if avoid_points:
        for x, y in zip(xs, ys):
            px, py = ax.transData.transform((x, y))
            point_boxes.append(_mk_box(px - point_radius_px, py - point_radius_px,
                                       px + point_radius_px, py + point_radius_px))

    used = []
    n = len(texts)
    for index in range(n):
        x, y = xs[index], ys[index]
        label = texts[index]
        chosen = None
        candidates = offsets if max_tries is None else offsets[:max_tries]
        for dx, dy in candidates:
            ann = ax.annotate(label, (x, y), textcoords="offset points",
                              xytext=(dx, dy), fontsize=fontsize, color=color, zorder=8)
            fig.canvas.draw()
            box = ann.get_window_extent(renderer=renderer)
            clash = any(_bbox_overlap(box, other, pad=1.2) for other in placed + point_boxes)
            if not clash:
                chosen = (dx, dy, box)
                break
            ann.remove()
        if chosen is None:
            dx, dy = candidates[0]
            ann = ax.annotate(label, (x, y), textcoords="offset points",
                              xytext=(dx, dy), fontsize=fontsize, color=color, zorder=8)
            fig.canvas.draw()
            chosen = (dx, dy, ann.get_window_extent(renderer=renderer))
        used.append((dx, dy))
        placed.append(chosen[2])
    return used


def _mk_box(x0, y0, x1, y1):
    class _Box:
        __slots__ = ("x0", "y0", "x1", "y1")
    b = _Box()
    b.x0, b.y0, b.x1, b.y1 = x0, y0, x1, y1
    return b


def box_of_artist(artist, fig):
    """把任意 artist（图例、文本、矩形）的显示坐标包围盒转成可避让盒。"""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ext = artist.get_window_extent(renderer=renderer)
    return _mk_box(ext.x0, ext.y0, ext.x1, ext.y1)


def axes_box(ax, fig):
    """返回坐标区自身的显示坐标包围盒，用于检测标签越界。"""
    fig.canvas.draw()
    return box_of_artist(ax.get_window_extent(), fig) if hasattr(ax, "get_window_extent") else None