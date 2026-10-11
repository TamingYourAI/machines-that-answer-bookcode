"""Tests for the Chapter 23 lab. Run: python3 -m unittest test_trust_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import trust_lab as lab

DATA = lab.inputs("fixture")


class WhereTheNumberLands(unittest.TestCase):
    def test_week_8_reached_the_five_places_in_the_record(self):
        got = lab.lands(DATA["forks"], "week 8")
        self.assertEqual(sorted(got), sorted(["recognizer", "model", "transcript",
                                              "evaluation copy", "recording"]))

    def test_at_launch_only_a_person_hears_the_whole_number(self):
        got = lab.lands(DATA["forks"], "at launch")
        whole = [k for k, v in got.items() if v == "whole"]
        self.assertEqual(whole, ["a person on the payments line"])
        self.assertNotIn("transcript", got)

    def test_the_isolated_path_reaches_only_the_processor(self):
        self.assertEqual(lab.lands(DATA["forks"], "isolated path"),
                         {"the payment processor": "whole"})


class ProvingIsolation(unittest.TestCase):
    def test_every_fork_stopped_opens_the_path(self):
        ok, _ = lab.prove_isolation(DATA["runs"]["A"])
        self.assertTrue(ok)

    def test_a_fork_that_says_paused_and_keeps_receiving_blocks_it(self):
        ok, rows = lab.prove_isolation(DATA["runs"]["B"])
        self.assertFalse(ok)
        self.assertIn(("recording", "paused", 4000, "said paused; still receiving"), rows)

    def test_a_fork_that_does_not_pause_blocks_it(self):
        fork = {"name": "x", "says": "running", "bytes_before": 0, "bytes_after": 10}
        ok, rows = lab.prove_isolation([fork])
        self.assertFalse(ok)
        self.assertEqual(rows[0][3], "did not pause")

    def test_the_agent_receives_a_token_and_a_status_never_the_digits(self):
        res = lab.take_payment(True, DATA["card"], DATA["amount"], DATA["processor"])
        self.assertEqual(res["status"], "approved")
        self.assertNotIn(DATA["card"], " ".join(str(v) for v in res.values()))
        self.assertEqual(res["card_ends"], DATA["card"][-4:])

    def test_without_proof_no_keys_are_collected_and_another_way_is_offered(self):
        res = lab.take_payment(False, DATA["card"], DATA["amount"], DATA["processor"])
        self.assertEqual(res["status"], "not taken")
        self.assertIn("secure link", res["offer"])

    def test_the_payment_still_completes_by_link(self):
        self.assertEqual(DATA["link"]["status"], "approved")
        report = lab.report("fixture")
        self.assertIn("the case closes paid", report)


class Redaction(unittest.TestCase):
    def outputs(self):
        """Each turn through the three filters, a new redactor per call."""
        rows, call, red = [], None, None
        for c, u, holds in DATA["utterances"]:
            if c != call:
                call, red = c, lab.Redactor()
            rows.append((u, holds, lab.naive(u), lab.checksum(u),
                         red.turn(u)))
        return rows

    def test_a_naive_filter_misses_card_numbers_said_as_words(self):
        u, holds, naive, _, _ = self.outputs()[2]
        self.assertEqual(holds, "card")
        self.assertEqual(lab.left(naive), 16)

    def test_the_span_redactor_leaves_no_card_or_code_digits(self):
        for u, holds, _, _, spans in self.outputs():
            if holds != "neither":
                self.assertEqual(lab.left(spans), 0, u)

    def test_it_leaves_account_and_phone_numbers_alone(self):
        rows = [r for r in self.outputs() if "account" in r[0]]
        self.assertEqual(rows[0][4], rows[0][0])

    def test_one_misheard_digit_defeats_a_filter_that_needs_the_checksum(self):
        u, holds, _, luhn, spans = self.outputs()[5]
        self.assertEqual(holds, "misheard")
        self.assertFalse(lab.luhn("4111111111111112"))
        self.assertEqual(lab.left(luhn), 16)
        self.assertEqual(lab.left(spans), 0)

    def test_a_number_read_in_two_turns_is_masked_in_both(self):
        halves = [r for r in self.outputs() if r[1].endswith("half")]
        self.assertEqual([lab.left(r[3]) for r in halves], [8, 8])
        self.assertEqual([lab.left(r[4]) for r in halves], [0, 0])

    def test_double_one_is_read_as_eleven(self):
        self.assertEqual(lab.spoken_digits("four double one"), ["4", "11"])
        self.assertEqual(lab.spoken_digits("double check"),
                         ["double", "check"])

    def test_it_errs_toward_masking_an_order_number_of_card_length(self):
        rows = [r for r in self.outputs() if "order" in r[0]]
        self.assertIn("[card]", rows[0][4])


class Signals(unittest.TestCase):
    def setUp(self):
        self.fired = {name: (seen, t) for name, _, seen, t in lab.signals(DATA["evening"])}

    def test_one_number_probing_accounts_fires_on_the_fourth(self):
        seen, t = self.fired["accounts tried from one number"]
        self.assertEqual((seen, lab.clock(t)), ("555 0188: 4 accounts", "21:05"))

    def test_failed_checks_on_one_account_from_four_numbers_fire(self):
        seen, t = self.fired["failed checks on one account"]
        self.assertEqual(seen, "4012: 4 numbers")

    def test_a_flood_of_silent_calls_fires_and_ordinary_callers_do_not(self):
        self.assertEqual(self.fired["silent calls a minute"][0], "18")
        self.assertEqual(len(self.fired), 3)


class Modes(unittest.TestCase):
    def test_fixture_matches_mock(self):
        self.assertEqual(lab.report("mock").splitlines()[1:],
                         lab.report("fixture").splitlines()[1:])

    def test_output_fits_78_columns(self):
        self.assertTrue(all(len(x) <= 78 for x in lab.report("mock").splitlines()))


if __name__ == "__main__":
    unittest.main()
