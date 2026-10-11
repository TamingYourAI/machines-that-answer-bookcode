"""Tests for the Chapter 5 SOP lab. Run: python3 -m unittest test_sop_lab.py"""
from __future__ import annotations

import unittest

import sop_lab as s


class TestRanking(unittest.TestCase):
    def setUp(self):
        self.ranked = {r["reason"]: d for r, _, d in s.rank(s.drivers())}

    def test_first_two_are_billing_and_visits(self):
        firsts = sorted(k for k, d in self.ranked.items() if d == "first")
        self.assertEqual(firsts, ["billing question", "technician visit"])

    def test_risk_gates_the_highest_score(self):
        self.assertEqual(self.ranked["payment"], "later: after its controls")

    def test_the_counter_atlas_is_never_ranked_in(self):
        for reason in ("complaint", "bill dispute", "bereavement"):
            self.assertTrue(self.ranked[reason].startswith("never"))


class TestCompiler(unittest.TestCase):
    def setUp(self):
        self.compiled = s.compile_sop(s.sop_document(), s.sop_practice())

    def test_practice_is_inserted_where_the_desk_does_it(self):
        steps = [c["step"] for c in self.compiled]
        self.assertEqual(steps.index("2a"), steps.index("2") + 1)
        self.assertEqual(steps.index("5a"), steps.index("5") + 1)

    def test_drift_is_flagged(self):
        drift = [c["step"] for c in self.compiled if c["source"] == "practice"]
        self.assertEqual(drift, ["2a", "5a"])

    def test_every_write_is_marked(self):
        writes = [c["touch"] for c in self.compiled if c["touch"].startswith("write")]
        self.assertEqual(len(writes), 4)

    def test_the_safety_step_escalates_to_a_person(self):
        gas = next(c for c in self.compiled if c["safety"])
        self.assertEqual((gas["block"], gas["touch"]), ("escalate", "human"))


class TestOutboundGate(unittest.TestCase):
    def test_gate_decisions(self):
        decisions = [s.may_call(c) for c in s.reminder_list()]
        self.assertEqual(decisions.count("call now"), 2)
        self.assertIn("skip: no consent on record", decisions)
        self.assertIn("skip: opted out", decisions)
        self.assertEqual(sum(d.startswith("defer") for d in decisions), 2)

    def test_nine_pm_is_outside_the_window(self):
        c = {"to": "x", "consent": "y", "opted_out": False, "local": "21:00"}
        self.assertTrue(s.may_call(c).startswith("defer"))


class TestOneCall(unittest.TestCase):
    def setUp(self):
        self.compiled = s.compile_sop(s.sop_document(), s.sop_practice())
        self.call = s.the_call()

    def test_the_call_follows_the_compiled_order(self):
        self.assertTrue(s.in_order(self.call["steps"], self.compiled))

    def test_a_call_that_books_before_it_checks_the_outage_map_is_out_of_order(self):
        steps = [x for x in self.call["steps"] if x[1] != "verify"]
        steps.insert(8, ["20:14:39", "verify", "the outage map, too late", True])
        self.assertFalse(s.in_order(steps, self.compiled))


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        strip = lambda t: t.split("\n", 1)[1]
        self.assertEqual(strip(s.report("mock")), strip(s.report("fixture")))

    def test_output_fits_78_columns(self):
        for line in s.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
