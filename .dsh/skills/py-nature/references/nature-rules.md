# 科研严格模式：Nature 官方规范

本文件只约束 profile=research。数学建模竞赛优先遵循赛事模板、语言和缩印可读性。

来源：
- https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/
- https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/

## 必守规则

- 主图宽度优先按 `89 mm`（单栏）或 `183 mm`（双栏）
- 最大高度控制在 `170 mm` 内，给图注留空间
- 正文字体优先 `Arial` / `Helvetica`
- 除 panel 字母外，其余最终排版字号控制在 `5–7 pt`
- panel 标号用粗体小写 `a, b, c...`
- 坐标轴必须有刻度和单位
- 避免背景网格线、装饰图标、阴影、彩色正文文字
- 图片导出优先 `RGB`
- 主图优先 `svg` / `pdf` 等矢量格式，并保留**可编辑文字**
- `matplotlib` 必须设置：
  - `svg.fonttype = 'none'`
  - `pdf.fonttype = 42`
  - `ps.fonttype = 42`

## 可访问性

- 避免红绿直接对打
- 黑白文字优先于彩色文字
- 颜色承担类别区分时，仍要保证灰度下可辨识
- 复杂图例优先改成关键线或直接标注

## 对 Py-Nature 的落地约束

- 自动 QA 检查 SVG 文字节点、字体声明、89/183 mm 画布、5–7 pt 普通文字、8 pt 小写加粗 panel 标签及三格式非空。
- 自动 QA 不认证 PDF 字体嵌入、文字重叠、统计正确性或期刊录用条件；这些项目必须人工复核。

- 默认白底
- 默认去掉 top/right spines
- 默认不加网格线
- 默认 `svg + pdf + png` 三格式导出
- 默认走统一的 `apply_py_nature_style(...)` 与 `run_py_nature_qa(...)`
