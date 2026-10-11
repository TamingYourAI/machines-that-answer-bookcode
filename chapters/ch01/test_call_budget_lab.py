"""Tests for the Chapter 1 lab. Run: python3 -m unittest test_call_budget_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import call_budget_lab as lab


class Budget(unittest.TestCase):
    def setUp(self):
        self.res = lab.experiment_budget(lab.load_turns("fixture"))

    def test_boundaries_nest_on_every_turn(self):
        for turns in lab.load_turns("fixture").values():
            for t in turns:
                d, s, c = lab.boundaries(t)
                self.assertLessEqual(d, s)
                self.assertLessEqual(s, c)

    def test_the_dashboard_hides_most_of_the_wait(self):
        call = self.res["call-shaped loop"]
        self.assertLess(call["the dashboard"]["p50"], lab.TARGET_MS)
        self.assertGreater(call["the caller"]["p50"], lab.TROUBLE_MS)

    def test_the_mean_hides_the_tail(self):
        for by in self.res.values():
            self.assertGreater(by["the caller"]["p95"], by["the caller"]["mean"])

    def test_demo_passes_and_call_fails_the_wall(self):
        self.assertLess(self.res["demo loop"]["the caller"]["p95"], lab.WALL_MS)
        self.assertGreater(self.res["call-shaped loop"]["the caller"]["p95"], lab.WALL_MS)

    def test_the_tuned_loop_meets_the_wall_at_p95(self):
        self.assertLess(self.res["tuned call loop"]["the caller"]["p95"], lab.WALL_MS)

    def test_a_filler_takes_the_tool_off_the_path(self):
        with_filler = lab.Turn(0, 0, 0, 100, 700, 50, 0, tool_hit=True, filler=True)
        without = lab.Turn(0, 0, 0, 100, 700, 50, 0, tool_hit=True, filler=False)
        self.assertEqual(lab.boundaries(with_filler)[0], 150)
        self.assertEqual(lab.boundaries(without)[0], 850)


class Ruler(unittest.TestCase):
    def setUp(self):
        self.b = lab.business_family(lab.load_calls("fixture"))

    def test_containment_is_not_task_completion(self):
        self.assertEqual(self.b["containment"], 70.0)
        self.assertEqual(self.b["task completion by the agent"], 50.0)
        self.assertEqual(self.b["contained, task not done"], 20.0)

    def test_surveys_miss_the_unresolved(self):
        self.assertEqual(self.b["surveys from unresolved calls"], 0)

    def test_one_false_commitment(self):
        self.assertEqual(self.b["said done, not done"], 1)


class Modes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").splitlines()[1:], lab.report("fixture").splitlines()[1:])

    def test_frozen_output(self):
        for mode in ("mock", "fixture"):
            frozen = (lab.OUTPUTS / f"call_budget_lab.{mode}.out.txt").read_text()
            self.assertEqual(lab.report(mode), frozen)


if __name__ == "__main__":
    unittest.main()
