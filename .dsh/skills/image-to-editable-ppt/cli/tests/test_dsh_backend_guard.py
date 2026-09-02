"""editppt image 在 dsh-current 运行内的硬防线测试（攻击测试：认证读取前必须失败）。"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parents[1]
RUNTIME_DIR = CLI_DIR / "editppt" / "runtime"
sys.path.insert(0, str(RUNTIME_DIR))

import image_gen  # noqa: E402


def make_page(root: Path, backend_id: str):
    run_dir = root / "run"
    page_dir = run_dir / "pages" / "page_001"
    page_dir.mkdir(parents=True)
    deck = {"image_backend": {"backend_id": backend_id, "connection_id": "img_mti303k7_e0224219"}}
    (run_dir / "deck_manifest.json").write_text(json.dumps(deck), encoding="utf-8")
    source = page_dir / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return run_dir, page_dir, source


class GuardTests(unittest.TestCase):
    def test_dsh_current_blocks_before_any_auth_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run, page, source = make_page(Path(tmp), "dsh-current")
            out = page / "assets" / "clean_base.png"
            calls = {"codex_auth": 0, "api_key": 0, "client": 0}

            def forbidden(name):
                def _raise(*_args, **_kwargs):
                    calls[name] += 1
                    raise AssertionError(f"{name} 被调用：防线必须早于认证/API 路径")
                return _raise

            original = (image_gen._load_codex_auth, image_gen._ensure_api_key, image_gen._create_client)
            image_gen._load_codex_auth = forbidden("codex_auth")
            image_gen._ensure_api_key = forbidden("api_key")
            image_gen._create_client = forbidden("client")
            argv = ["editppt image", "edit", "--image", str(source), "--out", str(out), "--prompt", "x"]
            old_argv = sys.argv
            sys.argv = argv
            err = io.StringIO()
            try:
                with self.assertRaises(SystemExit) as caught, redirect_stderr(err), redirect_stdout(io.StringIO()):
                    image_gen.main()
            finally:
                sys.argv = old_argv
                image_gen._load_codex_auth, image_gen._ensure_api_key, image_gen._create_client = original
            message = err.getvalue()
            self.assertIn(image_gen.DSH_CURRENT_CLI_FORBIDDEN, message)
            self.assertIn("editable_ppt_image", message)
            self.assertEqual(calls, {"codex_auth": 0, "api_key": 0, "client": 0})
            self.assertFalse(out.exists())

    def test_generate_also_blocked_in_dsh_current_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run, page, _source = make_page(Path(tmp), "dsh-current")
            out = page / "assets" / "new.png"
            with self.assertRaises(SystemExit):
                image_gen._guard_not_dsh_current_run(str(out))

    def test_legacy_and_standalone_usage_not_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, page, _source = make_page(root, "editppt-image-cli")
            image_gen._guard_not_dsh_current_run(str(page / "assets" / "x.png"))  # 不得抛出
            standalone_out = root / "elsewhere" / "out.png"
            image_gen._guard_not_dsh_current_run(str(standalone_out))  # 无 manifest：放行

    def test_broken_manifest_above_output_exits_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            page = run / "pages" / "page_001"
            page.mkdir(parents=True)
            (run / "deck_manifest.json").write_text("{ not json", encoding="utf-8")
            with self.assertRaises(SystemExit):
                image_gen._guard_not_dsh_current_run(str(page / "out.png"))

    def test_dry_run_skips_guard_function(self):
        # 防线的启用条件是“非 dry-run”；dry-run 不读认证也不发起请求。
        self.assertTrue(callable(image_gen._guard_not_dsh_current_run))
        src = Path(image_gen.__file__).read_text(encoding="utf-8")
        self.assertIn("if not args.dry_run:", src)


if __name__ == "__main__":
    unittest.main()
