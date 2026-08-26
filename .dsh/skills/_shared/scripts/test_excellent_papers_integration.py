from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("discover_excellent_papers.py")
SPEC = importlib.util.spec_from_file_location("discover_excellent_papers_integration", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
DSH_HOME = SCRIPT.resolve().parents[3]
PROJECT = DSH_HOME.parent
STAGE_SCRIPT = PROJECT / ".release-staging/metamath-harness/.dsh/skills/_shared/scripts/discover_excellent_papers.py"


class RealLibraryIntegrationTests(unittest.TestCase):
    def test_cumcm_a_matches_only_a(self) -> None:
        result = module.discover(dsh_home=DSH_HOME, competition="国赛", problem="A")
        self.assertEqual((result["status"], result["count"], result["problem_match"]), ("matched", 2, True))
        self.assertTrue(all(item["competition"] == "国赛" and item["problem"] == "A" for item in result["files"]))

    def test_huawei_b_matches_only_b(self) -> None:
        result = module.discover(dsh_home=DSH_HOME, competition="中国研究生数学建模竞赛", problem="B")
        self.assertEqual((result["status"], result["count"]), ("matched", 2))
        self.assertTrue(all(item["competition"] == "华为杯" and item["problem"] == "B" for item in result["files"]))

    def test_huashu_empty_falls_back(self) -> None:
        result = module.discover(dsh_home=DSH_HOME, competition="华数杯", problem="A")
        self.assertEqual((result["status"], result["count"]), ("no_matching_sample", 0))
        self.assertEqual(result["fallback_reason"], "暂无匹配样本")

    def test_mcm_review_matches_and_rules_remain_external(self) -> None:
        result = module.discover(dsh_home=DSH_HOME, competition="MCM/ICM", problem="A")
        self.assertEqual((result["status"], result["count"], result["problem_match"]), ("matched", 2, True))
        self.assertTrue(all(item["competition"] == "美赛" for item in result["files"]))

    def test_disabled_does_not_scan(self) -> None:
        result = module.discover(dsh_home=PROJECT / "不存在的 DSH Home", competition="国赛", disabled=True)
        self.assertEqual((result["status"], result["count"]), ("disabled", 0))

    def test_staging_script_infers_its_own_dsh_home(self) -> None:
        environment = dict(os.environ)
        environment.pop("DSH_HOME", None)
        completed = subprocess.run(
            [sys.executable, str(STAGE_SCRIPT), "--competition", "CUMCM", "--problem", "A"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        result = json.loads(completed.stdout)
        self.assertEqual((result["status"], result["count"]), ("matched", 2))
        self.assertIn(".release-staging", result["root"])


if __name__ == "__main__":
    unittest.main()
