#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""“合格即冻结、硬缺陷驱动重画”口径的合成验证（Q01/Q02）。

夹具全部为合成数据，只用于测试，不进入实际论文。本测试不引入调度系统：
用生成计数器证明三轮自查只读复核不增加生成调用；用候选目录证明失败候选
不覆盖已合格的正式图。"""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path


MAX_CONSECUTIVE_FAILURES = 3


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


CONCRETE_DEFECT_TOKENS = (
    "数据错误", "数据来源", "标注错误", "标注遮挡", "遮挡", "缺字", "裁切", "布局错误",
    "量纲", "坐标轴", "图例", "策略违反", "配色不可读", "导出不可读", "用户要求",
)


class FigureFreezePolicy:
    """合格即冻结的最小规则模型：重画必须对应具体缺陷，失败候选不覆盖合格图。"""

    def __init__(self) -> None:
        self.failure_streak = 0

    def regeneration_allowed(self, defect: str | None) -> bool:
        text = str(defect or "").strip()
        if not any(token in text for token in CONCRETE_DEFECT_TOKENS):
            return False  # “更高级一点”这类无具体缺陷的理由不构成重画依据
        return self.failure_streak < MAX_CONSECUTIVE_FAILURES

    def record_candidate_result(self, qa_passed: bool) -> None:
        self.failure_streak = 0 if qa_passed else self.failure_streak + 1


class StopRedrawFreezeTests(unittest.TestCase):
    def test_qualified_figure_not_regenerated_across_review_rounds(self):
        # Q01：合格图进入三轮自查，只读复核，生成调用计数不增长
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            counter = root / "gen_count.txt"
            qualified = root / "figures" / "fig1.png"
            qualified.parent.mkdir(parents=True)

            def generate(target: Path) -> None:
                count = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
                counter.write_text(str(count + 1), encoding="utf-8")
                target.write_bytes(f"figure-v{count + 1}".encode("utf-8"))

            generate(qualified)
            baseline = sha256_bytes(qualified.read_bytes())
            # 合成 QA：数据来源正确、无遮挡缺字、导出可读、策略满足 → 合格即冻结
            qa_passed = True
            self.assertTrue(qa_passed)
            for _ in range(3):
                # 三轮自查只读复核：读图、读 QA 记录，不调用 generate
                self.assertTrue(qualified.read_bytes().startswith(b"figure-v1"))
                self.assertEqual(
                    int(counter.read_text(encoding="utf-8")),
                    1,
                    "合格图自查不得增加生成调用",
                )
            self.assertEqual(sha256_bytes(qualified.read_bytes()), baseline, "合格图文件不得被改写")

    def test_failed_candidate_does_not_overwrite_qualified(self):
        # Q02：新候选 QA 未通过时，旧合格图保留原样，候选留在候选目录并记录缺陷
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            counter = root / "gen_count.txt"
            qualified = root / "figures" / "fig1.png"
            candidate_dir = root / "candidates"
            qualified.parent.mkdir(parents=True)
            candidate_dir.mkdir(parents=True)

            def generate(target: Path) -> None:
                count = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
                counter.write_text(str(count + 1), encoding="utf-8")
                target.write_bytes(f"figure-v{count + 1}".encode("utf-8"))

            generate(qualified)
            qualified_bytes = qualified.read_bytes()
            policy = FigureFreezePolicy()
            defect = "图例遮挡第二条曲线的峰值标注，需上移图例"
            self.assertTrue(policy.regeneration_allowed(defect))
            candidate = candidate_dir / "fig1_v2.png"
            generate(candidate)  # 候选写到候选目录，不直接写正式路径
            policy.record_candidate_result(qa_passed=False)  # 合成 QA：候选仍遮挡 → 失败
            self.assertEqual(qualified.read_bytes(), qualified_bytes, "失败候选不得覆盖合格图")
            self.assertTrue(candidate.exists(), "失败候选保留在候选目录")
            self.assertEqual(policy.failure_streak, 1)

    def test_vague_reason_and_strike_limit_block_regeneration(self):
        # “更高级”不构成重画理由；同一失败连续 3 次后必须换具体策略
        policy = FigureFreezePolicy()
        self.assertFalse(policy.regeneration_allowed("更高级一点"))
        self.assertFalse(policy.regeneration_allowed(None))
        concrete = "横轴量纲错误，应为小时"
        for _ in range(MAX_CONSECUTIVE_FAILURES):
            self.assertTrue(policy.regeneration_allowed(concrete))
            policy.record_candidate_result(False)
        self.assertFalse(policy.regeneration_allowed(concrete), "连续 3 次失败后须切换策略，不能循环清零")


if __name__ == "__main__":
    unittest.main()
