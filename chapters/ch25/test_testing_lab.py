"""Tests for the Chapter 25 lab. Run: python3 -m unittest test_testing_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import testing_lab as lab

DATA = lab.inputs("fixture")
POLITE = DATA["calls"]["polite"]
REALISTIC = DATA["calls"]["realistic"]


def passes(calls, version) -> int:
    return sum(lab.score(c, version).startswith("pass") for c in calls)


class UnitTestsOnTheGate(unittest.TestCase):
    def test_every_unit_case_gets_its_expected_answer(self):
        for name, call, expected in DATA["unit_cases"]:
            self.assertEqual(lab.gate(**call), expected, name)

    def test_a_yes_that_never_heard_the_fee_is_refused(self):
        self.assertEqual(lab.gate("book_visit", "visit", "pin",
                                  ["slot", "address"]),
                         "refused: fee not heard")


class OneBookingInText(unittest.TestCase):
    def test_a_wording_test_fails_a_correct_reworded_agent(self):
        self.assertEqual(lab.on_wording(lab.agent_booking("B2")), "fail")
        self.assertEqual(lab.on_state(lab.agent_booking("B2")), "pass")

    def test_a_wording_test_passes_an_agent_that_booked_nothing(self):
        run = lab.agent_booking("C")
        self.assertEqual(lab.on_wording(run), "pass")
        self.assertEqual(run["ops"], [])

    def test_the_state_test_catches_the_false_booked(self):
        self.assertTrue(lab.on_state(lab.agent_booking("C")).startswith(
            "fail: no booking"))


class SimulatedCallers(unittest.TestCase):
    def test_the_polite_caller_passes_the_version_that_breaks(self):
        self.assertEqual(passes(POLITE, lab.version_a), 20)

    def test_the_realistic_caller_exposes_it(self):
        self.assertLess(passes(REALISTIC, lab.version_a), 20)
        self.assertEqual(passes(REALISTIC, lab.version_b), 20)

    def test_every_failure_is_a_correction_or_a_restart(self):
        for c in REALISTIC:
            if lab.score(c, lab.version_a).startswith("fail"):
                self.assertIn(c["habit"], ("corrected", "restart"))

    def test_a_misheard_digit_is_repaired_not_failed(self):
        misheard = [c for c in REALISTIC
                    if lab.version_b(c["heard"]) != lab.ACCOUNT]
        self.assertTrue(misheard)
        for c in misheard:
            self.assertEqual(lab.score(c, lab.version_b),
                             "pass: misheard, one read-back repair")

    def test_both_versions_meet_the_same_calls(self):
        again = lab.calls_for(lab.PERSONAS["realistic"], 20, 2025)
        self.assertEqual(again, REALISTIC)


class WhatRunsCanProve(unittest.TestCase):
    def test_twenty_clean_runs_still_allow_about_fourteen_percent(self):
        self.assertAlmostEqual(lab.zero_failure_bound(20), 13.9, 1)

    def test_the_runs_a_claim_needs(self):
        self.assertEqual(lab.runs_needed(0.05), 59)
        self.assertEqual(lab.runs_needed(0.01), 299)

    def test_twenty_of_twenty_is_an_interval_not_a_certainty(self):
        lo, hi = lab.wilson(20, 20)
        self.assertAlmostEqual(lo, 83.9, 1)
        self.assertEqual(hi, 100.0)


class WhatRunsWhen(unittest.TestCase):
    def test_the_nightly_audio_suite_and_the_one_nobody_runs(self):
        name, tests, runs, minutes, rate, _ = DATA["layers"][2]
        self.assertEqual(lab.layer_cost(tests, runs, minutes, rate)[1], 180)
        self.assertEqual(lab.layer_cost(tests, 20, minutes, rate)[1], 720)


class TheReport(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").split("\n", 1)[1],
                         lab.report("fixture").split("\n", 1)[1])

    def test_every_line_fits_the_page(self):
        for line in lab.report("fixture").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
