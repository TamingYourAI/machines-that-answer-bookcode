"""Tests for the Chapter 17 lab. Run: python3 -m unittest test_tools_lab.py

The first group checks the release-blocking invariants the chapter states. The second checks
the mechanisms the prose describes, one claim per test.
"""
from __future__ import annotations

import unittest

import tools_lab as lab


class Invariants(unittest.TestCase):
    def setUp(self):
        self.faults = lab.load_faults("fixture")
        self.res = lab.experiment_retries(self.faults["link"])

    def test_operation_id_prevents_duplicates(self):
        self.assertEqual(self.res["operation id"]["duplicate action rate"], 0.0)
        self.assertEqual(self.res["operation id + reconcile"]["duplicate action rate"], 0.0)

    def test_naive_retry_duplicates(self):
        self.assertGreater(self.res["naive retry"]["duplicate action rate"], 0.0)

    def test_reconciliation_speaks_only_the_truth(self):
        self.assertEqual(self.res["operation id + reconcile"]["false commitment rate"], 0.0)

    def test_conditional_write_and_hold_never_double_book(self):
        self.assertEqual(lab.race("conditional write")[1], 0)
        self.assertEqual(lab.race("hold at offer")[1], 0)
        self.assertEqual(lab.race("check then book")[1], 4)

    def test_mock_and_fixture_agree(self):
        mock = lab.report("mock").splitlines()[1:]
        fixture = lab.report("fixture").splitlines()[1:]
        self.assertEqual(mock, fixture)


class Mechanisms(unittest.TestCase):
    def test_retry_returns_first_answer(self):
        cal = lab.Calendar(["Tue 09:00"])
        p = lab.Proposal("book_visit", "acct-1", (("slot", "Tue 09:00"),))
        self.assertEqual(cal.book(p, operation_id="op-1"), "booked")
        self.assertEqual(cal.book(p, operation_id="op-1"), "booked")
        self.assertEqual(cal.count("Tue 09:00", "acct-1"), 1)

    def test_same_id_different_terms_is_refused(self):
        cal = lab.Calendar(["Tue 09:00", "Thu 09:00"])
        tue = lab.Proposal("book_visit", "acct-1", (("slot", "Tue 09:00"),))
        thu = lab.Proposal("book_visit", "acct-1", (("slot", "Thu 09:00"),))
        cal.book(tue, operation_id="op-1")
        self.assertEqual(cal.book(thu, operation_id="op-1"), "mismatch")
        self.assertEqual(cal.count("Thu 09:00", "acct-1"), 0)

    def test_a_yes_does_not_cover_unheard_terms(self):
        c = lab.Confirmation(lab.TUESDAY.fingerprint(), frozenset({"slot", "address"}), 0.0, 1)
        ok, why = c.covers(lab.TUESDAY, lab.MATERIAL, 2.0, 1)
        self.assertFalse(ok)
        self.assertIn("fee", why)

    def test_a_yes_expires(self):
        c = lab.Confirmation(lab.TUESDAY.fingerprint(), frozenset(lab.MATERIAL), 0.0, 1)
        self.assertTrue(c.covers(lab.TUESDAY, lab.MATERIAL, lab.CONFIRM_TTL_S, 1)[0])
        self.assertFalse(c.covers(lab.TUESDAY, lab.MATERIAL, lab.CONFIRM_TTL_S + 1, 1)[0])

    def test_timeout_is_not_failure(self):
        cal = lab.Calendar(["Tue 09:00"])
        p = lab.Proposal("book_visit", "acct-1", (("slot", "Tue 09:00"),))
        link = lab.Link(["lost_response"])
        with self.assertRaises(lab.Timeout):
            link.call(lambda: cal.book(p, operation_id="op-1"))
        self.assertEqual(cal.lookup("op-1"), "booked")

    def test_every_failure_line_is_at_most_two_sentences(self):
        for f in lab.FAILURES:
            sentences = [s for s in f.line.replace("?", ".").split(".") if s.strip()]
            self.assertLessEqual(len(sentences), 2, f.code)


if __name__ == "__main__":
    unittest.main()
