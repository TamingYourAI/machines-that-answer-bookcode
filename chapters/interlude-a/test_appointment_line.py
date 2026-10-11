"""Tests for the Interlude A lab. Run: python3 -m unittest test_appointment_line.py"""
from __future__ import annotations

import copy
import unittest

import appointment_line as a


def fresh():
    docs, cal, script = a.load("mock")
    return docs, a.Systems(copy.deepcopy(cal)), script


class TestCalls(unittest.TestCase):
    def test_booking_books_once_and_texts(self):
        docs, sys_, script = fresh()
        c = a.run_call("booking", script["booking"], sys_, docs)
        self.assertEqual(c.ended, "booked")
        self.assertEqual(sys_.cal["tue-0900"]["booked"], "555 0142")
        self.assertEqual(len(sys_.outbox), 1)

    def test_each_yes_gets_its_own_id_and_a_replay_must_match(self):
        docs, sys_, script = fresh()
        first, second = sys_.mint(), sys_.mint()
        self.assertNotEqual(first, second)
        version = sys_.cal["tue-0900"]["version"]
        self.assertEqual(sys_.book(first, "tue-0900", "555 0142", version), "booked")
        self.assertEqual(sys_.book(first, "tue-0900", "555 0142", version), "booked")
        self.assertIn("other terms", sys_.book(first, "wed-0900", "555 0142", version))

    def test_the_agent_speaks_only_after_the_booking_is_read_back(self):
        docs, sys_, script = fresh()
        c = a.run_call("booking", script["booking"], sys_, docs)
        layers = [layer for _, layer, what in c.trace]
        book_at = next(i for i, (_, _, w) in enumerate(c.trace) if w.startswith("book "))
        self.assertEqual(layers[book_at + 1:], ["systems", "speaking"])

    def test_change_of_mind_releases_the_first_hold(self):
        docs, sys_, script = fresh()
        a.run_call("change", script["change"], sys_, docs)
        self.assertIsNone(sys_.cal["tue-0900"]["held"])
        self.assertIsNone(sys_.cal["tue-0900"]["booked"])
        self.assertEqual(sys_.cal["wed-0900"]["booked"], "555 0177")

    def test_person_gets_a_whisper_and_nothing_is_booked(self):
        docs, sys_, script = fresh()
        c = a.run_call("person", script["person"], sys_, docs)
        self.assertEqual(sys_.transfers[0]["whisper"], "Blocked drain. Wants Tuesday. Not booked.")
        self.assertFalse(any(s["booked"] or s["held"] for s in sys_.cal.values()))
        self.assertEqual(c.ended, "transferred with a whisper")


class TestFailures(unittest.TestCase):
    def test_recognizer_failure_ends_in_a_text_and_a_promise(self):
        docs, sys_, script = fresh()
        c = a.run_call("deaf", script["deaf"], sys_, docs)
        self.assertEqual(c.ended, "fallback: text and callback promise")
        self.assertEqual(len(sys_.promises), 1)

    def test_last_slot_cannot_be_booked_twice(self):
        docs, sys_, script = fresh()
        lines = a.last_slot(sys_)
        self.assertIn("refused", lines[3])
        self.assertIn("booked (same record)", lines[4])
        booked = [r for r in sys_.journal.values() if r["result"] == "booked"]
        self.assertEqual(len(booked), 1)

    def test_unknown_question_is_not_answered_from_the_model(self):
        docs, sys_, script = fresh()
        c = a.run_call("unknown", script["unknown"], sys_, docs)
        self.assertEqual(c.ended, "out of scope: message taken")

    def test_kill_switch_goes_straight_to_the_owner(self):
        docs, sys_, script = fresh()
        c = a.run_call("kill", script["booking"], sys_, docs, kill=True)
        self.assertEqual(len(c.said), 1)
        self.assertEqual(len(sys_.transfers), 1)


class TestModes(unittest.TestCase):
    def test_agent_lines_are_at_most_two_sentences(self):
        docs, sys_, script = fresh()
        for name in ("hours", "booking", "change", "person", "deaf", "unknown"):
            c = a.run_call(name, script[name], sys_, docs)
            for who, line in c.said:
                if who == "Agent":
                    self.assertLessEqual(line.count(". ") + line.count("? ") + 1, 2, line)

    def test_mock_and_fixture_agree(self):
        strip = lambda t: t.split("\n", 1)[1]
        self.assertEqual(strip(a.report("mock")), strip(a.report("fixture")))

    def test_output_fits_78_columns(self):
        for line in a.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
