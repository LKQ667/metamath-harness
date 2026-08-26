# draw.io XML、端口与路由规范

## 最小结构

```xml
<mxfile host="app.diagrams.net"><diagram id="diagram-id" name="图名"><mxGraphModel page="1" pageWidth="1600" pageHeight="900" grid="1" defaultFontFamily="Microsoft YaHei"><root>
  <mxCell id="0"/><mxCell id="1" parent="0"/>
</root></mxGraphModel></diagram></mxfile>
```

每个 `mxCell` 的 ID 唯一；每条边都必须指向已存在的 vertex，且有 `<mxGeometry relative="1" as="geometry"/>`。

## 节点

每个有文字的节点强制包含：

```text
html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;
```

- 数据：`shape=cylinder3`
- 过程：`rounded=1`
- 判断：`rhombus`
- 输出/文档：`shape=mxgraph.flowchart.document`
- 容器：`swimlane;horizontal=0;startSize=38`

节点值必须是 UTF-8 中文或论文中已定义的符号；属性值先用 XML 转义。不要把长句、公式推导或治理流程词写入节点。

## 边与端口

```xml
<mxCell id="e-001" value="通过" style="edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;endArrow=classic;endFill=1;html=1;fontFamily=Microsoft YaHei;fontSize=12;strokeColor=#52606D;strokeWidth=1.5;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="n-001" target="n-002">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

- 左→右主链使用 `exitX=1;exitY=0.5;entryX=0;entryY=0.5`；上→下主链使用 `exitX=0.5;exitY=1;entryX=0.5;entryY=0`。
- 同一节点的多条边不得共用端口：按 `0.25 / 0.5 / 0.75` 分配侧边位置。
- 绕开障碍时为 `mxGeometry` 加 `<Array as="points"><mxPoint x="…" y="…"/></Array>`；拐点只在空白走廊，距离节点边界至少 20 px。
- 不可用自由浮动边代替 `source`/`target`；不可让边标签承载整段解释。
