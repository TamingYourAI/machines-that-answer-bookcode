"""Tests for the Interlude B lab. Run: python3 -m unittest test_service_slice.py

One claim from the interlude per test.
"""
from __future__ import annotations

import unittest

import service_slice as lab

DATA = lab.inputs("fixture")


class Identity(unittest.TestCase):
    def setUp(self):
        self.stmt = lab.mint("6120", "pin", ["billing"], 0)

    def test_the_statement_allows_its_own_account(self):
        self.assertEqual(lab.check(self.stmt, "billing", "read_bill", "6120", 60)[0], True)

    def test_it_refuses_another_account(self):
        ok, why = lab.check(self.stmt, "billing", "read_bill", "6127", 60)
        self.assertFalse(ok)
        self.assertIn("6120", why)

    def test_an_edited_level_breaks_the_signature(self):
        stmt = {"body": dict(self.stmt["body"], level="pin + code"), "sig": self.stmt["sig"]}
        self.assertIn("signature", lab.check(stmt, "billing", "read_bill", "6120", 60)[1])

    def test_it_expires_after_fifteen_minutes(self):
        self.assertIn("expired", lab.check(self.stmt, "billing", "read_bill", "6120", 900)[1])


class HeardState(unittest.TestCase):
    def test_marks_prove_the_slot_was_heard_and_the_fee_was_not(self):
        heard = lab.heard_terms(DATA["booking_line"], DATA["cut_ms"], DATA["marks_every"])
        self.assertEqual(heard, ["the slot"])

    def test_a_yes_covers_only_what_was_heard(self):
        p = lab.visit("5108", lab.SLOTS["this Tuesday"])
        yes = lab.Confirmation(p.fingerprint(), frozenset(["the slot"]), 0, 7)
        self.assertEqual(yes.covers(p, 2, 7), (False, "the fee not heard"))


class TheYes(unittest.TestCase):
    """Chapter 17's other three checks, carried into the slice."""

    def setUp(self):
        self.p = lab.visit("5108", lab.SLOTS["this Tuesday"])
        self.yes = lab.Confirmation(self.p.fingerprint(),
                                    frozenset(lab.MATERIAL), 0, 7)

    def test_a_yes_from_a_canceled_turn_covers_nothing(self):
        self.assertEqual(self.yes.covers(self.p, 2, 8)[1], "canceled turn")

    def test_a_yes_for_tuesday_does_not_cover_one_oclock(self):
        other = lab.visit("5108", lab.SLOTS["one o'clock"])
        self.assertEqual(self.yes.covers(other, 2, 7)[1], "terms changed")

    def test_a_yes_expires_after_ninety_seconds(self):
        self.assertEqual(self.yes.covers(self.p, 91, 7)[1], "yes expired")


class OneAction(unittest.TestCase):
    def setUp(self):
        self.sched = lab.Scheduler(lose_answer=True)
        self.p = lab.visit("5108", lab.SLOTS["this Tuesday"])

    def test_reconciling_by_the_same_id_keeps_one_visit(self):
        result = lab.book_visit(self.sched, lab.Journal(), self.p, 0)
        self.assertEqual((result, len(self.sched.visits_for("5108"))),
                         ("committed", 1))

    def test_a_retry_under_a_new_id_meets_her_own_booking(self):
        result = lab.book_visit(self.sched, lab.Journal(), self.p, 0,
                                reconcile=False)
        self.assertEqual((result, len(self.sched.visits_for("5108"))),
                         ("conflict", 1))

    def test_the_id_is_journaled_before_the_write(self):
        journal = lab.Journal()
        oid = journal.mint(self.p)
        self.assertEqual(journal.ops[oid]["status"], "submitted")
        self.assertNotIn(oid, self.sched.by_operation)


class OneIdPerYes(unittest.TestCase):
    BUILT = dict(lab.one_id_cases(False))
    PER_YES = dict(lab.one_id_cases(True))

    def test_a_built_id_says_booked_falsely_three_times(self):
        self.assertEqual(sum(1 for r in self.BUILT.values()
                             if r.startswith("false")), 3)

    def test_one_id_per_yes_never_says_booked_falsely(self):
        self.assertFalse(any(r.startswith("false")
                             for r in self.PER_YES.values()))

    def test_a_later_tuesday_and_a_rebooking_are_new_visits(self):
        self.assertEqual(self.PER_YES["a later Tuesday at nine, a new yes"],
                         "booked")
        self.assertEqual(self.PER_YES["cancel, then the same slot again"],
                         "booked")

    def test_a_replay_with_other_terms_is_refused(self):
        self.assertEqual(self.PER_YES["an old id replayed with other terms"],
                         "refused")

    def test_a_restart_reads_the_journal_and_the_outcome_back(self):
        self.assertEqual(self.PER_YES["a restart while the outcome is open"],
                         "read back")

    def test_the_business_rule_catches_the_same_visit_twice(self):
        self.assertEqual(self.PER_YES["the same visit asked for again"],
                         "already booked")


class PaymentAndTransfer(unittest.TestCase):
    def test_a_fork_still_receiving_keeps_the_path_shut(self):
        self.assertEqual(lab.pay(DATA["forks_bad"])["path"], "link")

    def test_trusting_the_acknowledgement_puts_the_card_in_the_recording(self):
        self.assertTrue(lab.pay(DATA["forks_bad"], trust_the_ack=True)["card_in_recording"])

    def test_the_record_is_complete_and_the_whisper_under_fifteen_words(self):
        tr = lab.refer(DATA["record"], DATA["whisper"], 0, 180)
        self.assertEqual(tr["missing"], [])
        self.assertLess(tr["whisper_words"], 15)
        self.assertEqual(tr["desk"], "carried")

    def test_a_verification_ten_minutes_old_is_checked_again(self):
        self.assertEqual(lab.refer(DATA["record"], DATA["whisper"], 0, 600)["desk"],
                         "verifies again")


class Acceptance(unittest.TestCase):
    def test_the_slice_passes_all_four_scenarios(self):
        self.assertTrue(all(ok for ok, _ in lab.scenarios(DATA).values()))

    def test_each_piece_removed_fails_only_the_scenario_it_guards(self):
        for name, piece in lab.GUARDS.items():
            res = lab.scenarios(DATA, remove=piece)
            self.assertFalse(res[name][0], name)
            self.assertTrue(all(ok for k, (ok, _) in res.items() if k != name), piece)


class OneCallEndToEnd(unittest.TestCase):
    def test_the_pin_saves_the_search_for_her_bill(self):
        c = lab.part_v_call(DATA["recurring_call"])
        self.assertEqual((c["before"], c["after"], c["saved"]), (320, 236, 84))

    def test_part_v_adds_six_pieces_and_asks_for_no_account_number(self):
        steps = DATA["recurring_call"]["steps"]
        self.assertEqual(lab.part_v_call(DATA["recurring_call"])["pieces"], 6)
        self.assertFalse(any("number on your bill" in s[2] for s in steps))

    def test_memory_is_used_only_after_verification(self):
        steps = DATA["recurring_call"]["steps"]
        verified = next(i for i, s in enumerate(steps) if "statement" in s[2])
        recalled = next(i for i, s in enumerate(steps) if "text me" in s[2])
        self.assertGreaterEqual(recalled, verified)


class Modes(unittest.TestCase):
    def test_fixture_matches_mock(self):
        self.assertEqual(lab.report("mock").splitlines()[1:],
                         lab.report("fixture").splitlines()[1:])

    def test_output_fits_78_columns(self):
        self.assertTrue(all(len(x) <= 78 for x in lab.report("mock").splitlines()))


if __name__ == "__main__":
    unittest.main()
