"""Tests for the Chapter 11 turn-taking lab. Run: python3 -m unittest test_turn_lab.py"""
from __future__ import annotations

import unittest

import turn_lab as t

DATA = t.inputs("mock")


class TestCompleteness(unittest.TestCase):
    def test_half_an_account_number_is_not_an_answer(self):
        self.assertFalse(t.complete("my account number is two two", "account"))
        self.assertTrue(t.complete("my account number is two two three one",
                                   "account"))

    def test_no_digits_at_all_is_an_answer(self):
        self.assertTrue(t.complete("i don't have it here", "account"))

    def test_a_joining_word_is_never_the_end(self):
        for partial in ("my bill has doubled because", "um", "yes and"):
            self.assertFalse(t.complete(partial, "open"))

    def test_an_address_ends_on_the_street(self):
        self.assertFalse(t.complete("fourteen", "address"))
        self.assertTrue(t.complete("fourteen alder road", "address"))


class TestSweep(unittest.TestCase):
    def test_one_timer_trades_cut_offs_for_waiting(self):
        rates = [t.score(DATA["turns"], ms)["per_100"] for ms in (300, 700, 1100)]
        self.assertEqual(rates, sorted(rates, reverse=True))
        self.assertEqual(t.score(DATA["turns"], 700)["p50"], 720)

    def test_two_thresholds_are_polite_and_fast(self):
        two, one = t.score(DATA["turns"]), t.score(DATA["turns"], 900)
        self.assertLessEqual(two["per_100"], 2.0)
        self.assertEqual(two["p50"], t.SHORT_MS + t.FRAME_MS)
        self.assertLess(two["p50"], one["p50"])
        self.assertLessEqual(two["p95"] + t.OTHER_SPANS_MS, t.WALL_MS)

    def test_what_is_left_is_what_the_words_cannot_see(self):
        why = t.score(DATA["turns"])["why"]
        self.assertEqual(set(why), {"a yes, then more", "two sentences"})


class TestTrace(unittest.TestCase):
    def test_the_pilot_timer_cuts_the_number_in_half(self):
        events = t.trace(DATA["traced"], t.PILOT_TIMER_MS)
        self.assertIn("cut off", events[-1][1])

    def test_two_thresholds_wait_for_the_second_half(self):
        events = t.trace(DATA["traced"])
        self.assertEqual(events[-1], (3420, "end of turn: the agent answers"))


class TestOverlap(unittest.TestCase):
    def sound(self, name):
        return next(s for s in DATA["sounds"] if s["name"] == name)

    def test_a_backchannel_is_not_a_barge_in(self):
        mm = self.sound('"mm-hm"')
        self.assertEqual(t.overlap(mm, "stop on words")[0], "keep talking")
        self.assertEqual(t.overlap(mm, "pause on voice")[0], "resume")

    def test_a_barge_in_stops_within_the_voice_window(self):
        self.assertEqual(t.overlap(self.sound('"no, Thursday"'), "pause on voice"),
                         ("stop", t.VOICE_MS))

    def test_the_agents_own_echo_resumes_once_words_arrive(self):
        self.assertEqual(t.overlap(self.sound("own voice, echoed"),
                                   "pause on voice")[0], "resume")

    def test_a_keypress_always_stops(self):
        for p in t.POLICIES:
            self.assertEqual(t.overlap(self.sound("keypad 2"), p), ("stop", t.TONE_MS))


class TestHeard(unittest.TestCase):
    def test_the_cut_matches_chapters_6_and_8(self):
        self.assertEqual(t.line_ms(t.FEE_LINE), 6400)
        self.assertEqual(t.chars_at(t.FEE_LINE, 3300), 46)

    def test_the_history_keeps_only_what_was_heard(self):
        agent, caller = t.history_after_cut(t.FEE_LINE, 3300, "Yes, book it.")
        self.assertTrue(agent["cut_off"])
        self.assertNotIn("fee", agent["text"])
        self.assertEqual(caller["text"], "Yes, book it.")


class TestSilence(unittest.TestCase):
    def test_timers_start_when_the_question_has_played(self):
        self.assertAlmostEqual(t.silence_plan("most", 6.4)[0][0], 11.4)

    def test_a_relay_caller_is_never_ended_for_silence(self):
        self.assertEqual(t.silence_plan("relay", 0)[-1][0], float("inf"))

    def test_a_hold_checks_in_every_30_seconds_for_two_minutes(self):
        self.assertEqual([s for s, _ in t.silence_plan("hold", 0)],
                         [30, 60, 90, 120])


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(t.report("mock").splitlines()[1:],
                         t.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
