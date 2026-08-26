#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""静态验收数学建模论文 draw.io 图：XML、逻辑连接、布局、manifest 与导出文件。"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

MIN_PNG_BYTES = 1024
MOJIBAKE = ("\ufffd", "ï»¿", "Ã", "â€")
REQUIRED_CJK_STYLE = ("html=1", "whiteSpace=wrap", "fontFamily=Microsoft YaHei")

DRAWING_DIR = Path(__file__).resolve().parent / "drawing"
if str(DRAWING_DIR) not in sys.path:
    sys.path.insert(0, str(DRAWING_DIR))
from drawio_pipeline import ROADMAP_TEMPLATE_IDS, template_structure_errors


@dataclass
class Box:
    ident: str
    x: float
    y: float
    w: float
    h: float
    value: str
    style: str = ""

    def overlaps(self, other: "Box", gap: float = 0) -> bool:
        return self.x < other.x + other.w + gap and self.x + self.w + gap > other.x and self.y < other.y + other.h + gap and self.y + self.h + gap > other.y

    def contains(self, other: "Box") -> bool:
        return self.x <= other.x and self.y <= other.y and self.x + self.w >= other.x + other.w and self.y + self.h >= other.y + other.h

    def partial_overlaps(self, other: "Box") -> bool:
        """部分相交：有交集且互不完全嵌套。"""
        if self.contains(other) or other.contains(self):
            return False
        return self.overlaps(other)


def add(items: list[str], msg: str) -> None:
    items.append(msg)


def text_of(cell: ET.Element) -> str:
    return " ".join(cell.attrib.get("value", "").replace("<br>", " ").split())


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def is_roadmap(item: dict) -> bool:
    text = json.dumps(item, ensure_ascii=False).lower()
    return str(item.get("chart_family", "")).lower() == "roadmap" or any(
        token in text for token in ("roadmap", "技术路线", "路线图")
    )


def parse_box(cell: ET.Element) -> Box | None:
    geo = cell.find("mxGeometry")
    if geo is None:
        return None
    try:
        return Box(cell.attrib["id"], float(geo.attrib.get("x", 0)), float(geo.attrib.get("y", 0)), float(geo.attrib.get("width", 0)), float(geo.attrib.get("height", 0)), text_of(cell), cell.attrib.get("style", ""))
    except ValueError:
        return None


def validate_png(path: Path, errors: list[str]) -> None:
    if path.stat().st_size < MIN_PNG_BYTES:
        add(errors, f"PNG 过小或无效: {path}")
        return
    try:
        with path.open("rb") as f:
            header = f.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            add(errors, f"PNG 头无效: {path}")
            return
        width, height = struct.unpack(">II", header[16:24])
        if width < 800 or height < 400:
            add(errors, f"PNG 分辨率过低（{width}×{height}）: {path}")
    except OSError as exc:
        add(errors, f"PNG 无法读取: {path}: {exc}")


def validate_xml(path: Path, errors: list[str], warnings: list[str]) -> None:
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        add(errors, f"XML 解析失败: {path}: {exc}")
        return
    cells = root.findall(".//mxCell")
    diagram = root.find(".//diagram")
    template_id = diagram.get("id", "") if diagram is not None else ""
    fingerprinted_roadmap = template_id in ROADMAP_TEMPLATE_IDS
    by_id: dict[str, ET.Element] = {}
    boxes: list[Box] = []
    edges: list[ET.Element] = []
    for cell in cells:
        ident = cell.attrib.get("id")
        if not ident:
            add(errors, f"存在无 id 的 mxCell: {path}")
            continue
        if ident in by_id:
            add(errors, f"重复 id {ident}: {path}")
        by_id[ident] = cell
        value = text_of(cell)
        if any(x in value for x in MOJIBAKE):
            add(errors, f"疑似乱码标签 {ident}: {value}")
        if cell.attrib.get("vertex") == "1":
            style = cell.attrib.get("style", "")
            if value and has_cjk(value) and any(k not in style for k in REQUIRED_CJK_STYLE):
                add(errors, f"文字节点 {ident} 缺少中文文本样式: {value}")
            is_container = "swimlane" in style
            box = parse_box(cell)
            if box is None or box.w <= 0 or box.h <= 0:
                add(errors, f"节点 {ident} 几何信息无效")
            else:
                if not is_container:
                    boxes.append(box)
                if box.x < 0 or box.y < 0:
                    add(errors, f"节点 {ident} 位于画布外: ({box.x}, {box.y})")
                if value and len(re.sub(r"<[^>]+>", "", value)) > 100 and box.w < 220:
                    add(warnings, f"长标签可能截断，建议加宽或换行: {ident} {value}")
        if cell.attrib.get("edge") == "1":
            edges.append(cell)
    if not {"0", "1"}.issubset(by_id):
        add(errors, f"缺少根 cell 0/1: {path}")
    for edge in edges:
        ident = edge.attrib.get("id", "?")
        source, target = edge.attrib.get("source"), edge.attrib.get("target")
        style = edge.attrib.get("style", "")
        if source or target:
            # 连接边：已声明端点必须存在，且需显式箭头（路由样式不再强制正交）
            if source is not None and source not in by_id:
                add(errors, f"边 {ident} 指向不存在节点: {source} -> {target}")
            if target is not None and target not in by_id:
                add(errors, f"边 {ident} 指向不存在节点: {source} -> {target}")
            if "endArrow=" not in style:
                add(errors, f"边 {ident} 缺少明确箭头")
        # 悬浮边（无 source 且无 target，靠 sourcePoint/targetPoint 定位）豁免端点与路由检查
        if source == target and source is not None:
            add(warnings, f"边 {ident} 是自环，需确认其是否真表示反馈")
        if edge.find("mxGeometry") is None:
            add(errors, f"边 {ident} 缺少 mxGeometry")
    for i, left in enumerate(boxes):
        for right in boxes[i + 1:]:
            if left.partial_overlaps(right):
                # 装饰豁免：完全嵌套合法；部分相交仅当双方有值且均为实体盒（非 text; 非 dashed）才报错
                if left.value and right.value:
                    if not left.style.startswith("text;") and not right.style.startswith("text;"):
                        if "dashed=1" not in left.style and "dashed=1" not in right.style:
                            add(errors, f"节点重叠: {left.ident}（{left.value}）与 {right.ident}（{right.value}）")
            elif not fingerprinted_roadmap and left.overlaps(right, gap=20):
                add(warnings, f"节点间距不足 20px: {left.ident} 与 {right.ident}")
    # 同一 source-target 反复连线往往导致边叠加；允许方向相反的反馈边；无 source 悬浮边不参与。
    seen: set[tuple[str | None, str | None]] = set()
    for edge in edges:
        if edge.attrib.get("source") is None:
            continue
        pair = (edge.attrib.get("source"), edge.attrib.get("target"))
        if pair in seen:
            add(errors, f"重复边，可能箭头重叠: {pair[0]} -> {pair[1]}")
        seen.add(pair)


def load_manifest(project: Path, errors: list[str]) -> list[dict]:
    path = project / "figures" / "manifest.json"
    if not path.exists():
        add(errors, f"缺少 manifest: {path}")
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        add(errors, f"manifest JSON 无效: {exc}")
        return []
    items = data.get("items", data.get("figures", [])) if isinstance(data, dict) else data
    if not isinstance(items, list):
        add(errors, "manifest 必须是列表或含 figures 的对象")
        return []
    return items


def validate_project(project: Path, strict: bool) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    hand = project / "手绘图"
    if not hand.is_dir():
        return False, [f"缺少手绘图目录: {hand}"], warnings
    drawios = list(hand.glob("*.drawio"))
    if not drawios:
        add(errors, f"手绘图目录缺少 .drawio 源文件: {hand}")
    for source in drawios:
        validate_xml(source, errors, warnings)
    for item in load_manifest(project, errors):
        if not isinstance(item, dict):
            add(errors, "manifest 条目必须是对象")
            continue
        missing = [k for k in ("id", "title", "purpose", "section", "source", "exports", "paper_ready", "checks", "export_status", "needs_visual_review") if k not in item]
        if missing:
            add(errors, f"manifest 条目缺少字段 {missing}: {item.get('source', '?')}")
        source = project / str(item.get("source", ""))
        if not source.exists():
            add(errors, f"manifest source 不存在: {item.get('source')}")
        if is_roadmap(item):
            template_id = str(item.get("template_id") or "")
            if template_id not in ROADMAP_TEMPLATE_IDS:
                add(errors, f"技术路线图 template_id 必须属于新四类模板: {template_id or '<空>'}")
            elif source.is_file():
                for message in template_structure_errors(source, template_id):
                    add(errors, f"技术路线图模板结构不一致: {message}")
        exports = item.get("exports") or []
        if not exports:
            add(errors, f"manifest 缺少 exports: {item.get('source')}")
        for rel in exports:
            export = project / rel
            if not export.exists():
                add(errors, f"manifest export 不存在: {rel}")
            elif export.suffix.lower() == ".png":
                validate_png(export, errors)
        if item.get("paper_ready") is True and (item.get("needs_visual_review") is True or item.get("export_status") != "ok"):
            add(errors, f"paper_ready 与视觉/导出状态矛盾: {item.get('source')}")
    if strict and warnings:
        errors.extend(f"严格模式警告: {w}" for w in warnings)
    return not errors, errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--strict", action="store_true", help="将布局警告视为失败")
    args = parser.parse_args()
    ok, errors, warnings = validate_project(Path(args.project).resolve(), args.strict)
    print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
