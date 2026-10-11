"""Tests for the Chapter 28 lab. Run: python3 -m unittest test_resilience_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import resilience_lab as lab

DATA = lab.inputs("fixture")


class OneCapacityModel(unittest.TestCase):
    def test_littles_law_gives_135_calls_in_progress(self):
        self.assertEqual(lab.loads(DATA["peak"])["platform"], 135)

    def test_the_desk_binds_at_the_storm_peak(self):
        over = [r[0] for r in lab.binding(DATA["peak"], DATA["limits"])
                if r[5] > 1]
        self.assertEqual(over, ["desk"])

    def test_every_machine_layer_has_headroom(self):
        for layer, *_, use in lab.binding(DATA["peak"], DATA["limits"]):
            if layer != "desk":
                self.assertLess(use, 0.6, layer)


class FailoverMidCall(unittest.TestCase):
    def test_recognizer_next_call_only_hands_the_caller_over(self):
        r = lab.recognizer_fails(DATA["call"], mid_call=False)
        self.assertEqual(r["repairs"], lab.COUNTER_ACTS_AT)
        self.assertIn("handed over", r["outcome"])

    def test_recognizer_mid_call_loses_no_words_within_the_buffer(self):
        r = lab.recognizer_fails(DATA["call"], mid_call=True)
        self.assertEqual(r["repairs"], 0)

    def test_a_turn_longer_than_the_buffer_needs_one_repeat(self):
        call = [list(t) for t in DATA["call"]]
        call[lab.FAIL_AT][1] = 4.5
        self.assertEqual(lab.recognizer_fails(call, mid_call=True)["repairs"], 1)

    def test_model_next_call_only_hands_over_at_2_s(self):
        r = lab.model_fails(DATA["call"], mid_call=False)
        self.assertEqual(r["extra_s"], lab.HANDOFF_MS / 1000)

    def test_model_mid_call_keeps_the_booking_with_the_agent(self):
        self.assertEqual(lab.model_fails(DATA["call"], mid_call=True)["outcome"],
                         "booked by the agent")


class FailureClasses(unittest.TestCase):
    def test_only_a_carrier_or_region_loss_drops_the_call(self):
        dropped = [c["name"] for c in DATA["classes"] if not c["survives"]]
        self.assertEqual(dropped, ["a carrier or a region lost"])


class NothingDoneTwice(unittest.TestCase):
    def run_design(self, journal_both, fence):
        return lab.takeover(DATA["takeover"], journal_both, fence)

    def test_copies_behind_know_nothing_and_book_every_one_twice(self):
        r = self.run_design(False, False)
        self.assertEqual((r["known"], r["twice"]), (0, 9))

    def test_the_journal_in_both_regions_knows_every_rebooking(self):
        self.assertEqual(self.run_design(True, False)["known"], 9)

    def test_without_a_fence_the_east_books_a_changed_flight_twice(self):
        self.assertEqual(self.run_design(True, False)["twice"], 1)

    def test_the_journal_and_the_fence_book_nothing_twice(self):
        self.assertEqual(self.run_design(True, True)["twice"], 0)


class TheDrill(unittest.TestCase):
    def test_the_error_alarm_never_fires(self):
        self.assertIsNone(lab.drill(DATA["drill"])["error_alarm_at"])

    def test_the_empty_transcript_alarm_fires_in_the_first_minute(self):
        self.assertEqual(lab.drill(DATA["drill"])["empty_alarm_at"], 1)

    def test_the_empty_alarm_spares_300_callers(self):
        r = lab.drill(DATA["drill"])
        self.assertEqual(r["deaf_without"] - r["deaf_with_alarm"], 300)


class TheLadder(unittest.TestCase):
    def test_the_evening_climbs_the_ladder_and_comes_back_down(self):
        rungs = [lab.rung(p, w, lim, e) for _, p, w, lim, e in DATA["evening"]]
        self.assertEqual(rungs, [0, 1, 2, 3, 2, 0])

    def test_empty_transcripts_go_straight_to_the_kill_switch(self):
        self.assertEqual(lab.rung(700, 2, False, 60), 4)


class TheReport(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").split("\n", 1)[1],
                         lab.report("fixture").split("\n", 1)[1])

    def test_every_line_fits_the_page(self):
        for line in lab.report("fixture").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
