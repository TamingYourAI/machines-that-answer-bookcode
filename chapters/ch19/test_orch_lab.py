"""Tests for the Chapter 19 orchestration lab. Run: python3 -m unittest test_orch_lab.py"""
from __future__ import annotations

import json
import unittest

import orch_lab as o

DATA = o.inputs("mock")
FEE = DATA["fee"]


class TestQueues(unittest.TestCase):
    def test_a_data_frame_waits_behind_the_queued_audio(self):
        self.assertEqual(o.interruption_delay(1_000, "data"), 1_000)

    def test_a_system_frame_waits_for_one_frame_at_most(self):
        self.assertEqual(o.interruption_delay(1_000, "system"), o.FRAME_MS)


class TestPlaybackTruth(unittest.TestCase):
    def test_marks_before_the_clear_agree_with_chapter_8(self):
        r = o.playback(FEE, 3_300, count_echoes=False)
        self.assertEqual((r["heard"], r["total"]), (45, 6_400))
        self.assertFalse(r["fee_heard"])

    def test_counting_every_echo_as_played_hears_the_fee(self):
        r = o.playback(FEE, 3_300, count_echoes=True)
        self.assertTrue(r["fee_heard"])
        self.assertEqual((r["sent"], r["played"], r["cleared"]), (21, 16, 5))

    def test_a_late_barge_in_hears_the_whole_line(self):
        r = o.playback(FEE, 6_400, count_echoes=False)
        self.assertEqual(r["heard"], len(FEE["line"]))


class TestRaceSuite(unittest.TestCase):
    def setUp(self):
        self.s = o.race_suite(FEE, DATA["runs"], seed=19)

    def test_the_correct_orchestrator_breaks_nothing(self):
        self.assertEqual(self.s["correct"], {"canceled": 0, "unheard": 0, "late": 0})

    def test_the_naive_one_breaks_every_invariant(self):
        self.assertTrue(all(n > 0 for n in self.s["naive"].values()))


class TestSpeculation(unittest.TestCase):
    def setUp(self):
        self.rows = {r["setting"]: r for r in o.speculation(DATA["spec"], seed=19)}

    def test_no_speculation_matches_chapter_6_at_the_median(self):
        self.assertAlmostEqual(self.rows["no speculation"]["p50"], 610, delta=15)

    def test_speculating_the_model_saves_time_and_never_talks_over(self):
        spec = self.rows["speculate the model"]
        self.assertLess(spec["p50"], self.rows["no speculation"]["p50"] - 100)
        self.assertEqual(spec["over"], 0)
        self.assertEqual(spec["discarded"], DATA["spec"]["goes_on"])

    def test_playing_before_the_turn_is_confirmed_talks_over_callers(self):
        self.assertEqual(self.rows["play before the turn is confirmed"]["over"],
                         DATA["spec"]["goes_on"])


class TestSpansPlaybookCall(unittest.TestCase):
    def test_the_hold_is_invisible_to_the_vendor_dashboard(self):
        before, after = o.spans(DATA["turn"], 0), o.spans(DATA["turn"], 200)
        self.assertEqual(sum(x[2] for x in before), 610)
        self.assertEqual(sum(x[2] for x in after), 810)
        shown = [sum(x[2] for x in v if x[3]) for v in (before, after)]
        self.assertEqual(shown[0], shown[1])

    def test_every_lever_saves_time(self):
        rows = o.playbook(DATA["playbook"])
        self.assertEqual((rows[0][1], rows[-1][1]), (1_215, 440))
        self.assertTrue(all(a[1] > b[1] for a, b in zip(rows, rows[1:])))

    def test_the_call_runs_in_time_order_through_the_part_iv_pieces(self):
        events = o.end_to_end(DATA["events"])
        self.assertEqual([e[0] for e in events], sorted(e[0] for e in events))
        text = " ".join(e[2] for e in events if e[3])
        for piece in ("policy layer", "state", "checked", "marks", "explanation"):
            self.assertIn(piece, text)


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(o.report("mock").splitlines()[1:],
                         o.report("fixture").splitlines()[1:])

    def test_fixture_matches_the_data(self):
        stored = json.loads((o.FIXTURES / "orch.json").read_text())
        self.assertEqual(stored, json.loads(json.dumps(o.inputs("mock"))))

    def test_output_fits_the_page(self):
        for line in o.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
