# 上游来源与适配边界

本技能是面向中文数学建模论文的独立技能，不覆盖、不删除、不改写上游项目。

## 来源

1. Agents365-ai/drawio-skill
   - 仓库：https://github.com/Agents365-ai/drawio-skill
   - 吸收内容：本地 `.drawio` 生成、draw.io desktop CLI 导出、自检与迭代修正思想、PNG/SVG/PDF 可编辑导出约定。
   - 许可证：MIT，以原仓库为准。

2. softaworks/agent-toolkit（draw-io skill）
   - 仓库：https://github.com/softaworks/agent-toolkit/tree/main/skills/draw-io
   - 吸收内容：字体一致性、节点/容器安全间距、箭头层次、PNG 视觉验收与渐进披露。
   - 许可证：以原仓库为准。

3. DayuanJiang/next-ai-draw-io
   - 仓库：https://github.com/DayuanJiang/next-ai-draw-io
   - 吸收内容：自然语言图稿迭代、历史修订、XML 作为图的可编辑单一事实来源。
   - 许可证：Apache-2.0，以原仓库为准。

## 本技能新增约束

- 全部标签、图题、注释默认中文。
- 输出默认适配 `math-paper-cn` 项目的 `手绘图/` 和 `figures/manifest.json`。
- 以全国大学生数学建模竞赛论文为目标，优先服务技术路线图、问题分析图、模型求解流程图和结果检验流程图。
- 强制保留 `.drawio` 源文件，导出图不得替代源文件。
- 上游思想只用于流程、约束和布局；本技能不复制其代码或视觉资产。
