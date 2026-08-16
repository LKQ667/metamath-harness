#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查项目锁定的 Draw.io / AI 非数据绘图契约。"""
from __future__ import annotations
import json
import hashlib
import struct
import binascii
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path
from common import project_arg, write_report

MODES = {"drawio", "ai"}
FLOW_TOKENS = ("flowchart", "roadmap", "技术路线", "路线图", "流程图", "问题分析")
AI_GENERATORS = {"imagegen", "image gen", "openai-imagegen"}
FIELDS = ("generator", "template_id", "source", "exports", "prompt_source", "paper_ready", "export_status", "needs_visual_review", "qa")
DRAWIO_QA = ("static_check_ok", "cli_export_ok", "content_ok", "cn_text_ok", "layout_ok", "edge_routing_ok", "node_overlap_ok", "text_fit_ok", "grayscale_ok", "single_column_ok", "double_column_ok", "paper_insert_ok")
AI_QA = ("content_consistency_ok", "cn_text_ok", "symbol_formula_ok", "crop_ok", "clarity_ok", "single_column_ok", "double_column_ok", "paper_insert_ok")


def load_object(path: Path) -> tuple[dict, list[str]]:
    if not path.exists():
        return {}, [f"缺少文件: {path.name}"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"{path.name} JSON 解析失败: {exc}"]
    return (value, []) if isinstance(value, dict) else ({}, [f"{path.name} 顶层必须是对象"])


def rel(value: object) -> str:
    return str(value or "").replace("\\", "/")


def flat(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {flat(child)}" for key, child in value.items())
    if isinstance(value, list):
        return " ".join(flat(child) for child in value)
    return str(value or "")


def is_flow(item: dict) -> bool:
    text = flat(item).lower()
    return "flowchart" in str(item.get("chart_family", "")).lower() or any(token in text for token in FLOW_TOKENS)


def is_python_data(item: dict) -> bool:
    return str(item.get("generator", "")).lower() == "python" and not is_flow(item)


def export_paths(item: dict) -> list[str]:
    value = item.get("exports")
    if isinstance(value, list):
        return [rel(path) for path in value]
    if isinstance(value, dict):
        return [rel(path) for path in value.values()]
    return []


def project_file(project: Path, value: object) -> Path | None:
    text = rel(value)
    if not text:
        return None
    candidate = (project / text).resolve()
    try:
        candidate.relative_to(project)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) >= 33 and data[:8] == b"\x89PNG\r\n\x1a\n":
        pos, width, height, channels, bit_depth = 8, 0, 0, 0, 0
        idat = bytearray()
        while pos + 12 <= len(data):
            length = struct.unpack(">I", data[pos:pos + 4])[0]
            kind = data[pos + 4:pos + 8]
            payload = data[pos + 8:pos + 8 + length]
            crc = data[pos + 8 + length:pos + 12 + length]
            if len(crc) != 4 or binascii.crc32(kind + payload) & 0xFFFFFFFF != struct.unpack(">I", crc)[0]:
                return None
            if kind == b"IHDR" and len(payload) == 13:
                width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
                if not (0 < width <= 20000 and 0 < height <= 20000):
                    return None
                channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type, 0)
            elif kind == b"IDAT":
                idat.extend(payload)
                if len(idat) > 100 * 1024 * 1024:
                    return None
            elif kind == b"IEND":
                break
            pos += 12 + length
        row_bytes = (width * channels * bit_depth + 7) // 8
        expected = (row_bytes + 1) * height
        if not channels or expected > 200 * 1024 * 1024:
            return None
        try:
            decoder = zlib.decompressobj()
            raw = decoder.decompress(bytes(idat), expected + 1)
        except Exception:
            return None
        if decoder.unconsumed_tail or not decoder.eof:
            return None
        if width and height and len(raw) == expected:
            return width, height
    return None


def drawio_errors(path: Path) -> list[str]:
    try:
        root = ET.parse(path).getroot()
    except Exception as exc:
        return [f"Draw.io XML 无法解析: {exc}"]
    errors: list[str] = []
    cells = root.findall(".//mxCell")
    ids = [cell.get("id", "") for cell in cells]
    if len(ids) != len(set(ids)):
        errors.append("Draw.io XML 存在重复 mxCell id")
    id_set = set(ids)
    boxes: list[tuple[str, float, float, float, float]] = []
    for cell in cells:
        style = cell.get("style", "")
        if cell.get("vertex") == "1":
            if cell.get("value") and "fontFamily=Microsoft YaHei" not in style:
                errors.append(f"节点 {cell.get('id')} 缺少 Microsoft YaHei")
            geo = cell.find("mxGeometry")
            if geo is not None:
                boxes.append((cell.get("id", ""), *(float(geo.get(key, "0")) for key in ("x", "y", "width", "height"))))
        if cell.get("edge") == "1":
            if cell.get("source") not in id_set or cell.get("target") not in id_set:
                errors.append(f"边 {cell.get('id')} 端点不存在")
            if "orthogonalEdgeStyle" not in style:
                errors.append(f"边 {cell.get('id')} 不是正交路由")
    for index, (a, ax, ay, aw, ah) in enumerate(boxes):
        for b, bx, by, bw, bh in boxes[index + 1:]:
            if ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by:
                errors.append(f"节点重叠: {a} 与 {b}")
    return errors


def paper_has(project: Path, paths: list[str]) -> bool:
    path = project / "论文" / "main.tex"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").replace("\\", "/")
    return any(Path(item).name in text or item in text for item in paths)


def common_entry(project: Path, item: dict, label: str, errors: list[str]) -> None:
    for field in FIELDS:
        if field not in item:
            errors.append(f"{label} 缺少统一字段 {field}")
    source = rel(item.get("source"))
    if not source or project_file(project, source) is None:
        errors.append(f"{label} source 不存在: {source}")
    paths = export_paths(item)
    if not paths:
        errors.append(f"{label} exports 为空或格式错误")
    for path in paths:
        if project_file(project, path) is None:
            errors.append(f"{label} 导出文件不存在: {path}")
    if item.get("paper_ready") is not True:
        errors.append(f"{label} 未标记 paper_ready=true")
    if item.get("needs_visual_review") is not False:
        errors.append(f"{label} 必须完成视觉复核")


def check_drawio(project: Path, items: list[dict], prompts: list[Path], errors: list[str]) -> None:
    non_data = [item for item in items if not is_python_data(item)]
    flows = [item for item in items if is_flow(item) and not is_python_data(item)]
    if not flows:
        errors.append("Draw.io 模式至少需要一张流程类图")
    if any(str(item.get("generator", "")).lower() in AI_GENERATORS for item in items):
        errors.append("Draw.io 模式不得混入 AI 成图条目")
    invalid = [item for item in non_data if str(item.get("generator", "")).lower() != "drawio"]
    if invalid:
        errors.append("Draw.io 模式存在 generator 不是 drawio 的非数据绘图条目")
    non_flow = [item for item in non_data if not is_flow(item)]
    if non_flow:
        errors.append("Draw.io 模式不得自动生成原理/模型/概念/示意图条目")
    if not 2 <= len(prompts) <= 4:
        errors.append(f"Draw.io 模式概念类提示词必须为 2–4 份，当前 {len(prompts)} 份")
    proof, proof_errors = load_object(project / "检查结果" / "drawio_cli_verification.json")
    errors.extend(proof_errors)
    if proof:
        executable = Path(str(proof.get("executable", "")))
        required_proof = proof.get("version_ok") is True and proof.get("source_ok") is True and proof.get("cn_text_ok") is True
        export_proof = isinstance(proof.get("exports"), dict) and all(proof["exports"].get(fmt) is True for fmt in ("png", "svg", "pdf"))
        recorded_hash = str(proof.get("executable_sha256", "")).lower()
        executable_ok = executable.is_file() and len(recorded_hash) == 64
        if executable_ok:
            executable_ok = hashlib.sha256(executable.read_bytes()).hexdigest() == recorded_hash
        version_recorded = isinstance(proof.get("version"), str) and bool(proof["version"].strip())
        if proof.get("ok") is not True or not executable_ok or not version_recorded or not required_proof or not export_proof:
            errors.append("Draw.io CLI 验证记录、可执行文件或四项验证证据不完整")
    for index, item in enumerate(flows, 1):
        label = f"Draw.io 流程图条目 {index}"
        common_entry(project, item, label, errors)
        source = rel(item.get("source"))
        if str(item.get("generator", "")).lower() != "drawio":
            errors.append(f"{label} generator 必须为 drawio")
        if not source.startswith("手绘图/") or not source.endswith(".drawio"):
            errors.append(f"{label} source 必须为 手绘图/*.drawio")
        elif project_file(project, source) is not None:
            errors.extend(f"{label}: {message}" for message in drawio_errors(project_file(project, source)))
        if not item.get("template_id"):
            errors.append(f"{label} 缺少 template_id")
        if not {".png", ".svg", ".pdf"}.issubset({Path(path).suffix.lower() for path in export_paths(item)}):
            errors.append(f"{label} 必须包含 2× PNG、SVG、PDF")
        if item.get("export_status") != "cli_exported":
            errors.append(f"{label} export_status 必须为 cli_exported")
        if item.get("export_scale") != 2:
            errors.append(f"{label} export_scale 必须为 2")
        qa = item.get("qa")
        if not isinstance(qa, dict):
            errors.append(f"{label} qa 必须是对象")
        else:
            for key in DRAWIO_QA:
                if qa.get(key) is not True:
                    errors.append(f"{label} QA 未通过 {key}")
        if not paper_has(project, export_paths(item)):
            errors.append(f"{label} 导出图未在论文中插入")


def check_ai(project: Path, items: list[dict], prompts: list[Path], errors: list[str]) -> None:
    loose_drawio = sorted((project / "手绘图").glob("*.drawio")) if (project / "手绘图").exists() else []
    if loose_drawio:
        errors.append("AI 模式的 手绘图/ 不得残留 .drawio 源文件")
    if any(str(item.get("generator", "")).lower() == "drawio" or rel(item.get("source")).endswith(".drawio") for item in items):
        errors.append("AI 模式不得混入 Draw.io 非数据绘图条目")
    invalid = [item for item in items if not is_python_data(item) and str(item.get("generator", "")).lower() not in AI_GENERATORS]
    if invalid:
        errors.append("AI 模式存在 generator 不是 imagegen 的非数据绘图条目")
    ai_items = [item for item in items if str(item.get("generator", "")).lower() in AI_GENERATORS]
    concepts = [item for item in ai_items if not is_flow(item)]
    if not 2 <= len(concepts) <= 4:
        errors.append(f"AI 模式概念类成图必须为 2–4 张，当前 {len(concepts)} 张")
    if not any(is_flow(item) for item in ai_items):
        errors.append("AI 模式必须另生成至少一张流程类图")
    mapping: dict[str, int] = {}
    for item in ai_items:
        prompt = rel(item.get("prompt_source"))
        if prompt:
            mapping[prompt] = mapping.get(prompt, 0) + 1
    expected = {path.relative_to(project).as_posix() for path in prompts}
    for prompt in expected:
        if mapping.get(prompt) != 1:
            errors.append(f"提示词必须且只能对应一张 AI 成图: {prompt}")
    if set(mapping) != expected:
        errors.append("AI manifest 提示词集合与 手绘图/*.md 不一致")
    for index, item in enumerate(ai_items, 1):
        label = f"AI 成图条目 {index}"
        common_entry(project, item, label, errors)
        if item.get("template_id") not in (None, "", "imagegen"):
            errors.append(f"{label} template_id 应为空或 imagegen")
        if item.get("export_status") != "generated":
            errors.append(f"{label} export_status 必须为 generated")
        source = rel(item.get("source"))
        source_path = project_file(project, source)
        size = image_size(source_path) if source_path else None
        if size is None:
            errors.append(f"{label} 图像不可严格解码为 PNG: {source}")
        elif size[0] < 1200 or size[1] < 800:
            errors.append(f"{label} 尺寸不足 1200×800: {size[0]}×{size[1]}")
        qa = item.get("qa")
        if not isinstance(qa, dict):
            errors.append(f"{label} qa 必须是对象")
        else:
            for key in AI_QA:
                if qa.get(key) is not True:
                    errors.append(f"{label} QA 未通过 {key}")
        if not paper_has(project, [source, *export_paths(item)]):
            errors.append(f"{label} 未在论文中插入")


def main() -> int:
    parser = project_arg("检查项目级 Draw.io / AI 全自动双绘图契约")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    state, errors = load_object(project / "项目状态.json")
    manifest, manifest_errors = load_object(project / "figures" / "manifest.json")
    errors.extend(manifest_errors)
    state_mode = state.get("drawing_mode")
    manifest_mode = manifest.get("drawing_mode")
    if state_mode not in MODES:
        errors.append("项目状态缺少有效 drawing_mode；旧项目必须补问，不得猜测")
    if manifest_mode not in MODES:
        errors.append("manifest 顶层缺少有效 drawing_mode")
    if state_mode != manifest_mode:
        errors.append("项目状态与 manifest 的 drawing_mode 不一致")
    if state.get("drawing_mode_locked") is not True or state.get("drawing_mode_confirmed") is not True:
        errors.append("项目绘图模式未记录为已确认并锁定")
    if manifest.get("drawing_mode_locked") is not True:
        errors.append("manifest 顶层 drawing_mode_locked 必须为 true")
    raw_items = manifest.get("items", manifest.get("figures"))
    if not isinstance(raw_items, list):
        errors.append("manifest 顶层必须包含 items 列表")
        items: list[dict] = []
    else:
        items = [item for item in raw_items if isinstance(item, dict)]
        if len(items) != len(raw_items):
            errors.append("manifest 条目必须全部为对象")
    hand = project / "手绘图"
    prompts = sorted(path for path in hand.glob("*.md") if path.name.lower() != "readme.md") if hand.exists() else []
    for prompt in prompts:
        if not prompt.read_text(encoding="utf-8", errors="replace").strip():
            errors.append(f"提示词文件为空: {prompt.relative_to(project)}")
    if state_mode == "drawio":
        check_drawio(project, items, prompts, errors)
    elif state_mode == "ai":
        check_ai(project, items, prompts, errors)
    return write_report(not errors, "check_drawing_contract", errors, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
