"""Tests for the Chapter 18 guard lab. Run: python3 -m unittest test_guard_lab.py"""
from __future__ import annotations

import inspect
import json
import unittest

import guard_lab as g

DATA = g.inputs("mock")


def end_of_call() -> g.State:
    return g.state_of(DATA["coached"])


def at_offer() -> g.State:
    lines = DATA["coached"]["money_lines"]
    return g.State(money_lines=lines, money_now=lines[0], step="offer")


class TestCommitmentCheck(unittest.TestCase):
    def test_a_committed_booking_may_be_spoken(self):
        verdict, why = g.check("You're booked for Wednesday at nine.", end_of_call())
        self.assertEqual(verdict, "speak")
        self.assertIn("op-6b7c", why)

    def test_a_booking_not_yet_committed_is_blocked(self):
        verdict, _ = g.check("You're booked for Tuesday at nine.", at_offer())
        self.assertEqual(verdict, "block")

    def test_a_promise_needs_a_promise_record(self):
        self.assertEqual(g.check("I'll text you the details.", end_of_call())[0], "speak")
        self.assertEqual(g.check("A technician will call you soon.", end_of_call())[0], "block")

    def test_money_is_spoken_only_as_a_fixed_line(self):
        s = end_of_call()
        self.assertEqual(g.check(s.money_lines[1], s)[0], "speak")
        verdict, why = g.check("The fee is forty dollars, same as always.", s)
        self.assertEqual(verdict, "replace")
        self.assertIn(s.money_now, why)

    def test_a_false_exception_is_blocked(self):
        verdict, why = g.check("I've made an exception this time, so there's no "
                               "call-out fee.", end_of_call())
        self.assertEqual((verdict, why), ("block", "no committed waive_callout"))

    def test_paraphrases_leak_through_patterns_but_not_structure(self):
        counts = dict(g.paraphrase_counts(DATA))
        self.assertEqual(counts["claim patterns alone"], 4)
        self.assertEqual(counts["+ the money rule"], 10)
        self.assertEqual(counts["+ fixed lines at the fee step"], 12)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.rows = {r["defense"]: r for r in
                     g.persistence(DATA["give_in"], DATA["runs"], seed=18)}

    def test_the_prompt_alone_grants_what_it_promises(self):
        r = self.rows["the prompt only"]
        self.assertGreater(r["waived"], 0)
        self.assertEqual(r["waived"], r["promised"])

    def test_the_policy_layer_stops_the_action_but_not_the_words(self):
        r = self.rows["+ the policy layer on tools"]
        self.assertEqual(r["waived"], 0)
        self.assertEqual(r["promised"], self.rows["the prompt only"]["promised"])

    def test_the_commitment_check_stops_the_words(self):
        self.assertEqual(self.rows["+ the commitment check"]["promised"], 0)
        self.assertEqual(self.rows["+ the commitment check"]["asks"], 9.0)

    def test_two_refusals_then_a_person(self):
        r = self.rows["+ two refusals, then a person"]
        self.assertEqual(r["asks"], 2.0)
        self.assertEqual(r["offered"], DATA["runs"])


class TestInjection(unittest.TestCase):
    def test_the_policy_layer_has_no_input_for_words(self):
        self.assertEqual(list(inspect.signature(g.decide).parameters), ["tool", "st"])
        for st in DATA["states"].values():
            self.assertNotIn("words", st)

    def test_an_obedient_model_changes_nothing(self):
        rows = g.injections(DATA)
        self.assertTrue(all(r["policy"] != "allowed" for r in rows if r["tool"]))
        self.assertFalse(any(r["verdict"] == "speak" for r in rows))


class TestDriftReplayRecord(unittest.TestCase):
    def test_compaction_keeps_every_window_under_the_alert(self):
        rows = g.drift(DATA["drift"], seed=18)
        self.assertTrue(all(r["compacted"] <= DATA["drift"]["alert"] for r in rows))
        self.assertGreater(rows[-1]["whole"], DATA["drift"]["alert"])

    def test_replay_finds_the_one_regression_and_writes_nothing(self):
        rep = g.replay(DATA["recorded"], "1.3", "1.4")
        self.assertEqual(len(rep["same"]), 7)
        self.assertEqual([c for c, _ in rep["wording"]], ["r02", "r08"])
        self.assertEqual(rep["changed"], [("r07", "read_back")])
        self.assertEqual(rep["tools"].reached, 0)
        self.assertEqual(sum(rep["tools"].suppressed.values()), 10)

    def test_the_record_explains_the_turn_on_its_own(self):
        r = DATA["record"]
        for key in ("heard", "versions", "proposal", "policy", "check", "spoken"):
            self.assertIn(key, r)
        text = g.explain(r)
        self.assertIn("rule 5a", text)
        self.assertIn("never played", text)


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        mock = g.report("mock").splitlines()[1:]
        fixture = g.report("fixture").splitlines()[1:]
        self.assertEqual(mock, fixture)

    def test_fixture_matches_the_data(self):
        stored = json.loads((g.FIXTURES / "guard.json").read_text())
        self.assertEqual(stored, json.loads(json.dumps(g.inputs("mock"))))

    def test_output_fits_the_page(self):
        for line in g.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
