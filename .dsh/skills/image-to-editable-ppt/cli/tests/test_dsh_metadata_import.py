"""editppt image import 的 DSH 元数据来源校验测试（§7.3 六项 + 兼容性）。"""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = CLI_DIR / "editppt" / "runtime"
RECORD = RUNTIME_DIR / "record_imagegen_result.py"

FAKE_KEY = "sk-fixture123"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR-fixture"
CONNECTION_ID = "img_mti303k7_e0224219"
CONTRACT = {
    "backend_id": "dsh-current",
    "tool_name": "editable_ppt_image",
    "connection_binding": "run-start-pinned",
    "connection_id": CONNECTION_ID,
    "connection_name": "tokenbom-image2",
    "model": "gpt-image-2",
    "protocol": "openai-images",
    "requires_openai_api_key": False,
    "allow_codex": False,
    "fallback_policy": "none",
    "mode_policy": "generate-or-edit-per-asset",
    "save_path_policy": "write one output directly inside the owning page directory",
    "handoff_rule": "call editable_ppt_image serially with the pinned connectionId; never call editppt image generate/edit",
}


def make_run(root: Path, backend: dict):
    run = root / "run"
    page = run / "pages" / "page_001"
    (page / "assets").mkdir(parents=True)
    (run / "deck_manifest.json").write_text(json.dumps({"image_backend": backend}), encoding="utf-8")
    (page / "imagegen-jobs.json").write_text(json.dumps({"schema_version": 1, "jobs": []}), encoding="utf-8")
    source = run / "generated.png"
    source.write_bytes(PNG_BYTES)
    return run, page, source


def metadata_for(dest: Path, **overrides) -> dict:
    meta = {
        "schema": "dsh.mathmodel.editable-ppt-image-metadata/v1",
        "createdAt": "2026-09-02T03:00:00.000Z",
        "connectionId": CONNECTION_ID,
        "connectionName": "tokenbom-image2",
        "template": "openai-compatible",
        "model": "gpt-image-2",
        "protocol": "openai-images",
        "operation": "edit",
        "promptSha256": hashlib.sha256(b"prompt").hexdigest(),
        "inputSha256": [hashlib.sha256(PNG_BYTES).hexdigest()],
        "size": "auto",
        "quality": None,
        "files": [{"file": dest.name, "sha256": hashlib.sha256(PNG_BYTES).hexdigest(), "mime": "image/png"}],
    }
    meta.update(overrides)
    return meta


class ImportMetadataTests(unittest.TestCase):
    def run_import(self, page: Path, extra):
        return subprocess.run(
            [sys.executable, str(RECORD), str(page), "--job-id", "job-1",
             "--source-image", str(self.source), "--dest", "assets/base.png", "--role", "clean_base", *extra],
            capture_output=True, text=True,
        )

    def test_happy_path_records_provenance_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, page, source = make_run(root, CONTRACT)
            self.source = source
            dest = page / "assets" / "base.png"
            meta_path = page / "assets" / "base.dsh-image.json"
            meta_path.write_text(json.dumps(metadata_for(dest)), encoding="utf-8")
            proc = self.run_import(page, ["--metadata-file", str(meta_path), "--note", "DSH current connection; run-pinned"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            jobs = json.loads((page / "imagegen-jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(len(jobs["jobs"]), 1)
            job = jobs["jobs"][0]
            self.assertEqual(job["status"], "recorded")
            self.assertEqual(job["output"], "assets/base.png")
            self.assertEqual(job["output_sha256"], hashlib.sha256(PNG_BYTES).hexdigest())
            self.assertEqual(job["metadata_file"], "assets/base.dsh-image.json")
            self.assertEqual(len(job["metadata_sha256"]), 64)
            self.assertEqual(job["connection_id"], CONNECTION_ID)
            self.assertEqual(job["model"], "gpt-image-2")
            self.assertEqual(job["protocol"], "openai-images")
            serialized = json.dumps(jobs)
            for banned in (FAKE_KEY, "baseUrl", "credentialRef", "://"):
                self.assertNotIn(banned, serialized)

    def test_metadata_outside_page_dir_is_copied_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, page, source = make_run(root, CONTRACT)
            self.source = source
            dest = page / "assets" / "base.png"
            meta_path = run / "detached.dsh-image.json"
            meta_path.write_text(json.dumps(metadata_for(dest)), encoding="utf-8")
            proc = self.run_import(page, ["--metadata-file", str(meta_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            job = json.loads((page / "imagegen-jobs.json").read_text(encoding="utf-8"))["jobs"][0]
            self.assertTrue(job["metadata_file"].startswith("assets/"))
            self.assertTrue((page / job["metadata_file"]).is_file())

    def _expect_reject(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, page, source = make_run(root, CONTRACT)
            self.source = source
            dest = page / "assets" / "base.png"
            meta = metadata_for(dest)
            mutate(meta, dest)
            meta_path = page / "assets" / "base.dsh-image.json"
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            proc = self.run_import(page, ["--metadata-file", str(meta_path)])
            self.assertNotEqual(proc.returncode, 0, "校验失败必须拒绝登记")
            jobs = json.loads((page / "imagegen-jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(jobs["jobs"], [], "拒绝后不得写入任何 job")
            self.assertFalse(dest.exists(), "provenance 失败不得把未验证资产复制进页面目录")
            self.assertIn("DSH metadata provenance rejected", proc.stderr + proc.stdout)

    def test_reject_wrong_connection(self):
        self._expect_reject(lambda meta, dest: meta.update(connectionId="img_otherconn_0000"))

    def test_reject_hash_tamper(self):
        self._expect_reject(lambda meta, dest: meta["files"].__setitem__(0, {**meta["files"][0], "sha256": "0" * 64}))

    def test_reject_wrong_protocol_or_model(self):
        self._expect_reject(lambda meta, dest: meta.update(protocol="codex-images"))
        self._expect_reject(lambda meta, dest: meta.update(model="other-model"))

    def test_reject_unknown_or_sensitive_fields(self):
        self._expect_reject(lambda meta, dest: meta.update(baseUrl="https://gateway.invalid/v1"))
        self._expect_reject(lambda meta, dest: meta.update(apiKey=FAKE_KEY))

    def test_reject_secret_value_nested(self):
        self._expect_reject(lambda meta, dest: meta.update(connectionName=f"ok {FAKE_KEY}"))

    def test_reject_wrong_schema(self):
        self._expect_reject(lambda meta, dest: meta.update(schema="other/v1"))

    def test_dsh_run_requires_metadata_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, page, source = make_run(root, CONTRACT)
            self.source = source
            proc = self.run_import(page, [])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("--metadata-file", proc.stderr + proc.stdout)

    def test_malformed_deck_manifest_fails_closed_before_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, page, source = make_run(root, CONTRACT)
            self.source = source
            (run / "deck_manifest.json").write_text("{broken", encoding="utf-8")
            proc = self.run_import(page, [])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("运行清单无法解析", proc.stderr + proc.stdout)
            self.assertFalse((page / "assets" / "base.png").exists())
            jobs = json.loads((page / "imagegen-jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(jobs["jobs"], [])

    def test_legacy_run_keeps_old_params(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = {"backend_id": "editppt-image-cli", "handoff_rule": "…Codex OAuth first…"}
            run, page, source = make_run(root, legacy)
            self.source = source
            proc = self.run_import(page, ["--prompt-file", "prompts/base.md"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            jobs = json.loads((page / "imagegen-jobs.json").read_text(encoding="utf-8"))
            job = jobs["jobs"][0]
            self.assertEqual(job["status"], "recorded")
            self.assertNotIn("metadata_file", job)
            self.assertEqual(job["prompt_file"], "prompts/base.md")

    def test_path_traversal_dest_still_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, page, source = make_run(root, {"backend_id": "editppt-image-cli"})
            self.source = source
            proc = subprocess.run(
                [sys.executable, str(RECORD), str(page), "--job-id", "job-x",
                 "--source-image", str(source), "--dest", "../escape.png"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
