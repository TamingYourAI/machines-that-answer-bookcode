"""Tests for the Chapter 29 lab. Run: python3 -m unittest test_care_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import care_lab as lab

DATA = lab.inputs("fixture")
DRIFT = {m: (first, why) for m, first, why in lab.drift(DATA["month"],
                                                        DATA["known"])}


class TheCalendar(unittest.TestCase):
    def test_five_tasks_are_overdue(self):
        self.assertEqual(len(lab.due(DATA["calendar"])["overdue"]), 5)

    def test_the_failover_drill_is_the_most_overdue(self):
        self.assertEqual(lab.due(DATA["calendar"])["overdue"][0][0],
                         "failover drill")


class Drift(unittest.TestCase):
    def test_the_carrier_change_alerts_on_the_second_day(self):
        self.assertEqual(DRIFT["entity errors, account numbers (%)"][0][0], 19)

    def test_resolution_that_lasts_moves_a_week_later(self):
        self.assertEqual(DRIFT["resolution that lasts (%)"][0][0], 26)

    def test_the_bill_run_is_explained_not_alerted(self):
        self.assertIn("bill run", DRIFT["billing share of calls (%)"][1])

    def test_a_slow_creep_never_alerts_against_its_median(self):
        self.assertIsNone(DRIFT["voice to voice p95 (ms)"][0])


class FixedLimits(unittest.TestCase):
    LIMITS = {m: first for m, _, _, first in lab.limits(DATA["month"],
                                                         DATA["fixed"])}

    def test_the_fixed_limit_catches_the_creep(self):
        self.assertEqual(self.LIMITS["voice to voice p95 (ms)"], 22)

    def test_resolution_stays_above_its_line(self):
        self.assertIsNone(self.LIMITS["resolution that lasts (%)"])


class WhatExpires(unittest.TestCase):
    def test_loud_expiry_pulls_the_ended_waiver(self):
        ended = [r for r in lab.expire(DATA["expiring"], loud=True) if r[2] < 0]
        self.assertEqual(ended[0][3], "pulled from the index; owner paged")

    def test_silent_expiry_leaves_it_live(self):
        ended = [r for r in lab.expire(DATA["expiring"], loud=False) if r[2] < 0]
        self.assertEqual(ended[0][3], "still live, nobody told")


class ReleaseDiff(unittest.TestCase):
    def test_two_parts_changed(self):
        self.assertEqual([c[0] for c in lab.diff(DATA["old"], DATA["new"])],
                         ["knowledge", "recognizer"])

    def test_a_recognizer_change_triggers_the_entity_scenarios(self):
        runs = lab.runs_for(lab.diff(DATA["old"], DATA["new"]))
        self.assertIn("entity scenarios", runs)

    def test_three_runs_got_worse(self):
        worse = [r for r in lab.runs_for(lab.diff(DATA["old"], DATA["new"]))
                 if DATA["results"][r][1] < DATA["results"][r][0]]
        self.assertEqual(len(worse), 3)


class CostDrift(unittest.TestCase):
    def test_two_parts_rose_more_than_a_tenth(self):
        parts = [r[0] for r in lab.cost_alarms(DATA["cost"]) if r[5]]
        self.assertEqual(parts, ["platform minutes", "model"])

    def test_the_total_rose_about_an_eighth(self):
        rows = lab.cost_alarms(DATA["cost"])
        t1, t3 = sum(r[1] for r in rows), sum(r[3] for r in rows)
        self.assertAlmostEqual((t3 - t1) / t1, 0.125, places=3)


class TheReport(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").split("\n", 1)[1],
                         lab.report("fixture").split("\n", 1)[1])

    def test_every_line_fits_the_page(self):
        for line in lab.report("fixture").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
