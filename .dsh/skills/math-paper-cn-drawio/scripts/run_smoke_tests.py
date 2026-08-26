#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""多轮回归：标准生成、布局错误拦截与中文转义。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHILD_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def manifest(project: Path, source: str, ready: bool = True, template_id: str | None = None) -> None:
    figures = project / "figures"; figures.mkdir(parents=True, exist_ok=True)
    (project / "手绘图" / "图.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"/>', encoding="utf-8")
    title = "技术路线图" if template_id else "中文 QA 图"
    item = {"id": "qa", "title": title, "purpose": "测试", "section": "附录", "source": source, "exports": ["手绘图/图.svg"], "paper_ready": ready, "checks": ["xml", "layout"], "export_status": "ok", "needs_visual_review": False}
    if template_id:
        item.update({"chart_family": "roadmap", "template_id": template_id})
    data = {"figures": [item]}
    (figures / "manifest.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def validate(project: Path, expected: int, strict: bool = True) -> None:
    command = [sys.executable, str(HERE / "validate_drawio_project.py"), "--project", str(project)]
    if strict:
        command.append("--strict")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=CHILD_ENV)
    if result.returncode != expected:
        raise AssertionError(f"校验码 {result.returncode}，期望 {expected}: {result.stdout}{result.stderr}")


def pipeline_smoke() -> None:
    """十类模板管道冒烟：选路优先级与四个新模板的生成/静态校验。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("drawio_pipeline", HERE / "drawing" / "drawio_pipeline.py")
    pipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pipe)
    routing = [
        ({"feedback": 1, "branches": 1, "actors": 3, "panels": 2, "side_head": 1, "output_banner": 1, "focus_stage": 1}, "dual-panel-bilevel"),
        ({"feedback": 1}, "feedback-loop"),
        ({"side_head": 1}, "stepwise-sidehead"),
        ({}, "horizontal-stage-chain"),
        ({"kind": "roadmap"}, "stage-blocks-l"),
        ({"kind": "roadmap", "panels": 2, "feedback": 1, "support_blocks": 2}, "dual-panel-bilevel"),
        ({"kind": "roadmap", "side_head": 1}, "stepwise-sidehead"),
        ({"kind": "roadmap", "output_banner": 1}, "steps-stacked-banner"),
    ]
    for brief, want in routing:
        got = pipe.choose_template(brief)
        if got != want:
            raise AssertionError(f"选路错误: {brief} -> {got}，期望 {want}")
    for template in ("dual-panel-bilevel", "stage-blocks-l", "stepwise-sidehead", "steps-stacked-banner"):
        with tempfile.TemporaryDirectory(prefix="math-drawio-pipe-") as temp:
            out = Path(temp) / f"{template}.drawio"
            out.write_text(pipe.build_xml(template), encoding="utf-8")
            errors = pipe.validate_drawio(out, template)
            if errors:
                raise AssertionError(f"模板 {template} 校验失败: {errors}")
    with tempfile.TemporaryDirectory(prefix="math-drawio-atomic-") as temp:
        root = Path(temp)
        brief = root / "brief.json"
        brief.write_text(json.dumps({"kind": "roadmap"}, ensure_ascii=False), encoding="utf-8")
        out = root / "roadmap.drawio"
        result = subprocess.run(
            [sys.executable, str(HERE / "drawing" / "drawio_pipeline.py"), "build", "--brief", str(brief), "--output", str(out)],
            capture_output=True, text=True, encoding="utf-8", env=CHILD_ENV,
        )
        payload = json.loads(result.stdout)
        if result.returncode != 0 or payload.get("template_id") != "stage-blocks-l":
            raise AssertionError(f"原子选路构建失败: {result.stdout}{result.stderr}")
        forged = root / "forged.drawio"
        forged.write_text(pipe.build_xml("main-chain-support"), encoding="utf-8")
        errors = pipe.template_structure_errors(forged, "stage-blocks-l")
        if not errors or not any("节点" in error or "diagram id" in error for error in errors):
            raise AssertionError(f"旧结构伪装新模板未被拦截: {errors}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="math-drawio-smoke-") as temp:
        root = Path(temp); good = root / "good"; hand = good / "手绘图"; hand.mkdir(parents=True)
        spec = {"title": "数据清洗与模型建立", "nodes": [{"id": "n1", "label": "原始数据&附件", "role": "data", "shape": "data"}, {"id": "n2", "label": "异常值审计", "role": "check"}, {"id": "n3", "label": "主模型建立", "role": "model"}], "edges": [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3", "label": "通过"}]}
        spec_path = root / "spec.json"; spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        source = hand / "图.drawio"
        subprocess.run([sys.executable, str(HERE / "build_drawio_diagram.py"), "--input", str(spec_path), "--output", str(source)], check=True, env=CHILD_ENV)
        xml = source.read_text(encoding="utf-8")
        if "原始数据&amp;附件" not in xml or "&amp;amp;" in xml:
            raise AssertionError("XML 特殊字符转义错误")
        manifest(good, "手绘图/图.drawio")
        validate(good, 0)

        bad = root / "bad"; bad_hand = bad / "手绘图"; bad_hand.mkdir(parents=True)
        bad_xml = xml.replace('x="270" y="180"', 'x="50" y="180"')
        (bad_hand / "图.drawio").write_text(bad_xml, encoding="utf-8")
        manifest(bad, "手绘图/图.drawio")
        validate(bad, 1)
        import importlib.util
        pipe_spec = importlib.util.spec_from_file_location("drawio_pipeline_fixture", HERE / "drawing" / "drawio_pipeline.py")
        pipe = importlib.util.module_from_spec(pipe_spec)
        pipe_spec.loader.exec_module(pipe)
        roadmap_good = root / "roadmap-good"; good_hand = roadmap_good / "手绘图"; good_hand.mkdir(parents=True)
        (good_hand / "图.drawio").write_text(pipe.build_xml("stage-blocks-l"), encoding="utf-8")
        manifest(roadmap_good, "手绘图/图.drawio", template_id="stage-blocks-l")
        validate(roadmap_good, 0, strict=True)
        roadmap_bad = root / "roadmap-bad"; bad_roadmap_hand = roadmap_bad / "手绘图"; bad_roadmap_hand.mkdir(parents=True)
        (bad_roadmap_hand / "图.drawio").write_text(pipe.build_xml("main-chain-support"), encoding="utf-8")
        manifest(roadmap_bad, "手绘图/图.drawio", template_id="stage-blocks-l")
        validate(roadmap_bad, 1, strict=True)
    pipeline_smoke()
    print("smoke tests 通过：生成、转义、重叠拦截、原子选路、四新模板指纹与伪造结构拦截")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
