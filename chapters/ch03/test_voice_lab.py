"""Tests for the Chapter 3 voice lab. Run: python3 -m unittest test_voice_lab.py"""
from __future__ import annotations

import unittest

import voice_lab as v


class TestBrief(unittest.TestCase):
    def test_service_line_brief_is_complete(self):
        self.assertEqual(v.check_brief(v.service_line_brief()), [])

    def test_disclosure_must_come_first(self):
        b = v.service_line_brief()
        b["disclosure"]["opening"] = "Hi there! This is an automated assistant."
        self.assertIn("the first sentence does not say it is automated", v.check_brief(b))

    def test_never_say_phrases_are_caught_in_test_lines(self):
        b = v.service_line_brief()
        b["test_lines"][5] = "Per policy, the earliest visit is Thursday."
        self.assertTrue(any("never-say" in p for p in v.check_brief(b)))


class TestEar(unittest.TestCase):
    def test_memo_fails_and_rewrite_passes(self):
        self.assertEqual(len(v.ear_check(v.MEMO)), 4)
        self.assertEqual(v.ear_check(v.FOR_THE_EAR), [])

    def test_abbreviation_does_not_split_a_sentence(self):
        self.assertEqual(len(v.sentences(v.MEMO)), 1)


class TestSaying(unittest.TestCase):
    def test_digits_in_groups_with_no_stranded_digit(self):
        self.assertEqual(v.say_digits("4417"), "four four, one seven")
        self.assertEqual(v.say_digits("2125550142"),
                         "two one two, five five five, zero one four two")

    def test_money_and_times(self):
        self.assertEqual(v.say_money("40"), "forty dollars")
        self.assertEqual(v.say_money("124.50"),
                         "one hundred twenty-four dollars and fifty cents")
        self.assertEqual(v.say_time("09:00"), "nine in the morning")

    def test_canon_address_and_date(self):
        self.assertEqual(v.say_address("14 Alder Rd"), "fourteen Alder Road")
        self.assertEqual(v.say_date("2026-09-29"), "Tuesday the twenty-ninth of September")

    def test_codes_spell_letters(self):
        self.assertEqual(v.say_code("K7B"), "K for kilo, seven, B for bravo")


class TestListening(unittest.TestCase):
    def test_the_most_natural_voice_fails_on_numbers(self):
        brief, panel = v.load("mock")
        a, b = v.score(panel["A"]), v.score(panel["B"])
        self.assertGreater(a["natural"], b["natural"])
        self.assertTrue(v.verdict(a))
        self.assertEqual(v.verdict(b), [])


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        strip = lambda t: t.split("\n", 1)[1]
        self.assertEqual(strip(v.report("mock")), strip(v.report("fixture")))

    def test_output_fits_78_columns(self):
        for line in v.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
