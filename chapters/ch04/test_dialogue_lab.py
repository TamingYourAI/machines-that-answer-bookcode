"""Tests for the Chapter 4 dialogue lab. Run: python3 -m unittest test_dialogue_lab.py"""
from __future__ import annotations

import unittest

import dialogue_lab as d


class TestConfirmation(unittest.TestCase):
    def test_identifiers_are_read_back_in_groups(self):
        slot = d.book_visit_flow()["slots"][1]
        self.assertEqual(d.read_back(slot, "2231"), "That's two two, three one. Is that right?")

    def test_low_risk_needs_no_read_back(self):
        slot = d.book_visit_flow()["slots"][3]
        self.assertIsNone(d.read_back(slot, "It's blank."))


class TestDesigns(unittest.TestCase):
    def setUp(self):
        self.flow, self.calls = d.load("mock")

    def test_happy_path_books_in_both_designs(self):
        for catalog in (False, True):
            self.assertEqual(d.run(self.flow, self.calls["happy path"], catalog).outcome,
                             "booked")

    def test_v1_loops_on_a_misheard_number_and_v2_recovers(self):
        v1 = d.run(self.flow, self.calls["misheard number"], False)
        v2 = d.run(self.flow, self.calls["misheard number"], True)
        self.assertEqual(v1.outcome, "hung up in a loop")
        self.assertEqual(v2.outcome, "booked")

    def test_a_person_on_the_second_request_at_most(self):
        r = d.run(self.flow, self.calls["asks for a person"], True)
        self.assertEqual(r.outcome, "handed over with context")
        self.assertLessEqual(sum(1 for who, _ in r.lines if who == "Agent"), 3)

    def test_after_offering_a_person_a_request_is_honored_at_once(self):
        r = d.run(self.flow, self.calls["out of scope"], True)
        self.assertEqual(r.outcome, "handed over with context")

    def test_silence_ends_with_a_text_not_a_loop(self):
        r = d.run(self.flow, self.calls["silence"], True)
        self.assertEqual(r.outcome, "text sent, call ended")

    def test_the_catalog_never_repeats_itself(self):
        for turns in self.calls.values():
            self.assertEqual(d.run(self.flow, turns, True).repeats, 0)


class TestReadAloud(unittest.TestCase):
    def test_happy_path_passes(self):
        flow, calls = d.load("mock")
        r = d.run(flow, calls["happy path"], True)
        self.assertEqual(d.read_aloud([t for who, t in r.lines if who == "Agent"]), [])

    def test_a_three_sentence_line_fails(self):
        self.assertTrue(d.read_aloud(["One. Two. Three."]))


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        strip = lambda t: t.split("\n", 1)[1]
        self.assertEqual(strip(d.report("mock")), strip(d.report("fixture")))

    def test_output_fits_78_columns(self):
        for line in d.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
