#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

import latex_runtime


class LatexRuntimeTests(unittest.TestCase):
    def test_ascii_path(self) -> None:
        self.assertTrue(latex_runtime.is_ascii_path(Path(r"F:\math-paper-cn-runtime")))
        self.assertFalse(latex_runtime.is_ascii_path(Path(r"F:\数学建模")))

    def test_override_must_be_outside_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            with patch.dict(os.environ, {latex_runtime.RUNTIME_ENV: str(project / "runtime")}):
                with self.assertRaises(latex_runtime.LatexRuntimeError):
                    latex_runtime.choose_runtime_root(project, minimum_free_bytes=1)

    def test_parse_sha512(self) -> None:
        value = "a" * 128
        self.assertEqual(latex_runtime.parse_sha512(f"{value}  install-tl.zip"), value)

    def test_probe_does_not_create_managed_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = base / "project"
            project.mkdir()
            runtime = base / "runtime" / "texlive"
            with (
                patch.dict(os.environ, {latex_runtime.RUNTIME_ENV: str(runtime)}),
                patch("latex_runtime.shutil.which", return_value=None),
            ):
                self.assertIsNone(latex_runtime.discover(project))
            self.assertFalse(runtime.parent.exists())

    def test_render_profile_uses_current_texlive_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "profile"
            latex_runtime.render_profile(Path(r"F:\math-paper-cn-runtime\texlive-2026"), output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("binary_windows 1", text)
            self.assertIn("tlpdbopt_install_docfiles 0", text)
            self.assertIn("TEXMFSYSVAR F:/math-paper-cn-runtime/texlive-2026/texmf-var", text)

    def test_bundled_template_has_compile_boundary(self) -> None:
        template = latex_runtime.SKILL_ROOT / "assets" / "templates" / "main.tex"
        self.assertIn("\\begin{document}", template.read_text(encoding="utf-8"))

    def test_missing_packages(self) -> None:
        log = "! LaTeX Error: File `foo.sty' not found.\n! LaTeX Error: File `bar.cls' not found."
        self.assertEqual(latex_runtime.missing_packages(log), ["foo.sty", "bar.cls"])

    def test_offline_package_requires_valid_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "runtime.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("texlive/bin/windows/xelatex.exe", b"x")
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            archive.with_suffix(".zip.sha256").write_text(checksum, encoding="utf-8")
            target = root / "target" / "texlive"
            with patch.dict(os.environ, {latex_runtime.OFFLINE_ENV: str(archive)}):
                self.assertTrue(latex_runtime.install_offline(target))

    def test_safe_extract_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", b"x")
            with zipfile.ZipFile(archive) as bundle:
                with self.assertRaises(latex_runtime.LatexRuntimeError):
                    latex_runtime.safe_extract(bundle, root / "output")

    def test_installer_rotates_mirror_and_reuses_verified_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            payload = b"verified-installer"
            digest = hashlib.sha512(payload).hexdigest()
            calls: list[str] = []

            def fake_download(url: str, output: Path, timeout: int = 120) -> None:
                calls.append(url)
                if "mirror-one" in url:
                    raise urllib.error.URLError("mirror unavailable")
                output.write_bytes(payload) if output.name.endswith(".zip") else output.write_text(digest, encoding="utf-8")

            with patch("latex_runtime.download", side_effect=fake_download):
                archive = latex_runtime.download_verified_installer(
                    work,
                    ("https://mirror-one", "https://mirror-two"),
                )
            self.assertEqual(archive.read_bytes(), payload)
            self.assertTrue(any("mirror-one" in url for url in calls))
            self.assertTrue(any("mirror-two" in url for url in calls))
            with patch("latex_runtime.download", side_effect=AssertionError("不应重复下载")):
                cached = latex_runtime.download_verified_installer(work, ("https://mirror-one",))
            self.assertEqual(cached, archive)


if __name__ == "__main__":
    unittest.main()
