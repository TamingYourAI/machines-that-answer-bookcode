"""Tests for the Chapter 10 hearing lab. Run: python3 -m unittest test_hearing_lab.py"""
from __future__ import annotations

import unittest

import hearing_lab as h

DATA = h.inputs("mock")


class TestWer(unittest.TestCase):
    def test_alignment_counts_each_kind_of_error(self):
        self.assertEqual(h.align("a b c d".split(), "a x c".split()), (1, 1, 0))
        self.assertEqual(h.align("a b".split(), "z a b".split()), (0, 0, 1))

    def test_errors_rise_with_the_condition(self):
        rates = [h.wer(h.results(DATA, c)) for c in h.CONDITIONS]
        self.assertEqual(rates, sorted(rates))

    def test_a_low_rate_can_hide_wrong_entities(self):
        right, total = h.entity_accuracy(h.results(DATA, "phone"))
        self.assertLess(h.wer(h.results(DATA, "phone")), 0.1)
        self.assertLess(right / total, 0.7)


class TestPartials(unittest.TestCase):
    def test_a_revised_word_is_never_stable(self):
        texts = [t for _, t in DATA["partials"]]
        for stable in h.stable_prefix(texts):
            self.assertNotIn(" to", f" {stable}")

    def test_the_last_stable_prefix_is_the_final(self):
        texts = [t for _, t in DATA["partials"]]
        self.assertEqual(h.stable_prefix(texts)[-1], texts[-1])


class TestBoost(unittest.TestCase):
    def names(self, boost):
        pairs = h.results(DATA, "phone", boost)
        return {w for _, hyp in pairs for w in hyp.split()} & set(h.VOCAB)

    def test_boost_recovers_the_names(self):
        self.assertNotIn("kestrel", self.names(0.0))
        self.assertTrue({"kestrel", "ashby"} <= self.names(0.4))

    def test_too_much_boost_hears_names_nobody_said(self):
        pairs = h.results(DATA, "phone", 0.8)
        self.assertIn("i need to alder my payment date", [p for _, p in pairs])


class TestNumbers(unittest.TestCase):
    def test_every_way_of_saying_2231(self):
        for spoken in ("two two three one", "double two three one",
                       "twenty two thirty one"):
            self.assertEqual(h.digits(spoken.split()), "2231")

    def test_a_short_account_is_asked_again(self):
        self.assertIn("ask again", h.account("to two three one"))

    def test_sound_alike_amounts_are_spelled_back(self):
        self.assertIn('"one five"', h.amount("fifteen"))
        self.assertEqual(h.amount("twenty five"), "25: confirm")


class TestCohorts(unittest.TestCase):
    def test_small_samples_give_wide_intervals(self):
        lo_big, hi_big = h.wilson(372, 400)
        lo_small, hi_small = h.wilson(10, 12)
        self.assertLess(hi_big - lo_big, hi_small - lo_small)

    def test_verdicts(self):
        self.assertEqual(h.verdict(372, 400, 0.9), "meets")
        self.assertEqual(h.verdict(48, 60, 0.9), "below")
        self.assertEqual(h.verdict(10, 12, 0.9), "unknown")


class TestKept(unittest.TestCase):
    def test_accounts_and_emails_are_redacted(self):
        self.assertEqual(h.keep(DATA["finals"][0]),
                         "my account number is [account]")
        self.assertEqual(h.keep(DATA["finals"][1]), "my email is [email]")

    def test_a_card_number_is_never_kept(self):
        self.assertIn("incident", h.keep(DATA["finals"][2]))


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(h.report("mock").splitlines()[1:],
                         h.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
