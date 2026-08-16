#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置 Draw.io 模板生成、静态校验、CLI 探测/安装与导出验证。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
}
FONT = "Microsoft YaHei"
TEMPLATE_FILE = Path(__file__).resolve().parents[2] / "assets" / "drawio" / "template_library.json"
SKILL_NAME = Path(__file__).resolve().parents[2].name


def load_library() -> dict:
    return json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))


def choose_template(brief: dict) -> str:
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


def build_xml(template_id: str, labels: dict[str, str] | None = None) -> str:
    library = load_library()
    template = next((item for item in library["templates"] if item["id"] == template_id), None)
    if template is None:
        raise ValueError(f"未知模板: {template_id}")
    labels = labels or {}
    page = template["page"]
    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net", "agent": SKILL_NAME, "version": "24.7.17"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": template_id, "name": template["name"]})
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1200", "dy": "800", "grid": "1", "gridSize": "10", "guides": "1",
            "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1",
            "pageScale": "1", "pageWidth": str(page["width"]), "pageHeight": str(page["height"]),
            "math": "0", "shadow": "0",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    node_map = {node[0]: node for node in template["nodes"]}
    for node_id, label, x, y, width, height, role in template["nodes"]:
        cell = ET.SubElement(
            root,
            "mxCell",
            {"id": node_id, "value": labels.get(node_id, label), "style": vertex_style(role), "vertex": "1", "parent": "1"},
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(width), "height": str(height), "as": "geometry"})
    for index, (source, target, label) in enumerate(template["edges"]):
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"e{index + 1}", "value": label, "style": edge_style(node_map[source], node_map[target]),
                "edge": "1", "parent": "1", "source": source, "target": target,
            },
        )
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    ET.indent(mxfile, space="  ")
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=False)


def validate_drawio(path: Path) -> list[str]:
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
    boxes: list[tuple[str, float, float, float, float]] = []
    for cell in cells:
        if cell.get("vertex") == "1":
            style = cell.get("style", "")
            value = cell.get("value", "")
            if value and f"fontFamily={FONT}" not in style:
                errors.append(f"节点 {cell.get('id')} 缺少中文字体")
            if value and "whiteSpace=wrap" not in style:
                errors.append(f"节点 {cell.get('id')} 未启用自动换行")
            geo = cell.find("mxGeometry")
            if geo is not None:
                try:
                    boxes.append((cell.get("id", ""), *(float(geo.get(k, "0")) for k in ("x", "y", "width", "height"))))
                except ValueError:
                    errors.append(f"节点 {cell.get('id')} 几何值无效")
        if cell.get("edge") == "1":
            if cell.get("source") not in id_set or cell.get("target") not in id_set:
                errors.append(f"边 {cell.get('id')} 端点不存在")
            style = cell.get("style", "")
            if "orthogonalEdgeStyle" not in style:
                errors.append(f"边 {cell.get('id')} 不是正交路由")
            if "endArrow=block" not in style:
                errors.append(f"边 {cell.get('id')} 缺少明确箭头")
    for index, (a_id, ax, ay, aw, ah) in enumerate(boxes):
        for b_id, bx, by, bw, bh in boxes[index + 1:]:
            if ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by:
                errors.append(f"节点重叠: {a_id} 与 {b_id}")
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
    build.add_argument("--template", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--labels-json")
    select = sub.add_parser("select")
    select.add_argument("--brief", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("source")
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
        labels = json.loads(Path(args.labels_json).read_text(encoding="utf-8")) if args.labels_json else {}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(build_xml(args.template, labels), encoding="utf-8")
        errors = validate_drawio(output)
        print(json.dumps({"ok": not errors, "template_id": args.template, "source": str(output), "errors": errors}, ensure_ascii=False))
        return 0 if not errors else 1
    if args.command == "select":
        brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
        print(choose_template(brief))
        return 0
    if args.command == "validate":
        errors = validate_drawio(Path(args.source))
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
