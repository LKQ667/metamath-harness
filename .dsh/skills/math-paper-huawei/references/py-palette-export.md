# Python 顶刊绘图配色与导出规范

## 来源蒸馏

- `nature-figure` 的 Nature 风格 palette 与统一家族策略
- `figures4papers` 的蓝/绿/红/中性语义映射
- Nature 官方可访问性要求
- 10 篇 Nature 系论文的十轮截图蒸馏结论
- `PaperGallery` 的图型分类与版式展示方式，仅作为截图整理和图型命名参考

## 主调色板

```python
PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "cyan_main": "#3F8EFC",
    "green_soft": "#AADCA9",
    "green_strong": "#4F8A4B",
    "red_soft": "#E9A6A1",
    "red_strong": "#B64342",
    "orange_main": "#E28E2C",
    "coral_main": "#E76F51",
    "teal_main": "#42949E",
    "violet_main": "#9A4D8E",
    "gold_main": "#D8A431",
    "curvature_low": "#2A6DBB",
    "curvature_mid": "#BFD3EA",
    "curvature_high": "#D95F4C",
    "temporal_focus": "#2B7C6F",
    "spatial_focus": "#1F9D8A",
    "neutral_light": "#D8D8D8",
    "neutral_mid": "#8A8A8A",
    "neutral_dark": "#3F3F3F",
    "slate_dark": "#324A5F",
    "black": "#222222",
}
```

## 统一家族色

当多个方法属于同一类，只做层级区分，不做彩虹配色：

```python
PALETTE_FAMILY = {
    "baseline_dark": "#484878",
    "baseline_mid": "#7884B4",
    "baseline_soft": "#B4C0E4",
    "hero_tiny": "#E4E4F0",
    "hero_base": "#E4CCD8",
    "hero_large": "#F0C0CC",
}
```

## 角色规则

- 主方法 / 主方案：深蓝或同一 hero 家族
- 基线 / 对照：冷色基线家族或中性灰
- 改进 / 上升：绿色，仅用于方向性提示时优先
- 下降 / 风险 / 劣化：红色，仅用于方向性提示时优先
- 结构背景：浅灰
- 强调点：金色或橙色，但一个图内尽量只用一次
- 网络几何 / 曲率：`curvature_low -> curvature_mid -> curvature_high`
- 时序网络 / 突发活动：`temporal_focus + neutral_mid + orange_main`
- 时空网络：`spatial_focus + blue_secondary + neutral_mid`

## 禁忌

- 不用高饱和彩虹渐变
- 不用大面积紫蓝单色霸屏
- 不让同一方法在不同 panel 换色
- 不用彩色正文文字解释颜色

## 数学建模默认策略

- 趋势图：`蓝 + 橙 + 灰`
- 敏感性：`蓝灰主调 + 红绿方向提示`
- Pareto：`蓝灰底 + 橙色前沿`
- 网络：`结构灰 + 节点角色蓝/橙`
- 相图：`灰色相轨 + 蓝色主轨 + 红色平衡点`
- 网络几何：`曲率蓝 -> 浅灰蓝 -> 珊瑚红`
- 时序网络：`深青 + 中性灰 + 单个阈值暖色`
- 时空网络：`连续场主色 + 网络结构副色 + 最少量强调色`

## 导出与字体

| 配置 | 字体优先 | QA 边界 |
|---|---|---|
| competition_cn（默认） | 微软雅黑/黑体 | 中文显示、三格式、可编辑文字与缩印可读性 |
| competition_en | Arial/Helvetica | 英文术语、单位、三格式与可编辑文字 |
| research | Arial/Helvetica | 额外检查 89/183 mm 画布及 5–7 pt 普通文字；8 pt 仅用于小写加粗 panel 标签 |

- Python 图统一设置：
  - `svg.fonttype = 'none'`
  - `pdf.fonttype = 42`
  - `ps.fonttype = 42`
- 中文竞赛字体回退优先：
  - `Microsoft YaHei`
  - `SimHei`
  - `Arial`
  - `Helvetica`
  - `DejaVu Sans`
- 默认白底、无顶边/右边框、无背景网格。
- 至少导出：
  - `svg`：主矢量文件，文字可编辑
  - `pdf`：论文级矢量导出
  - `png`：快速核图与排版预览
- 默认 `dpi >= 300`，高密度图可用 `dpi >= 320` 或 `600`

## 单栏与双栏建议

- 单栏优先宽度：`89 mm`
- 双栏优先宽度：`183 mm`
- 图缩小后仍需保证中文标题、坐标轴、图例和注释清晰可读

QA 不自动证明文字无重叠、统计正确、PDF 字体已嵌入或达到期刊录用水平；这些项目保留人工复核。
