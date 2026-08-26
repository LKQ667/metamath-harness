#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置 Draw.io 模板生成、静态校验、CLI 探测/安装与导出验证。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROLE_STYLES = {
    "input": ("#E8F1F8", "#527A95"),
    "process": ("#EDF4EA", "#66865B"),
    "model": ("#F3ECF7", "#80678F"),
    "output": ("#F9EFE3", "#A57645"),
    "support": ("#F2F3F5", "#72777D"),
    "header": ("#E5E9EE", "#56616D"),
    "decision": ("#FFF4D9", "#A67B24"),
    "container": ("none", "#8A8F98"),
    "zone": ("#F5F3EF", "none"),
    "action": ("#3D6B99", "none"),
    "caption": ("none", "none"),
}
FONT = "Microsoft YaHei"
TEMPLATE_FILE = Path(__file__).resolve().parents[2] / "assets" / "drawio" / "template_library.json"
SKILL_NAME = Path(__file__).resolve().parents[2].name
ROADMAP_TEMPLATE_IDS = frozenset({
    "dual-panel-bilevel",
    "stage-blocks-l",
    "stepwise-sidehead",
    "steps-stacked-banner",
})


def load_library() -> dict:
    return json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))


def choose_template(brief: dict) -> str:
    if brief.get("kind") == "roadmap":
        # 技术路线图强制新四类模板，默认三段环抱式
        if int(brief.get("panels", 0)) > 1:
            return "dual-panel-bilevel"
        if int(brief.get("side_head", 0)) > 0:
            return "stepwise-sidehead"
        if int(brief.get("output_banner", 0)) > 0:
            return "steps-stacked-banner"
        return "stage-blocks-l"
    if int(brief.get("panels", 0)) > 1:
        return "dual-panel-bilevel"
    if int(brief.get("side_head", 0)) > 0:
        return "stepwise-sidehead"
    if int(brief.get("output_banner", 0)) > 0:
        return "steps-stacked-banner"
    if int(brief.get("focus_stage", 0)) > 0:
        return "stage-blocks-l"
    if int(brief.get("feedback", 0)) > 0:
        return "feedback-loop"
    if int(brief.get("branches", 0)) > 0:
        return "branch-decision"
    if int(brief.get("actors", 0)) > 1:
        return "dual-swimlane"
    if int(brief.get("support_blocks", 0)) > 0:
        return "main-chain-support"
    if int(brief.get("stages", 0)) >= 5 and brief.get("direction") == "vertical":
        return "vertical-layer-chain"
    return "horizontal-stage-chain"


def vertex_style(role: str) -> str:
    fill, stroke = ROLE_STYLES.get(role, ROLE_STYLES["process"])
    # 所有带文字节点必须包含中文字体与自动换行，保证静态校验一致
    base = f"whiteSpace=wrap;html=1;fontFamily={FONT};"
    if role == "action":
        return (
            f"rounded=1;arcSize=40;{base}fillColor={fill};strokeColor=none;"
            "fontColor=#FFFFFF;fontStyle=1;fontSize=13;align=center;verticalAlign=middle;spacing=6;"
        )
    if role == "caption":
        return (
            f"text;{base}strokeColor=none;fillColor=none;"
            "fontColor=#2B3138;fontStyle=1;fontSize=12;align=left;verticalAlign=middle;spacing=2;"
        )
    if role == "container":
        return (
            f"rounded=1;arcSize=6;{base}dashed=1;dashPattern=8 6;fillColor=none;"
            f"strokeColor={stroke};strokeWidth=1.6;fontColor=#2B3138;fontSize=13;align=center;verticalAlign=middle;"
        )
    if role == "zone":
        return (
            f"rounded=0;{base}fillColor={fill};strokeColor=none;"
            "fontColor=#2B3138;fontSize=12;align=center;verticalAlign=middle;"
        )
    shape = "rhombus;" if role == "decision" else "rounded=1;arcSize=10;"
    return (
        f"{shape}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
        f"fontColor=#20262D;fontFamily={FONT};fontSize=14;align=center;verticalAlign=middle;"
        "spacing=8;strokeWidth=1.4;"
    )


def edge_style(source_node: list, target_node: list) -> str:
    sx, sy = source_node[2] + source_node[4] / 2, source_node[3] + source_node[5] / 2
    tx, ty = target_node[2] + target_node[4] / 2, target_node[3] + target_node[5] / 2
    dx, dy = tx - sx, ty - sy
    if abs(dx) >= abs(dy):
        port = "exitX=1;exitY=0.5;entryX=0;entryY=0.5;" if dx >= 0 else "exitX=0;exitY=0.5;entryX=1;entryY=0.5;"
    else:
        port = "exitX=0.5;exitY=1;entryX=0.5;entryY=0;" if dy >= 0 else "exitX=0.5;exitY=0;entryX=0.5;entryY=1;"
    return (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
        f"html=1;endArrow=block;endFill=1;strokeColor=#56616D;strokeWidth=1.4;{port}"
        f"fontFamily={FONT};fontSize=12;labelBackgroundColor=#FFFFFF;"
    )


def _has_cjk(text: str | None) -> bool:
    """判断文本是否含 CJK 字符（raw 通道字体注入判定）。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in (text or ""))


def _ensure_cjk_style(style: str) -> str:
    """CJK 值节点的 raw 样式：剔除旧 fontFamily 后追加雅黑，并确保自动换行。"""
    style = re.sub(r"fontFamily=[^;]*;?", "", style)
    parts = [p for p in style.split(";") if p]
    if not any(p.strip() == "whiteSpace=wrap" for p in parts):
        parts.append("whiteSpace=wrap")
    parts.append(f"fontFamily={FONT}")
    return ";".join(parts) + ";"


def build_xml(template_id: str, labels: dict[str, str] | None = None) -> str:
    library = load_library()
    template = next((item for item in library["templates"] if item["id"] == template_id), None)
    if template is None:
        raise ValueError(f"未知模板: {template_id}")
    labels = labels or {}
    page = template["page"]
    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "agent": SKILL_NAME, "version": "24.7.17"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": template_id, "name": template["name"]})
    model_attrs = {
        "dx": "1200", "dy": "800", "grid": "1", "gridSize": "10", "guides": "1",
        "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1",
        "pageScale": "1", "pageWidth": str(page["width"]), "pageHeight": str(page["height"]),
        "math": "0", "shadow": "0",
    }
    if page.get("background"):
        model_attrs["background"] = str(page["background"])
    model = ET.SubElement(diagram, "mxGraphModel", model_attrs)
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    node_map = {node[0]: node for node in template["nodes"]}
    for node in template["nodes"]:
        node_id, label, x, y, width, height, role = node[:7]
        raw_style = node[7] if len(node) > 7 else None
        value = labels.get(node_id, label)
        if raw_style is not None:
            style = _ensure_cjk_style(raw_style) if _has_cjk(value) else raw_style
        else:
            style = vertex_style(role)
        cell = ET.SubElement(
            root,
            "mxCell",
            {"id": node_id, "value": value, "style": style, "vertex": "1", "parent": "1"},
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(width), "height": str(height), "as": "geometry"})
    for index, edge in enumerate(template["edges"]):
        raw = edge[3] if len(edge) > 3 else None
        if raw is not None:
            edge_id = raw.get("id") or f"e{index + 1}"
            source, target, label = edge[0], edge[1], edge[2]
            attrs = {
                "id": edge_id, "value": labels.get(edge_id, label), "style": raw["style"],
                "edge": "1", "parent": "1",
            }
            if source:
                attrs["source"] = source
            if target:
                attrs["target"] = target
            cell = ET.SubElement(root, "mxCell", attrs)
            geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
            if raw.get("sourcePoint"):
                ET.SubElement(geo, "mxPoint", {"x": str(raw["sourcePoint"][0]), "y": str(raw["sourcePoint"][1]), "as": "sourcePoint"})
            if raw.get("targetPoint"):
                ET.SubElement(geo, "mxPoint", {"x": str(raw["targetPoint"][0]), "y": str(raw["targetPoint"][1]), "as": "targetPoint"})
            if raw.get("points"):
                arr = ET.SubElement(geo, "Array", {"as": "points"})
                for px, py in raw["points"]:
                    ET.SubElement(arr, "mxPoint", {"x": str(px), "y": str(py)})
            continue
        source, target, label = edge
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"e{index + 1}", "value": labels.get(f"e{index + 1}", label), "style": edge_style(node_map[source], node_map[target]),
                "edge": "1", "parent": "1", "source": source, "target": target,
            },
        )
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=False)


def _short_ids(values: set[str]) -> str:
    ordered = sorted(values)
    shown = ", ".join(ordered[:8])
    return shown + (f" 等 {len(ordered)} 项" if len(ordered) > 8 else "")


def _template_structure_errors(root: ET.Element, template_id: str) -> list[str]:
    """核对模板身份与结构骨架；允许标签、字体和几何位置按项目调整。"""
    template = next((item for item in load_library()["templates"] if item["id"] == template_id), None)
    if template is None:
        return [f"模板库不存在 template_id: {template_id}"]
    errors: list[str] = []
    diagram = root.find(".//diagram")
    actual_diagram_id = diagram.get("id", "") if diagram is not None else ""
    if actual_diagram_id != template_id:
        errors.append(f"diagram id 不一致: 期望 {template_id}，实际 {actual_diagram_id or '<空>'}")

    cells = root.findall(".//mxCell")
    actual_vertices = {cell.get("id", "") for cell in cells if cell.get("vertex") == "1"}
    actual_edges = {cell.get("id", "") for cell in cells if cell.get("edge") == "1"}
    expected_vertices = {str(node[0]) for node in template["nodes"]}
    expected_topology: dict[str, tuple[str | None, str | None]] = {}
    for index, edge in enumerate(template["edges"]):
        raw = edge[3] if len(edge) > 3 else None
        edge_id = str(raw.get("id") or f"e{index + 1}") if raw is not None else f"e{index + 1}"
        expected_topology[edge_id] = (edge[0], edge[1])
    expected_edges = set(expected_topology)

    missing_vertices = expected_vertices - actual_vertices
    extra_vertices = actual_vertices - expected_vertices
    missing_edges = expected_edges - actual_edges
    extra_edges = actual_edges - expected_edges
    if missing_vertices:
        errors.append(f"模板节点缺失: {_short_ids(missing_vertices)}")
    if extra_vertices:
        errors.append(f"模板节点多余: {_short_ids(extra_vertices)}")
    if missing_edges:
        errors.append(f"模板边缺失: {_short_ids(missing_edges)}")
    if extra_edges:
        errors.append(f"模板边多余: {_short_ids(extra_edges)}")

    actual_by_id = {cell.get("id", ""): cell for cell in cells if cell.get("edge") == "1"}
    mismatched = {
        edge_id
        for edge_id, endpoints in expected_topology.items()
        if edge_id in actual_by_id
        and (actual_by_id[edge_id].get("source"), actual_by_id[edge_id].get("target")) != endpoints
    }
    if mismatched:
        errors.append(f"模板边连接关系不一致: {_short_ids(mismatched)}")
    return errors


def template_structure_errors(path: Path, template_id: str) -> list[str]:
    """供项目门禁复用的模板结构指纹检查。"""
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        return [f"XML 无法解析: {exc}"]
    return _template_structure_errors(root, template_id)


def validate_drawio(path: Path, expected_template_id: str | None = None) -> list[str]:
    errors: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        return [f"XML 无法解析: {exc}"]
    cells = root.findall(".//mxCell")
    ids = [cell.get("id", "") for cell in cells]
    if len(ids) != len(set(ids)):
        errors.append("mxCell id 重复")
    id_set = set(ids)
    boxes: list[tuple[str, float, float, float, float, str, str]] = []
    for cell in cells:
        if cell.get("vertex") == "1":
            style = cell.get("style", "")
            value = cell.get("value", "")
            # 仅 CJK 文本要求中文字体与自动换行（raw 直录英文节点保留原型字体）
            if value and _has_cjk(value):
                if f"fontFamily={FONT}" not in style:
                    errors.append(f"节点 {cell.get('id')} 缺少中文字体")
                if "whiteSpace=wrap" not in style:
                    errors.append(f"节点 {cell.get('id')} 未启用自动换行")
            geo = cell.find("mxGeometry")
            if geo is not None:
                try:
                    boxes.append((cell.get("id", ""), *(float(geo.get(k, "0")) for k in ("x", "y", "width", "height")), value, style))
                except ValueError:
                    errors.append(f"节点 {cell.get('id')} 几何值无效")
        if cell.get("edge") == "1":
            source, target = cell.get("source"), cell.get("target")
            style = cell.get("style", "")
            if source or target:
                # 连接边：已声明端点必须存在，且需显式箭头（路由样式不再强制正交）
                if source is not None and source not in id_set:
                    errors.append(f"边 {cell.get('id')} 端点不存在")
                if target is not None and target not in id_set:
                    errors.append(f"边 {cell.get('id')} 端点不存在")
                if "endArrow=" not in style:
                    errors.append(f"边 {cell.get('id')} 缺少明确箭头")
            # 悬浮边（无 source 且无 target，靠 sourcePoint/targetPoint 定位）豁免端点与路由检查
    for index, (a_id, ax, ay, aw, ah, a_value, a_style) in enumerate(boxes):
        for b_id, bx, by, bw, bh, b_value, b_style in boxes[index + 1:]:
            if ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by:
                # 完全嵌套（容器/分区包住内容节点）合法，仅部分相交或同尺寸重复框报错
                a_contains_b = ax <= bx and ay <= by and ax + aw >= bx + bw and ay + ah >= by + bh and aw * ah > bw * bh
                b_contains_a = bx <= ax and by <= ay and bx + bw >= ax + aw and by + bh >= ay + ah and bw * bh > aw * ah
                if a_contains_b or b_contains_a:
                    continue
                # 装饰豁免：文字标签与虚线装饰层允许叠放，仅实体内容盒部分相交报错
                if not (a_value and b_value):
                    continue
                if a_style.startswith("text;") or b_style.startswith("text;"):
                    continue
                if "dashed=1" in a_style or "dashed=1" in b_style:
                    continue
                errors.append(f"节点重叠: {a_id} 与 {b_id}")
    if expected_template_id:
        errors.extend(_template_structure_errors(root, expected_template_id))
    return errors


def find_drawio() -> Path | None:
    runtime_root = os.environ.get("DSH_RUNTIME_ROOT") or os.environ.get("MATH_PAPER_CN_RUNTIME")
    bundled = str(Path(runtime_root) / "drawio" / "draw.io.exe") if runtime_root else None
    strict = os.environ.get("DSH_PORTABLE_STRICT") == "1"
    candidates = [
        os.environ.get("DRAWIO_CLI"),
        bundled,
    ]
    if not strict:
        candidates += [shutil.which("drawio"), shutil.which("draw.io"), r"C:\Program Files\draw.io\draw.io.exe", r"C:\Program Files (x86)\draw.io\draw.io.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def run_cli(executable: Path, args: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(executable), *args], text=True, encoding="utf-8", errors="replace",
        capture_output=True, timeout=timeout,
    )


def install_drawio(portable_dir: Path) -> tuple[Path | None, list[str]]:
    log: list[str] = []
    if os.environ.get("DSH_PORTABLE_STRICT") == "1":
        return None, ["portable_strict_missing_bundled_drawio"]
    winget = shutil.which("winget")
    if winget:
        proc = subprocess.run(
            [winget, "install", "--id", "JGraph.Draw", "--exact", "--silent",
             "--accept-package-agreements", "--accept-source-agreements"],
            text=True, capture_output=True, timeout=600,
        )
        log.append(f"winget_exit={proc.returncode}")
        installed = find_drawio()
        if proc.returncode == 0 and installed:
            return installed, log
    portable_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        "https://api.github.com/repos/jgraph/drawio-desktop/releases/latest",
        headers={"User-Agent": f"{SKILL_NAME}-drawio-installer"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
    except Exception as exc:
        log.append(f"portable_download_failed={type(exc).__name__}")
        return None, log
    asset = next(
        (item for item in release.get("assets", []) if "windows-no-installer" in item["name"].lower() and item["name"].lower().endswith(".exe")),
        None,
    )
    if not asset:
        log.append("portable_asset_missing")
        return None, log
    target = portable_dir / "draw.io.exe"
    urllib.request.urlretrieve(asset["browser_download_url"], target)
    log.append(f"portable={target}")
    return target, log


def verify_cli(executable: Path, work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    source = work_dir / "中文最小验证.drawio"
    source.write_text(build_xml("horizontal-stage-chain", {"n1": "中文字体验证"}), encoding="utf-8")
    result = {
        "executable": str(executable.resolve()),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "version": "",
        "version_ok": False,
        "source_ok": not validate_drawio(source),
        "exports": {},
        "cn_text_ok": False,
    }
    version = run_cli(executable, ["--version"], timeout=30)
    result["version"] = (version.stdout.strip() or version.stderr.strip()).splitlines()[0] if (version.stdout.strip() or version.stderr.strip()) else ""
    result["version_ok"] = version.returncode == 0
    for fmt in ("png", "svg", "pdf"):
        output = work_dir / f"中文最小验证.{fmt}"
        args = ["--export", "--format", fmt]
        if fmt == "png":
            args += ["--scale", "2"]
        args += ["--output", str(output), str(source)]
        proc = run_cli(executable, args)
        result["exports"][fmt] = proc.returncode == 0 and wait_for_stable_output(output)
    svg_path = work_dir / "中文最小验证.svg"
    if svg_path.exists():
        svg_text = svg_path.read_text(encoding="utf-8", errors="ignore")
        result["cn_text_ok"] = "中文字体验证" in svg_text or "Microsoft YaHei" in svg_text
    result["ok"] = all((result["version_ok"], result["source_ok"], result["cn_text_ok"], *result["exports"].values()))
    return result


def export_drawio(executable: Path, source: Path, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    exports: dict[str, str] = {}
    for fmt in ("png", "svg", "pdf"):
        output = output_dir / f"{source.stem}.{fmt}"
        args = ["--export", "--format", fmt]
        if fmt == "png":
            args += ["--scale", "2"]
        args += ["--output", str(output), str(source)]
        proc = run_cli(executable, args)
        if proc.returncode != 0 or not wait_for_stable_output(output):
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"{fmt} 导出失败：目标文件在 30 秒内未达到非空且连续两次大小稳定")
        exports[fmt] = str(output)
    return exports


def wait_for_stable_output(output: Path, timeout: float = 30.0, interval: float = 0.25) -> bool:
    """等待 Electron 完成异步写盘；非空且连续两次大小一致才算成功。"""
    deadline = time.monotonic() + timeout
    last_size: int | None = None
    stable_count = 0
    while time.monotonic() < deadline:
        try:
            size = output.stat().st_size
        except OSError:
            size = 0
        if size > 0 and size == last_size:
            stable_count += 1
            if stable_count >= 2:
                return True
        else:
            stable_count = 0
        last_size = size
        time.sleep(interval)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="生成、校验并导出内置 Draw.io 论文模板")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build_source = build.add_mutually_exclusive_group(required=True)
    build_source.add_argument("--template")
    build_source.add_argument("--brief")
    build.add_argument("--output", required=True)
    build.add_argument("--labels-json")
    select = sub.add_parser("select")
    select.add_argument("--brief", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("source")
    validate.add_argument("--template")
    verify = sub.add_parser("verify-cli")
    verify.add_argument("--executable")
    verify.add_argument("--work-dir", required=True)
    verify.add_argument("--install", action="store_true")
    verify.add_argument("--portable-dir")
    export = sub.add_parser("export")
    export.add_argument("source")
    export.add_argument("--output-dir", required=True)
    export.add_argument("--executable")
    args = parser.parse_args()

    if args.command == "build":
        template_id = args.template
        if args.brief:
            brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
            template_id = choose_template(brief)
        labels = json.loads(Path(args.labels_json).read_text(encoding="utf-8")) if args.labels_json else {}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(build_xml(template_id, labels), encoding="utf-8")
        errors = validate_drawio(output, template_id)
        print(json.dumps({"ok": not errors, "template_id": template_id, "source": str(output), "errors": errors}, ensure_ascii=False))
        return 0 if not errors else 1
    if args.command == "select":
        brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
        print(choose_template(brief))
        return 0
    if args.command == "validate":
        errors = validate_drawio(Path(args.source), args.template)
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    if args.command == "verify-cli":
        executable = Path(args.executable) if args.executable else find_drawio()
        if executable and not executable.is_file():
            executable = None
        install_log: list[str] = []
        if not executable and args.install:
            if not args.portable_dir:
                parser.error("--install 需要 --portable-dir")
            executable, install_log = install_drawio(Path(args.portable_dir))
        if not executable:
            print(json.dumps({"ok": False, "error": "drawio_cli_missing", "install_log": install_log}, ensure_ascii=False))
            return 1
        result = verify_cli(executable, Path(args.work_dir))
        result["install_log"] = install_log
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    executable = Path(args.executable) if args.executable else find_drawio()
    if executable and not executable.is_file():
        executable = None
    if not executable:
        print(json.dumps({"ok": False, "error": "drawio_cli_missing"}, ensure_ascii=False))
        return 1
    source = Path(args.source)
    errors = validate_drawio(source)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False))
        return 1
    exports = export_drawio(executable, source, Path(args.output_dir))
    print(json.dumps({"ok": True, "exports": exports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
