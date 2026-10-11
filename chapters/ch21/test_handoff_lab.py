"""Tests for the Chapter 21 lab. Run: python3 -m unittest test_handoff_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import handoff_lab as lab

DATA = lab.inputs("fixture")


class Record(unittest.TestCase):
    def test_the_service_lines_record_carries_everything(self):
        self.assertEqual(lab.problems(DATA["records"]["the Service Line's transfer"]), [])

    def test_the_prototypes_record_fails_four_ways(self):
        self.assertEqual(len(lab.problems(DATA["records"]["the prototype's transfer"])), 4)

    def test_a_long_whisper_is_flagged(self):
        record = dict(DATA["records"]["the Service Line's transfer"],
                      whisper=" ".join(["word"] * 16))
        self.assertIn("whisper of 16 words (at most 15)", lab.problems(record))


class Loops(unittest.TestCase):
    def test_the_overflow_rule_sends_callers_back_to_the_agent(self):
        found = lab.loops(DATA["routes"], "agent")
        self.assertEqual(found, [["agent", "billing queue", "service number", "agent"]])

    def test_the_fixed_rules_have_no_way_back(self):
        self.assertEqual(lab.loops(DATA["routes_fixed"], "agent"), [])


class Queue(unittest.TestCase):
    def setUp(self):
        self.old = lab.evening("old overflow", DATA["evening"])
        self.new = lab.evening("truthful queue", DATA["evening"])

    def test_the_old_rule_loops_callers_and_the_truthful_queue_none(self):
        self.assertGreater(self.old["looped"], 0)
        self.assertEqual(self.new["looped"], 0)

    def test_every_callback_is_kept(self):
        self.assertGreater(self.new["callbacks"], 0)
        self.assertEqual(self.new["kept"], self.new["callbacks"])

    def test_fewer_callers_give_up(self):
        self.assertLess(self.new["gave_up"], self.old["gave_up"])

    def test_the_stated_wait_is_right(self):
        ok, n = self.new["stated"]
        self.assertEqual(ok, n)


class Carried(unittest.TestCase):
    def test_a_fresh_pin_is_carried(self):
        self.assertTrue(lab.desk_accepts("pin", 3, "explain_bill", 10).startswith("carried"))

    def test_a_stale_verification_is_not(self):
        self.assertIn("again", lab.desk_accepts("pin", 14, "explain_bill", 10))

    def test_the_next_action_can_need_a_step_up(self):
        self.assertIn("step-up", lab.desk_accepts("pin", 2, "change_address", 10))


class Modes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        strip = lambda t: t.split("\n", 1)[1]
        self.assertEqual(strip(lab.report("mock")), strip(lab.report("fixture")))

    def test_output_fits_78_columns(self):
        for line in lab.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)

    def test_frozen_output(self):
        for mode in ("mock", "fixture"):
            frozen = (lab.OUTPUTS / f"handoff_lab.{mode}.out.txt").read_text()
            self.assertEqual(lab.report(mode), frozen)


if __name__ == "__main__":
    unittest.main()
