"""Tests for the Chapter 24 lab. Run: python3 -m unittest test_metrics_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import metrics_lab as lab

DATA = lab.inputs("fixture")
CALLS = {c["id"]: c for c in DATA["calls"]}
WEEK = lab.records(DATA["week_4"])


class ThreeRecordedCalls(unittest.TestCase):
    def test_a_low_word_error_rate_hides_the_entity_that_mattered(self):
        v = lab.voice_family(CALLS["r2"])
        self.assertLess(v["wer"], 5)
        self.assertEqual(v["entities wrong"], 1)

    def test_the_server_meets_the_wall_while_the_caller_does_not(self):
        turns = [t for c in DATA["calls"] for t in c["turns"]]
        self.assertLessEqual(lab.percentile([t["server"] for t in turns], 95),
                             800)
        self.assertGreater(lab.percentile([t["caller"] for t in turns], 95),
                           800)

    def test_the_mean_sits_under_the_wall_that_the_p95_crosses(self):
        xs = [t["caller"] for c in DATA["calls"] for t in c["turns"]]
        self.assertLess(sum(xs) / len(xs), 800)
        self.assertGreater(lab.percentile(xs, 95), 800)

    def test_the_three_business_numbers_differ_on_three_calls(self):
        b = [lab.business_family(c) for c in DATA["calls"]]
        self.assertEqual(sum(x["contained"] for x in b), 2)
        self.assertEqual(sum(x["completed by the agent"] for x in b), 2)
        self.assertEqual(sum(x["lasted"] for x in b), 1)

    def test_a_person_finishing_a_task_is_never_the_agents_completion(self):
        b = lab.business_family(CALLS["r3"])
        self.assertFalse(b["completed by the agent"])

    def test_a_repeat_call_is_part_of_the_first_calls_cost(self):
        self.assertEqual(lab.business_family(CALLS["r2"])["cost"], 8.14)


class OneWeekThreeWays(unittest.TestCase):
    def test_the_dashboard_and_the_spreadsheet_disagree(self):
        self.assertAlmostEqual(lab.dashboard_containment(WEEK), 64.0, 1)
        self.assertAlmostEqual(lab.spreadsheet_resolved(WEEK), 31.0, 1)

    def test_the_metrics_record_gives_all_three_numbers_in_order(self):
        b = lab.business(WEEK)
        self.assertGreaterEqual(b["containment"], b["task completion"])
        self.assertGreaterEqual(b["task completion"],
                                b["resolution that lasts"])
        self.assertAlmostEqual(b["resolution that lasts"], 34.1, 1)

    def test_the_spreadsheets_gap_is_the_unrelated_later_calls(self):
        gap = (lab.business(WEEK)["resolution that lasts"]
               - lab.spreadsheet_resolved(WEEK)) * len(WEEK) / 100
        self.assertEqual(round(gap), sum(c[8] for c in DATA["week_4"]))

    def test_machine_callers_are_in_no_number(self):
        self.assertEqual(len(WEEK), sum(c[3] for c in DATA["week_4"]))


class EveryNumberSplit(unittest.TestCase):
    def test_the_second_language_sits_wholly_below_the_week(self):
        rows = {r[0]: r for r in lab.split(WEEK, "lang")}
        self.assertEqual(rows["second"][6], "own item")
        self.assertEqual(rows["first"][6], "")

    def test_a_group_near_the_line_is_not_flagged(self):
        rows = {r[0]: r for r in lab.split(WEEK, "seat")}
        self.assertEqual(rows["phone"][6], "")

    def test_a_small_group_with_a_low_number_is_a_question_not_a_pass(self):
        lo, hi = lab.wilson(8, 40)   # 20 percent of 40 calls
        self.assertGreater(hi, 34.1)
        self.assertEqual(lab.review(lo, hi, 34.1), "too few")

    def test_a_small_group_far_below_the_week_is_still_a_gap(self):
        lo, hi = lab.wilson(2, 40)
        self.assertEqual(lab.review(lo, hi, 34.1), "own item")


class SimpsonsParadox(unittest.TestCase):
    def test_the_week_rose_while_every_flow_fell(self):
        cf = lab.containment_by_flow(DATA["flows"])
        self.assertGreater(cf["week 6"]["all"], cf["week 5"]["all"])
        for f in ("billing", "visits"):
            self.assertLess(cf["week 6"][f], cf["week 5"][f])

    def test_at_a_fixed_mix_the_week_fell(self):
        cf = lab.containment_by_flow(DATA["flows"])
        rates = {f: cf["week 6"][f] for f in ("billing", "visits")}
        self.assertLess(lab.at_fixed_mix(rates, cf["week 5"]["mix"]),
                        cf["week 5"]["all"])


class TheCasesLines(unittest.TestCase):
    def test_week_8_holds_every_line(self):
        got = lab.case_lines(DATA["week_8"])
        for name in ("resolution that lasts", "what a repeat call costs",
                     "agent cost per call"):
            self.assertEqual(lab.holds(name, got[name]), "yes")

    def test_the_cost_per_resolved_case_is_above_the_plan(self):
        got = lab.case_lines(DATA["week_8"])
        self.assertAlmostEqual(got["cost per resolved case"], 5.36, 2)
        self.assertGreater(got["cost per resolved case"], 4.20)

    def test_the_lowest_group_still_sits_below_the_week_at_week_8(self):
        w = DATA["week_8"]
        n, k = w["groups"]["language: second"]
        self.assertLess(lab.wilson(k, n)[1],
                        lab.case_lines(w)["resolution that lasts"])

    def test_a_caller_who_gave_up_is_never_a_resolved_case(self):
        p = lab.case_lines(DATA["week_8"])["parts"]
        w = DATA["week_8"]
        self.assertEqual(p["resolved"] + p["unresolved"] + p["gave up"],
                         w["calls"])

    def test_an_unresolved_handover_adds_its_cost_and_nothing_to_the_count(
            self):
        w = dict(DATA["week_8"])
        before = lab.case_lines(w)
        w["handovers resolved"] -= 87   # one handover in ten unresolved
        after = lab.case_lines(w)
        self.assertEqual(after["parts"]["cost"], before["parts"]["cost"])
        self.assertEqual(after["parts"]["resolved"],
                         before["parts"]["resolved"] - 87)
        self.assertAlmostEqual(after["cost per resolved case"], 5.54, 2)

    def test_the_saving_rests_on_the_human_path(self):
        w = dict(DATA["week_8"])
        self.assertEqual(lab.break_even(w), 290)
        w["repeats resolved"] -= 290
        person = lab.PERSON_PER_MIN * w["minutes before the pilot"]
        self.assertGreater(lab.case_lines(w)["cost per resolved case"],
                           person)


class TheReport(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").split("\n", 1)[1],
                         lab.report("fixture").split("\n", 1)[1])

    def test_every_line_fits_the_page(self):
        for line in lab.report("fixture").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
