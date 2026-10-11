"""Tests for the Chapter 13 speech-to-speech lab. Run: python3 -m unittest test_s2s_lab.py"""
from __future__ import annotations

import random
import unittest

import s2s_lab as s

DATA = s.inputs("mock")


class TestExactWords(unittest.TestCase):
    def test_an_instruction_is_usually_followed(self):
        rng = random.Random(1)
        self.assertEqual(s.instructed(s.WAIVER, ["x"], 0.0, rng), s.WAIVER)

    def test_instructed_lines_drift_and_fixed_lines_do_not(self):
        said = s.exact_words(DATA)
        self.assertLess(sum(x == s.WAIVER for x in said["waiver"]), DATA["waiver_sessions"])
        self.assertTrue(s.terms_kept(s.WAIVER, "waiver"))
        self.assertTrue(s.terms_kept(s.DISCLOSURE, "disclosure"))

    def test_a_plural_promises_more_than_the_memo(self):
        self.assertFalse(s.terms_kept("We can waive your late fees.", "waiver"))


class TestGate(unittest.TestCase):
    def call(self, **state):
        return dict(DATA["call"], **state)

    def test_payment_needs_a_verified_caller(self):
        self.assertIn("verify first", s.gate("take_payment", {"amount": 184.20}, self.call()))

    def test_the_amount_is_the_balance_not_what_was_heard(self):
        self.assertIn("not the balance",
                      s.gate("take_payment", {"amount": 180.42}, self.call(verified="pin")))

    def test_the_payment_runs_only_on_the_isolated_path(self):
        self.assertIn("a person takes it",
                      s.gate("take_payment", {"amount": 184.20},
                             self.call(verified="pin", isolated_path=False)))
        self.assertIn("allowed", s.gate("take_payment", {"amount": 184.20},
                                        self.call(verified="pin")))

    def test_the_waiver_follows_memo_114(self):
        self.assertIn("memo 114", s.gate("apply_waiver", {"amount": 12.0},
                                         self.call(verified="pin", storm_area=False)))

    def test_an_unknown_tool_is_refused(self):
        self.assertIn("not a tool", s.gate("refund_everything", {}, self.call()))


class TestCard(unittest.TestCase):
    def test_the_hybrid_sends_the_provider_nothing(self):
        got = s.recipients("the hybrid", DATA["keyed_ms"], DATA["card_digits"])
        self.assertTrue(got["the speech provider"].startswith("0 frames"))

    def test_a_pure_session_streams_the_tones(self):
        got = s.recipients("pure speech-to-speech", DATA["keyed_ms"], DATA["card_digits"])
        self.assertTrue(got["the speech provider"].startswith("400 frames"))


class TestCheckLag(unittest.TestCase):
    def test_a_late_word_is_heard_before_any_check(self):
        lag = s.check_lag(DATA["wrong"], "fees", DATA["lag_ms"])
        self.assertEqual(lag["heard"], lag["words"])
        self.assertGreater(lag["acts_ms"], lag["ends_ms"])


class TestOneObject(unittest.TestCase):
    def test_fixed_steps_are_the_same_on_both_roads(self):
        for _, kind in DATA["flow"]:
            if kind == "fixed":
                self.assertEqual(s.compile_step(kind, "cascade"), s.compile_step(kind, "s2s"))

    def test_the_card_step_pauses_the_model(self):
        self.assertIn("paused", s.compile_step("isolated", "s2s"))


class TestOneCall(unittest.TestCase):
    def setUp(self):
        self.events = s.booking_turn(DATA["turn"])

    def test_the_filler_is_heard_inside_the_wall(self):
        heard = [ms for ms, _, e, _ in self.events if e == "the caller hears it"]
        self.assertLess(heard[0], 800)

    def test_the_outcome_is_spoken_after_the_commit(self):
        at = {e: ms for ms, _, e, _ in self.events}
        self.assertGreater(at["first audio: \"You're booked for Tuesday at nine.\""],
                           at["the scheduler commits the booking"])


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(s.report("mock").splitlines()[1:],
                         s.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
