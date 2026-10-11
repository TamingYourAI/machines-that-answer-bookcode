"""Tests for the Chapter 20 lab. Run: python3 -m unittest test_identity_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import identity_lab as lab

DATA = lab.inputs("fixture")


class Lookup(unittest.TestCase):
    def test_a_number_finds_candidates_not_a_caller(self):
        self.assertEqual(lab.lookup("555 0131", DATA["records"]), ["2231"])
        self.assertEqual(len(lab.lookup("555 0158", DATA["records"])), 3)
        self.assertEqual(lab.lookup("555 0199", DATA["records"]), [])


class Ladder(unittest.TestCase):
    def test_a_number_match_proves_nothing(self):
        self.assertEqual(lab.step_up("none", "number match"), "none")
        self.assertEqual(lab.step_up("none", "voiceprint"), "none")

    def test_a_code_counts_only_on_top_of_a_pin(self):
        self.assertEqual(lab.step_up("none", "code to the phone on the account"), "none")
        level = lab.step_up("none", "account and PIN")
        self.assertEqual(lab.step_up(level, "code to the phone on the account"),
                         "pin + code")

    def test_an_address_change_needs_the_step_up(self):
        self.assertFalse(lab.allowed("change_address", "pin"))
        self.assertTrue(lab.allowed("change_address", "pin + code"))

    def test_card_payments_stay_with_a_person(self):
        self.assertFalse(lab.allowed("card_payment", "pin + code"))


class Chain(unittest.TestCase):
    def setUp(self):
        self.token = lab.mint("6120", "pin", ["pwd"], ["billing", "scheduling"],
                              issued=1205, jti="v-6120-1")

    def test_the_verified_account_is_read(self):
        ok, why = lab.check(self.token, "billing", "read_bill", "6120", 1206)
        self.assertTrue(ok)
        self.assertIn("caller 6120, actor service-line-agent", why)

    def test_another_account_on_the_same_number_is_refused(self):
        ok, why = lab.check(self.token, "billing", "read_bill", "6127", 1206)
        self.assertFalse(ok)
        self.assertIn("for 6120", why)

    def test_an_old_statement_is_refused(self):
        self.assertFalse(lab.check(self.token, "billing", "read_bill", "6120", 1221)[0])

    def test_a_system_not_named_refuses(self):
        self.assertFalse(lab.check(self.token, "payments", "read_bill", "6120", 1206)[0])

    def test_an_edited_statement_is_refused(self):
        forged = lab.edited(self.token, level="pin + code")
        ok, why = lab.check(forged, "billing", "change_address", "6120", 1206)
        self.assertFalse(ok)
        self.assertIn("signature", why)


class Memory(unittest.TestCase):
    def test_the_designed_memory_passes_all_five(self):
        self.assertEqual(sum(p for *_, p in lab.memory_tests(lab.DESIGNED, DATA)), 5)

    def test_the_naive_memory_passes_none(self):
        self.assertEqual(sum(p for *_, p in lab.memory_tests(lab.NAIVE, DATA)), 0)

    def test_nothing_is_recalled_before_verification(self):
        items = DATA["memory"]["household"]
        self.assertEqual(lab.recall(lab.DESIGNED, items, False, 640), [])


class Modes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        strip = lambda t: t.split("\n", 1)[1]
        self.assertEqual(strip(lab.report("mock")), strip(lab.report("fixture")))

    def test_output_fits_78_columns(self):
        for line in lab.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)

    def test_frozen_output(self):
        for mode in ("mock", "fixture"):
            frozen = (lab.OUTPUTS / f"identity_lab.{mode}.out.txt").read_text()
            self.assertEqual(lab.report(mode), frozen)


if __name__ == "__main__":
    unittest.main()
