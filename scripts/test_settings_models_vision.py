"""识图重放门禁的正式离线回归，不读取用户配置或凭据。"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("patch-settings-models-vision.py")
module_spec = importlib.util.spec_from_file_location("vision_patch", MODULE_PATH)
hotfix = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(hotfix)

# 最小官方语义结构，仅为脚本离线夹具。
BASE = ('editCapacity(index, "maxTokens", event.target.value);\n'
        '\t\t})]\n\t})]\n'
        'modelAdvanced: "容量",\n'
        'modelAdvanced: "Capacities",\n')


def patched_source():
    value = hotfix.patch_jsx(BASE)
    value = hotfix.patch_locale(value, hotfix.ANCHOR_ZH, hotfix.ZH_LOCALE_ADD, "zh")
    return hotfix.patch_locale(value, hotfix.ANCHOR_EN, hotfix.EN_LOCALE_ADD, "en")


class VisionPatchTests(unittest.TestCase):
    def invoke(self, target, check=False):
        args = [str(MODULE_PATH), *(["--check"] if check else []), str(target)]
        with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return hotfix.main()

    def test_complete_patch_and_idempotence(self):
        with tempfile.TemporaryDirectory(prefix="dsh-vision-gate-") as folder:
            target = Path(folder) / "client.js"
            target.write_text(BASE, encoding="utf-8")
            self.assertEqual(self.invoke(target), 0)
            saved = target.read_bytes()
            self.assertEqual(self.invoke(target, True), 0)
            self.assertEqual(self.invoke(target), 0)
            self.assertEqual(target.read_bytes(), saved)
            self.assertEqual(target.with_name(target.name + hotfix.BACKUP_SUFFIX).read_text(encoding="utf-8"), BASE)

    def test_marker_alone_rejected_without_write(self):
        with tempfile.TemporaryDirectory(prefix="dsh-vision-gate-") as folder:
            target = Path(folder) / "client.js"
            target.write_text(BASE + "// modelVision\n", encoding="utf-8")
            original = target.read_bytes()
            for check in (True, False):
                with self.assertRaises(SystemExit) as failure:
                    self.invoke(target, check)
                self.assertEqual(failure.exception.code, 1)
                self.assertEqual(target.read_bytes(), original)
            self.assertFalse(target.with_name(target.name + hotfix.BACKUP_SUFFIX).exists())

    def test_each_component_required(self):
        value = patched_source()
        for old, new in (
            ('modelVision: "识图（图片输入）"', 'modelVision: "坏"'),
            ('modelVisionHint: "When checked, this model accepts image input"', 'modelVisionHint: "bad"'),
            ('{ input: void 0 }', '{ input: ["text"] }'),
            ('type: "checkbox"', 'type: "text"'),
            ('model.input.includes("image")', 'false'),
        ):
            with self.subTest(component=old), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                hotfix.verify(value.replace(old, new))

    def test_anchor_failure_keeps_target_and_no_backup(self):
        with tempfile.TemporaryDirectory(prefix="dsh-vision-gate-") as folder:
            target = Path(folder) / "client.js"
            value = BASE.replace(hotfix.ANCHOR_EN, "changed")
            target.write_text(value, encoding="utf-8")
            with self.assertRaises(SystemExit):
                self.invoke(target)
            self.assertEqual(target.read_text(encoding="utf-8"), value)
            self.assertFalse(target.with_name(target.name + hotfix.BACKUP_SUFFIX).exists())

    def test_override_without_appdata(self):
        with patch.dict(os.environ, {"DSH_SETTINGS_MODELS_CLIENT": "fixture/client.js"}, clear=True):
            self.assertEqual(hotfix.default_client(), Path("fixture/client.js"))


if __name__ == "__main__":
    unittest.main()
