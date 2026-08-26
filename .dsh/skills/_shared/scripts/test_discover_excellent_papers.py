from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("discover_excellent_papers.py")
SPEC = importlib.util.spec_from_file_location("discover_excellent_papers", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="优秀论文 空格 ")
        self.home = Path(self.temp.name) / "另一个盘符模拟" / ".dsh"
        self.library = self.home / "往年优秀论文"
        self.library.mkdir(parents=True)
        self.entries: list[dict[str, object]] = []
        self.add("国赛/2023/A题/a-low.pdf", b"%PDF-low", "国赛", 2023, "A", 10)
        self.add("国赛/2023/A题/a-high.pdf", b"%PDF-high", "国赛", 2023, "A", 100)
        self.add("国赛/2024/A题/a-new.pdf", b"%PDF-new", "国赛", 2024, "A", 50)
        self.add("国赛/2023/B题/b.pdf", b"%PDF-b", "国赛", 2023, "B", 100)
        self.write_catalog()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def add(self, relative: str, data: bytes, competition: str, year: int | None, problem: str | None, priority: int) -> None:
        path = self.library / Path(*Path(relative).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.entries.append({"path": relative, "competition": competition, "year": year, "problem": problem, "priority": priority, "sha256": digest(data)})

    def write_catalog(self, *, papers: list[dict[str, object]] | None = None, schema: str = module.CATALOG_SCHEMA) -> None:
        payload = {
            "schema": schema,
            "competitions": {"国赛": ["全国大学生数学建模竞赛", "CUMCM"]},
            "papers": self.entries if papers is None else papers,
        }
        (self.library / "catalog.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_explicit_home_alias_problem_year_and_priority(self) -> None:
        result = module.discover(dsh_home=self.home, competition="CUMCM", problem="a题", year=2023)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["competition"], "国赛")
        self.assertTrue(result["problem_match"])
        self.assertEqual([Path(item["path"]).name for item in result["files"]], ["a-high.pdf", "a-low.pdf"])

    def test_environment_home(self) -> None:
        with patch.dict(os.environ, {"DSH_HOME": str(self.home)}):
            self.assertEqual(module.resolve_dsh_home(), self.home.resolve())

    def test_script_location_fallback(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(module.resolve_dsh_home(), SCRIPT.resolve().parents[3])

    def test_default_limit_and_cross_year_same_problem(self) -> None:
        result = module.discover(dsh_home=self.home, competition="国赛", problem="A")
        self.assertEqual(result["count"], 2)
        self.assertEqual([Path(item["path"]).name for item in result["files"]], ["a-high.pdf", "a-new.pdf"])

    def test_unknown_problem_does_not_cross_match(self) -> None:
        result = module.discover(dsh_home=self.home, competition="国赛", problem="C")
        self.assertEqual(result["status"], "no_matching_sample")
        self.assertEqual(result["count"], 0)

    def test_unknown_problem_allows_competition_samples(self) -> None:
        result = module.discover(dsh_home=self.home, competition="国赛")
        self.assertEqual(result["status"], "matched")
        self.assertFalse(result["problem_match"])

    def test_disabled_does_not_need_catalog(self) -> None:
        (self.library / "catalog.json").unlink()
        result = module.discover(dsh_home=self.home, competition="国赛", disabled=True)
        self.assertEqual(result["status"], "disabled")

    def test_catalog_missing_and_invalid_json(self) -> None:
        catalog = self.library / "catalog.json"
        catalog.unlink()
        self.assertEqual(module.discover(dsh_home=self.home, competition="国赛")["status"], "catalog_missing")
        catalog.write_text("{", encoding="utf-8")
        self.assertEqual(module.discover(dsh_home=self.home, competition="国赛")["status"], "catalog_invalid")

    def test_catalog_rejects_bad_paths_duplicates_and_non_pdf(self) -> None:
        base = dict(self.entries[0])
        cases = [
            [{**base, "path": "../escape.pdf"}],
            [base, dict(base)],
            [{**base, "path": "国赛/a.txt"}],
            [{**base, "path": str((self.library / "absolute.pdf").resolve()).replace("\\", "/")}],
        ]
        for papers in cases:
            with self.subTest(papers=papers):
                self.write_catalog(papers=papers)
                self.assertEqual(module.discover(dsh_home=self.home, competition="国赛")["status"], "catalog_invalid")

    def test_file_missing_and_hash_mismatch(self) -> None:
        target = self.library / "国赛/2023/A题/a-high.pdf"
        target.unlink()
        self.assertEqual(module.discover(dsh_home=self.home, competition="国赛", problem="A")["status"], "file_missing")
        target.write_bytes(b"changed")
        self.assertEqual(module.discover(dsh_home=self.home, competition="国赛", problem="A")["status"], "hash_mismatch")

    def test_verify_all_and_cli_utf8(self) -> None:
        result = module.discover(dsh_home=self.home, verify_all=True)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["count"], 4)
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--dsh-home", str(self.home), "--competition", "全国大学生数学建模竞赛", "--problem", "A"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["competition"], "国赛")
        self.assertEqual(payload["count"], 2)


if __name__ == "__main__":
    unittest.main()
