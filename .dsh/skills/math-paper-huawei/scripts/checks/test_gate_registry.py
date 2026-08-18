#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from gate_registry import GATES, STAGES, gates_for, validate_registry


class GateRegistryTests(unittest.TestCase):
    def test_every_check_is_registered_once(self) -> None:
        self.assertEqual(validate_registry(), [])

    def test_repeating_gate_sets_are_cumulative(self) -> None:
        previous: set[str] = set()
        for stage in STAGES:
            current = {gate.script for gate in gates_for(stage) if gate.repeat}
            self.assertTrue(previous <= current)
            previous = current

    def test_final_stage_contains_all_gates(self) -> None:
        self.assertEqual(len(gates_for("step5")), len(GATES))


if __name__ == "__main__":
    unittest.main()
