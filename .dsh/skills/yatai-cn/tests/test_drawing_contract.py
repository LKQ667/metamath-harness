#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import binascii
import json
import importlib.util
import shutil
import struct
import subprocess
import sys
import unittest
import uuid
from unittest import mock
import zlib
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
CHECK = SKILL / "scripts" / "checks" / "check_drawing_contract.py"
PIPELINE = SKILL / "scripts" / "drawing" / "drawio_pipeline.py"
DRAWIO = Path(r"D:\draw.io\draw.io.exe")
TEMP_ROOT = Path(r"D:\CodexTemp\dual-drawing-contract-tests") / SKILL.name


def chunk(kind: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def write_png(path: Path, width: int = 1200, height: int = 800) -> None:
    row = b"\x00" + b"\xF5\xF7\xF9" * width
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(row * height, 9))
    data += chunk(b"IEND", b"")
    path.write_bytes(data)


def qa_drawio() -> dict:
    keys = (
        "static_check_ok", "cli_export_ok", "content_ok", "cn_text_ok", "layout_ok",
        "edge_routing_ok", "node_overlap_ok", "text_fit_ok", "grayscale_ok",
        "single_column_ok", "double_column_ok", "paper_insert_ok", "color_palette_ok",
        "visual_density_ok", "style_not_stiff_ok",
    )
    return {key: True for key in keys}


def qa_ai() -> dict:
    keys = (
        "content_consistency_ok", "content_ok", "cn_text_ok", "symbol_formula_ok",
        "crop_ok", "clarity_ok", "single_column_ok", "double_column_ok",
        "paper_insert_ok", "color_palette_ok", "visual_density_ok", "edge_routing_ok",
        "node_overlap_ok", "text_fit_ok", "style_not_stiff_ok", "layout_ok",
    )
    return {key: True for key in keys}


class DrawingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.project = TEMP_ROOT / uuid.uuid4().hex
        for name in ("手绘图", "figures", "论文", "检查结果"):
            (self.project / name).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        resolved = self.project.resolve()
        if str(resolved).lower().startswith(str(TEMP_ROOT.resolve()).lower()):
            shutil.rmtree(resolved, ignore_errors=True)

    def run_check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CHECK), "--project", str(self.project)], text=True, capture_output=True)

    def write_state(self, mode: str) -> None:
        state = {"drawing_mode": mode, "drawing_mode_locked": True, "drawing_mode_confirmed": True}
        (self.project / "项目状态.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def test_ai_positive_with_python_data_figure(self) -> None:
        self.write_state("ai")
        items = []
        tex_refs = []
        for index, (stem, family) in enumerate((("原理图", "principle"), ("模型图", "model"), ("技术路线图", "flowchart")), 1):
            prompt = self.project / "手绘图" / f"{stem}.md"
            prompt.write_text("## 服务段落\n正文\n## 生成图片的提示词\n科研图\n## 硬约束\n中文", encoding="utf-8")
            image = self.project / "手绘图" / f"{stem}.png"
            write_png(image)
            rel_prompt = prompt.relative_to(self.project).as_posix()
            rel_image = image.relative_to(self.project).as_posix()
            items.append({
                "id": f"ai-{index}", "title": stem, "chart_family": family,
                "generator": "imagegen", "template_id": "imagegen", "source": rel_image,
                "exports": [rel_image], "prompt_source": rel_prompt, "paper_ready": True,
                "export_status": "generated", "needs_visual_review": False, "qa": qa_ai(),
            })
            tex_refs.append(image.name)
        data_source = self.project / "figures" / "data.py"
        data_source.write_text("print('data')", encoding="utf-8")
        write_png(self.project / "figures" / "data.png")
        (self.project / "figures" / "data.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        (self.project / "figures" / "data.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
        items.append({"id": "data", "chart_family": "trend", "generator": "python", "template_id": "trend-confidence", "source": "figures/data.py", "exports": ["figures/data.png", "figures/data.svg", "figures/data.pdf"], "paper_ready": True, "qa": {"cn_text_ok": True, "export_ok": True, "editable_text_ok": True}})
        manifest = {"drawing_mode": "ai", "drawing_mode_locked": True, "items": items}
        (self.project / "figures" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (self.project / "论文" / "main.tex").write_text("\n".join(tex_refs), encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 0)
        for name in ("check_python_figure_contract.py", "check_python_figure_quality.py", "check_python_bar_chart_policy.py"):
            result = subprocess.run([sys.executable, str(SKILL / "scripts" / "checks" / name), "--project", str(self.project)], capture_output=True)
            self.assertEqual(result.returncode, 0, name)

    def test_ai_missing_image_and_fake_png_fail(self) -> None:
        self.write_state("ai")
        prompts = []
        items = []
        for index, (stem, family) in enumerate((("原理图", "principle"), ("模型图", "model"), ("技术路线图", "flowchart")), 1):
            prompt = self.project / "手绘图" / f"{stem}.md"
            prompt.write_text("prompt", encoding="utf-8")
            prompts.append(prompt)
            image = self.project / "手绘图" / f"{stem}.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
            items.append({
                "chart_family": family, "generator": "imagegen", "template_id": "imagegen",
                "source": image.relative_to(self.project).as_posix(),
                "exports": [image.relative_to(self.project).as_posix()],
                "prompt_source": prompt.relative_to(self.project).as_posix(),
                "paper_ready": True, "export_status": "generated",
                "needs_visual_review": False, "qa": qa_ai(),
            })
        (self.project / "figures" / "manifest.json").write_text(json.dumps({"drawing_mode": "ai", "drawing_mode_locked": True, "items": items}, ensure_ascii=False), encoding="utf-8")
        (self.project / "论文" / "main.tex").write_text("技术路线图.png", encoding="utf-8")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不可严格解码", result.stdout)

    @unittest.skipUnless(DRAWIO.is_file(), "本机未安装 Draw.io CLI")
    def test_drawio_positive_and_mixed_mode_fail(self) -> None:
        self.write_state("drawio")
        for name in ("原理图.md", "模型图.md"):
            (self.project / "手绘图" / name).write_text("prompt", encoding="utf-8")
        source = self.project / "手绘图" / "技术路线图.drawio"
        subprocess.run([sys.executable, str(PIPELINE), "build", "--template", "horizontal-stage-chain", "--output", str(source)], check=True, capture_output=True)
        subprocess.run([sys.executable, str(PIPELINE), "export", str(source), "--output-dir", str(source.parent), "--executable", str(DRAWIO)], check=True, capture_output=True)
        verification = subprocess.run([sys.executable, str(PIPELINE), "verify-cli", "--executable", str(DRAWIO), "--work-dir", str(self.project / "检查结果" / "cli")], check=True, text=True, capture_output=True)
        (self.project / "检查结果" / "drawio_cli_verification.json").write_text(verification.stdout, encoding="utf-8")
        item = {
            "title": "技术路线图", "chart_family": "flowchart", "generator": "drawio",
            "template_id": "horizontal-stage-chain", "source": "手绘图/技术路线图.drawio",
            "exports": ["手绘图/技术路线图.png", "手绘图/技术路线图.svg", "手绘图/技术路线图.pdf"],
            "prompt_source": None, "paper_ready": True, "export_status": "cli_exported",
            "export_scale": 2, "needs_visual_review": False, "qa": qa_drawio(),
        }
        manifest = {"drawing_mode": "drawio", "drawing_mode_locked": True, "items": [item]}
        manifest_path = self.project / "figures" / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (self.project / "论文" / "main.tex").write_text("技术路线图.png", encoding="utf-8")
        self.assertEqual(self.run_check().returncode, 0)
        manifest["items"].append({
            "chart_family": "model", "generator": "imagegen", "source": "手绘图/技术路线图.png",
            "exports": ["手绘图/技术路线图.png"], "prompt_source": "手绘图/模型图.md",
        })
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_ai_rejects_loose_drawio_and_unknown_generator(self) -> None:
        self.write_state("ai")
        (self.project / "手绘图" / "残留.drawio").write_text("<mxfile/>", encoding="utf-8")
        manifest = {
            "drawing_mode": "ai", "drawing_mode_locked": True,
            "items": [{"generator": "manual", "chart_family": "model"}],
        }
        (self.project / "figures" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不得残留 .drawio", result.stdout)
        self.assertIn("generator 不是 imagegen", result.stdout)

    def test_missing_mode_and_install_failure_are_hard_failures(self) -> None:
        (self.project / "figures" / "manifest.json").write_text('{"items":[]}', encoding="utf-8")
        self.assertNotEqual(self.run_check().returncode, 0)
        result = subprocess.run([sys.executable, str(PIPELINE), "verify-cli", "--executable", str(self.project / "missing.exe"), "--work-dir", str(self.project / "检查结果" / "none")], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("drawio_cli_missing", result.stdout)

    def test_official_portable_install_failure_is_recorded(self) -> None:
        spec = importlib.util.spec_from_file_location("drawio_pipeline_under_test", PIPELINE)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        with mock.patch.object(module.shutil, "which", return_value=None), mock.patch.object(module.urllib.request, "urlopen", side_effect=OSError("offline")):
            executable, log = module.install_drawio(self.project / "portable")
        self.assertIsNone(executable)
        self.assertTrue(any("portable_download_failed" in item for item in log))


if __name__ == "__main__":
    unittest.main()
