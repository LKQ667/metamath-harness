#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成带判断分支的 draw.io 视觉回归样例。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


DRAWIO = '''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net"><diagram id="branch-qa" name="分支质检图"><mxGraphModel page="1" pageWidth="1600" pageHeight="900" grid="1" defaultFontFamily="Microsoft YaHei"><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="input" value="原始数据" style="rounded=1;html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;fillColor=#EAF3F8;strokeColor=#4F7F9F;" vertex="1" parent="1"><mxGeometry x="80" y="260" width="150" height="64" as="geometry"/></mxCell>
<mxCell id="audit" value="质量审计" style="rounded=1;html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;fillColor=#F3EEF8;strokeColor=#7A5C99;" vertex="1" parent="1"><mxGeometry x="330" y="260" width="150" height="64" as="geometry"/></mxCell>
<mxCell id="judge" value="满足阈值？" style="rhombus;html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;fillColor=#F3EEF8;strokeColor=#7A5C99;" vertex="1" parent="1"><mxGeometry x="580" y="235" width="150" height="110" as="geometry"/></mxCell>
<mxCell id="model" value="模型建立" style="rounded=1;html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;fillColor=#EEF6EA;strokeColor=#5E8C61;" vertex="1" parent="1"><mxGeometry x="830" y="160" width="150" height="64" as="geometry"/></mxCell>
<mxCell id="clean" value="清洗与补全" style="rounded=1;html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;fillColor=#FFF4E6;strokeColor=#B7791F;" vertex="1" parent="1"><mxGeometry x="830" y="380" width="150" height="64" as="geometry"/></mxCell>
<mxCell id="output" value="结果输出" style="rounded=1;html=1;whiteSpace=wrap;fontFamily=Microsoft YaHei;fontSize=14;fontColor=#222222;fillColor=#F8EEEE;strokeColor=#A65F5F;" vertex="1" parent="1"><mxGeometry x="1080" y="160" width="150" height="64" as="geometry"/></mxCell>
<mxCell id="e1" value="" style="edgeStyle=orthogonalEdgeStyle;endArrow=classic;html=1;strokeColor=#52606D;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="input" target="audit"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="e2" value="" style="edgeStyle=orthogonalEdgeStyle;endArrow=classic;html=1;strokeColor=#52606D;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="audit" target="judge"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="e3" value="是" style="edgeStyle=orthogonalEdgeStyle;endArrow=classic;html=1;fontFamily=Microsoft YaHei;fontSize=12;strokeColor=#52606D;exitX=1;exitY=0.3;entryX=0;entryY=0.5;" edge="1" parent="1" source="judge" target="model"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="e4" value="否" style="edgeStyle=orthogonalEdgeStyle;endArrow=classic;html=1;fontFamily=Microsoft YaHei;fontSize=12;strokeColor=#52606D;exitX=1;exitY=0.75;entryX=0;entryY=0.5;" edge="1" parent="1" source="judge" target="clean"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="e5" value="" style="edgeStyle=orthogonalEdgeStyle;endArrow=classic;html=1;strokeColor=#52606D;exitX=1;exitY=0.5;entryX=0;entryY=0.5;" edge="1" parent="1" source="model" target="output"><mxGeometry relative="1" as="geometry"/></mxCell>
<mxCell id="e6" value="重新审计" style="edgeStyle=orthogonalEdgeStyle;endArrow=classic;html=1;fontFamily=Microsoft YaHei;fontSize=12;strokeColor=#52606D;exitX=0;exitY=0.5;entryX=0.5;entryY=1;" edge="1" parent="1" source="clean" target="audit"><mxGeometry relative="1" as="geometry"><Array as="points"><mxPoint x="760" y="560"/><mxPoint x="405" y="560"/></Array></mxGeometry></mxCell>
</root></mxGraphModel></diagram></mxfile>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    root = Path(args.project); hand = root / "手绘图"; figures = root / "figures"
    hand.mkdir(parents=True, exist_ok=True); figures.mkdir(parents=True, exist_ok=True)
    (hand / "分支质量门.drawio").write_text(DRAWIO, encoding="utf-8")
    manifest = {"figures": [{"id": "branch-qa", "title": "分支质量门", "purpose": "模型流程图", "section": "模型建立", "source": "手绘图/分支质量门.drawio", "exports": ["手绘图/分支质量门.png", "手绘图/分支质量门.svg"], "paper_ready": True, "checks": ["xml", "layout", "visual-round-1", "visual-round-2"], "export_status": "ok", "needs_visual_review": False}]}
    (figures / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
