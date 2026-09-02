"""editppt dsh-current 后端契约测试（标准库 unittest，无网络、无付费调用）。"""

import json
import base64
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CLI_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = CLI_DIR / "editppt" / "runtime"
sys.path.insert(0, str(RUNTIME_DIR))

import configure_image_backend  # noqa: E402
import main as cli_main  # noqa: E402
import _input_normalization  # noqa: E402

DSH_ARGS = [
    "--backend-id", "dsh-current",
    "--connection-id", "img_mti303k7_e0224219",
    "--connection-name", "tokenbom-image2",
    "--model", "gpt-image-2",
    "--image-protocol", "openai-images",
]
TINY_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def fake_run(root: Path, pages: int = 2) -> Path:
    deck = {
        "schema_version": 1,
        "run_id": "run-test",
        "pages": [],
        "max_concurrent_pages": 6,
    }
    jobs = {"schema_version": 1, "pages": []}
    for index in range(1, pages + 1):
        page_id = f"page_{index:03d}"
        page_dir = root / "pages" / page_id
        page_dir.mkdir(parents=True)
        (page_dir / "imagegen-jobs.json").write_text(
            json.dumps({"schema_version": 1, "jobs": []}), encoding="utf-8"
        )
        request_path = page_dir / "page_request.json"
        request_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
        deck["pages"].append({"page_id": page_id, "page_dir": f"pages/{page_id}", "page_request": f"pages/{page_id}/page_request.json"})
        jobs["pages"].append({"page_id": page_id, "page_dir": f"pages/{page_id}", "page_request": f"pages/{page_id}/page_request.json", "status": "pending"})
    (root / "deck_manifest.json").write_text(json.dumps(deck), encoding="utf-8")
    (root / "page_jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
    return root


class BackendContractTests(unittest.TestCase):
    def run_configure(self, run_dir: Path, extra):
        return subprocess.run(
            [sys.executable, str(RUNTIME_DIR / "configure_image_backend.py"), str(run_dir), *extra],
            capture_output=True, text=True,
        )

    def test_dsh_current_writes_deck_and_all_page_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = fake_run(Path(tmp))
            proc = self.run_configure(run_dir, DSH_ARGS)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            deck = json.loads((run_dir / "deck_manifest.json").read_text(encoding="utf-8"))
            contract = deck["image_backend"]
            self.assertEqual(contract, {
                "backend_id": "dsh-current",
                "tool_name": "editable_ppt_image",
                "connection_binding": "run-start-pinned",
                "connection_id": "img_mti303k7_e0224219",
                "connection_name": "tokenbom-image2",
                "model": "gpt-image-2",
                "protocol": "openai-images",
                "requires_openai_api_key": False,
                "allow_codex": False,
                "fallback_policy": "none",
                "mode_policy": "generate-or-edit-per-asset",
                "save_path_policy": "write one output directly inside the owning page directory",
                "handoff_rule": "call editable_ppt_image serially with the pinned connectionId; never call editppt image generate/edit",
            })
            for page in json.loads((run_dir / "page_jobs.json").read_text(encoding="utf-8"))["pages"]:
                request = json.loads((run_dir / page["page_request"]).read_text(encoding="utf-8"))
                self.assertEqual(request["image_backend"], contract)
            # 契约绝不携带 Base URL/凭据类字段（按精确键名与值形态检查；requires_openai_api_key 是契约规定的布尔字段）
            serialized = json.dumps(contract)
            sensitive_keys = {"baseUrl", "base_url", "apiKey", "api_key", "key", "token", "credentialRef", "credential", "authorization"}
            self.assertEqual(set(contract.keys()) & sensitive_keys, set())
            self.assertNotIn("://", serialized)
            self.assertNotIn("sk-", serialized)

    def test_dsh_current_missing_fields_fail(self):
        cases = [
            [a for a in DSH_ARGS if a != "img_mti303k7_e0224219" and a != "--connection-id"],
            [a for a in DSH_ARGS if a != "gpt-image-2" and a != "--model"],
            [a for a in DSH_ARGS if a != "openai-images" and a != "--image-protocol"],
            [a for a in DSH_ARGS if a != "tokenbom-image2" and a != "--connection-name"],
        ]
        for extra in cases:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = fake_run(Path(tmp))
                proc = self.run_configure(run_dir, extra)
                self.assertNotEqual(proc.returncode, 0, f"应缺少必填字段仍失败：{extra}")

    def test_dsh_current_rejects_secret_like_and_control_chars(self):
        for bad_name in ("token sk-abcdef0123456789", "https://api.example/v1", "line\nbreak"):
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = fake_run(Path(tmp))
                proc = self.run_configure(run_dir, [
                    "--backend-id", "dsh-current",
                    "--connection-id", "img_mti303k7_e0224219",
                    "--connection-name", bad_name,
                    "--model", "gpt-image-2",
                    "--image-protocol", "openai-images",
                ])
                self.assertNotEqual(proc.returncode, 0, f"疑似秘密/控制字符必须被拒绝：{bad_name!r}")

    def test_legacy_backends_keep_old_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = fake_run(Path(tmp), pages=1)
            proc = self.run_configure(run_dir, [])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            contract = json.loads((run_dir / "deck_manifest.json").read_text(encoding="utf-8"))["image_backend"]
            self.assertEqual(contract["backend_id"], "editppt-image-cli")
            self.assertEqual(contract["tool_call"], "editppt image generate/edit")
            self.assertIn("Codex OAuth first", contract["handoff_rule"])
            self.assertFalse(contract["requires_openai_api_key"])
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = fake_run(Path(tmp), pages=1)
            proc = self.run_configure(run_dir, ["--backend-id", "openai-compatible-api"])
            contract = json.loads((run_dir / "deck_manifest.json").read_text(encoding="utf-8"))["image_backend"]
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(contract["requires_openai_api_key"])

    def test_prepare_parser_maps_dsh_args(self):
        parser = cli_main.build_parser()
        args = parser.parse_args([
            "prepare", "slide.png", "--image-backend", "dsh-current",
            "--connection-id", "img_mti303k7_e0224219", "--connection-name", "tokenbom-image2",
            "--image-model", "gpt-image-2", "--image-protocol", "openai-images",
        ])
        self.assertEqual(args.image_backend, "dsh-current")
        self.assertEqual(args.connection_id, "img_mti303k7_e0224219")
        self.assertEqual(args.image_model, "gpt-image-2")
        self.assertEqual(args.image_protocol, "openai-images")

    def test_prepare_writes_dsh_contract_before_returning_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "slide.png"
            source.write_bytes(TINY_PNG)
            run_dir = root / "run"
            proc = subprocess.run([
                sys.executable, str(RUNTIME_DIR / "main.py"), "prepare", str(source),
                "--job-dir", str(run_dir), "--no-text-hints",
                "--image-backend", "dsh-current",
                "--connection-id", "img_mti303k7_e0224219",
                "--connection-name", "tokenbom-image2",
                "--image-model", "gpt-image-2",
                "--image-protocol", "openai-images",
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            deck = json.loads((run_dir / "deck_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(deck["image_backend"]["backend_id"], "dsh-current")
            request = json.loads((run_dir / "pages" / "page_001" / "page_request.json").read_text(encoding="utf-8"))
            self.assertEqual(request["image_backend"], deck["image_backend"])

    def test_prepare_rejects_incomplete_dsh_contract_without_creating_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "slide.png"
            source.write_bytes(TINY_PNG)
            run_dir = root / "run"
            proc = subprocess.run([
                sys.executable, str(RUNTIME_DIR / "main.py"), "prepare", str(source),
                "--job-dir", str(run_dir), "--no-text-hints",
                "--image-backend", "dsh-current",
                "--connection-id", "img_mti303k7_e0224219",
                "--connection-name", "tokenbom-image2",
                "--image-protocol", "openai-images",
            ], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(run_dir.exists())

    def test_prepare_interruption_keeps_fail_closed_dsh_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "slide.png"
            source.write_bytes(TINY_PNG)
            run_dir = root / "run"
            contract = configure_image_backend.dsh_backend_contract(type("A", (), {
                "connection_id": "img_mti303k7_e0224219",
                "connection_name": "tokenbom-image2",
                "model": "gpt-image-2",
                "image_protocol": "openai-images",
            })())
            with patch.object(_input_normalization, "copy_input", side_effect=RuntimeError("simulated interruption")):
                with self.assertRaises(RuntimeError):
                    _input_normalization.normalize_inputs(
                        [source], job_dir=run_dir, initial_deck_fields={"image_backend": contract}
                    )
            deck = json.loads((run_dir / "deck_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(deck["run_status"], "preparing")
            self.assertEqual(deck["image_backend"]["backend_id"], "dsh-current")

    def test_run_backend_parser_accepts_dsh_current(self):
        parser = cli_main.build_parser()
        args = parser.parse_args(["run", "backend", "x", "--mode", "dsh-current", "--connection-id", "img_test_00000000"])
        self.assertEqual(args.mode, "dsh-current")

    def test_run_next_treats_dsh_current_as_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = fake_run(Path(tmp), pages=1)
            self.assertEqual(self.run_configure(run_dir, DSH_ARGS).returncode, 0)
            payload = cli_main.cmd_next(type("A", (), {"run": str(run_dir), "json": True})())
            self.assertEqual(payload, 0)

    def test_contract_builder_rejects_bad_connection_id_shape(self):
        args = type("A", (), {
            "connection_id": "not an id!!", "connection_name": "n", "model": "m", "image_protocol": "openai-images",
        })()
        with self.assertRaises(SystemExit):
            configure_image_backend.dsh_backend_contract(args)


if __name__ == "__main__":
    unittest.main()
