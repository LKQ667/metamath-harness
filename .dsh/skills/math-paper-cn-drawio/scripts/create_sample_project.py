#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create a generic math modeling draw.io sample project for validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DRAWIO = """<mxfile host="app.diagrams.net">
  <diagram id="route" name="技术路线图">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="900" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="赛题附件" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#EAF3F8;strokeColor=#4F7F9F;fontFamily=Microsoft YaHei;fontSize=14;" vertex="1" parent="1"><mxGeometry x="40" y="120" width="140" height="60" as="geometry"/></mxCell>
        <mxCell id="3" value="数据审计" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#EAF3F8;strokeColor=#4F7F9F;fontFamily=Microsoft YaHei;fontSize=14;" vertex="1" parent="1"><mxGeometry x="240" y="120" width="140" height="60" as="geometry"/></mxCell>
        <mxCell id="4" value="候选模型比较" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#EEF6EA;strokeColor=#5E8C61;fontFamily=Microsoft YaHei;fontSize=14;" vertex="1" parent="1"><mxGeometry x="440" y="120" width="150" height="60" as="geometry"/></mxCell>
        <mxCell id="5" value="Python 求解" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFF4E6;strokeColor=#B7791F;fontFamily=Microsoft YaHei;fontSize=14;" vertex="1" parent="1"><mxGeometry x="650" y="120" width="140" height="60" as="geometry"/></mxCell>
        <mxCell id="6" value="一致性校验" style="rhombus;whiteSpace=wrap;html=1;fillColor=#F3EEF8;strokeColor=#7A5C99;fontFamily=Microsoft YaHei;fontSize=14;" vertex="1" parent="1"><mxGeometry x="850" y="110" width="140" height="80" as="geometry"/></mxCell>
        <mxCell id="7" value="论文成稿" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#F8EEEE;strokeColor=#A65F5F;fontFamily=Microsoft YaHei;fontSize=14;" vertex="1" parent="1"><mxGeometry x="1060" y="120" width="140" height="60" as="geometry"/></mxCell>
        <mxCell id="e1" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=classic;html=1;strokeColor=#666666;strokeWidth=2;" edge="1" parent="1" source="2" target="3"><mxGeometry relative="1" as="geometry"/></mxCell>
        <mxCell id="e2" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=classic;html=1;strokeColor=#666666;strokeWidth=2;" edge="1" parent="1" source="3" target="4"><mxGeometry relative="1" as="geometry"/></mxCell>
        <mxCell id="e3" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=classic;html=1;strokeColor=#666666;strokeWidth=2;" edge="1" parent="1" source="4" target="5"><mxGeometry relative="1" as="geometry"/></mxCell>
        <mxCell id="e4" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=classic;html=1;strokeColor=#666666;strokeWidth=2;" edge="1" parent="1" source="5" target="6"><mxGeometry relative="1" as="geometry"/></mxCell>
        <mxCell id="e5" value="通过" style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=classic;html=1;strokeColor=#666666;strokeWidth=2;" edge="1" parent="1" source="6" target="7"><mxGeometry relative="1" as="geometry"/></mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create generic math modeling draw.io sample.")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    project = Path(args.project)
    hand = project / "手绘图"
    figures = project / "figures"
    hand.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    source = hand / "通用技术路线图.drawio"
    source.write_text(DRAWIO, encoding="utf-8")
    preview = hand / "通用技术路线图.svg"
    preview.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="white"/></svg>', encoding="utf-8")
    manifest = {
        "figures": [
            {
                "id": "route-generic",
                "title": "通用技术路线图",
                "purpose": "技术路线图",
                "section": "问题分析",
                "source": "手绘图/通用技术路线图.drawio",
                "exports": ["手绘图/通用技术路线图.svg"],
                "paper_ready": True,
                "checks": ["xml", "layout", "manifest", "source", "export", "visual-round-1", "visual-round-2"],
                "export_status": "ok",
                "needs_visual_review": False
            }
        ]
    }
    (figures / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
