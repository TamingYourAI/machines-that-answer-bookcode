"""Tests for the Chapter 14 core lab. Run: python3 -m unittest test_core_lab.py"""
from __future__ import annotations

import json
import unittest

import core_lab as c

DATA = c.inputs("mock")


def state(**kw) -> c.State:
    slots = dict(DATA["slots"], meter_days=kw.pop("meter_days", 21))
    return c.State(call="t", case="t", flows=kw.pop("flows", ["visit"]),
                   slots=slots, **kw)


def yes_for(slot: str, heard: list[str]) -> dict:
    return {"fingerprint": c.Proposal("book_visit", {"slot": slot}).fingerprint(),
            "heard": heard}


TUE = c.Proposal("book_visit", {"slot": "Tue 09:00"})
ALL = ["slot", "address", "fee"]


class TestPolicy(unittest.TestCase):
    def test_a_write_needs_a_verified_caller(self):
        self.assertEqual(c.decide(TUE, state()), "refused: verify first")

    def test_a_tool_outside_the_flow_is_refused(self):
        self.assertIn("not in this flow", c.decide(c.Proposal("read_bill"), state(verified="pin")))

    def test_a_read_needs_no_yes(self):
        self.assertEqual(c.decide(c.Proposal("find_slot", {"day": "Tue"}), state()), "allowed")

    def test_a_yes_covers_only_its_own_terms(self):
        s = state(verified="pin", yes=yes_for("Tue 09:00", ALL))
        self.assertEqual(c.decide(TUE, s), "allowed")
        wed = c.Proposal("book_visit", {"slot": "Wed 09:00"})
        self.assertEqual(c.decide(wed, s), "refused: other terms")

    def test_a_term_not_heard_is_not_agreed(self):
        s = state(verified="pin", yes=yes_for("Tue 09:00", ["slot", "address"]))
        self.assertEqual(c.decide(TUE, s), "refused: fee not heard")

    def test_a_person_decides_is_a_wait_not_a_yes(self):
        waive = c.Proposal("waive_callout", {"amount": 40.0})
        self.assertTrue(c.decide(waive, state(verified="pin")).startswith("wait"))

    def test_the_rules_come_before_the_rung(self):
        waive = c.Proposal("waive_callout", {"amount": 40.0})
        self.assertIn("not new", c.decide(waive, state(verified="pin", meter_days=730)))


class TestStyles(unittest.TestCase):
    rows = c.styles(DATA)

    def designed(self, style: str) -> list[int]:
        return [sum(e == r["designed"] for e in r["ends"][style]) for r in self.rows]

    def test_guided_ends_as_designed_on_every_call(self):
        self.assertEqual(self.designed("guided"), [DATA["runs"]] * len(DATA["calls"]))

    def test_scripted_loses_a_second_request(self):
        self.assertEqual(c.scripted(["visit+bill", "id", "yes"]), "the bill question lost")

    def test_scripted_cannot_follow_a_change_of_mind(self):
        self.assertIn("a person", c.scripted(["visit", "id", "change", "yes"]))

    def test_free_form_usually_follows_its_prompt_and_sometimes_not(self):
        got = self.designed("free-form")
        self.assertGreater(sum(got), 0.9 * DATA["runs"] * len(got))
        self.assertLess(sum(got), DATA["runs"] * len(got))


class TestLoop(unittest.TestCase):
    def test_a_stale_result_is_not_spoken_but_its_outcome_is_kept(self):
        s = c.State(call="t", case="t", epoch=7, operations={"op 7f3a": "submitted"})
        c.on_event(s, DATA["events"][1])
        self.assertIsNone(c.on_event(s, DATA["events"][2]))
        self.assertEqual(s.operations["op 7f3a"], "committed")
        self.assertIn("booked already", c.on_event(s, DATA["events"][3]))

    def test_without_epochs_the_canceled_response_revives(self):
        spoken = c.late_result(DATA, epochs=False)
        self.assertEqual(spoken[0][0], DATA["events"][2]["t"])


class TestState(unittest.TestCase):
    def test_state_round_trips_through_json(self):
        s = c.turn_six(DATA)
        self.assertEqual(c.State(**json.loads(c.save(s))), s)

    def test_resume_reconciles_before_speaking(self):
        s, line = c.resume(c.save(c.turn_six(DATA)), lambda op: "committed")
        self.assertEqual(s.operations["op 7f3a"], "committed")
        self.assertIn("You're booked", line)

    def test_an_operation_not_found_is_offered_again_not_claimed(self):
        _, line = c.resume(c.save(c.turn_six(DATA)), lambda op: "not found")
        self.assertIn("Shall I book", line)

    def test_without_saved_state_the_call_starts_again(self):
        s, line = c.resume(None, lambda op: "committed")
        self.assertIsNone(s)
        self.assertIn("How can I help?", line)


class TestApproval(unittest.TestCase):
    def test_an_approval_outlives_the_call(self):
        a = c.approval_life(DATA)
        self.assertEqual(a["status"], "approved")
        self.assertGreater(a["decided_at"], a["call_ends_at"])

    def test_an_undecided_approval_expires_to_the_desk(self):
        data = dict(DATA, approval=dict(DATA["approval"], decided_at=None))
        self.assertEqual(c.approval_life(data)["status"], "expired")


class TestPatterns(unittest.TestCase):
    def test_only_calls_on_the_turn_add_time(self):
        got = {name: c.on_the_turn(calls) for name, calls in DATA["patterns"]}
        self.assertEqual(got["one agent (the baseline)"], 610)
        self.assertEqual(got["a worker behind the turn"], 610)
        self.assertGreater(got["an agent used as a tool"], 800)


class TestHandoff(unittest.TestCase):
    def test_the_specialist_owns_the_state_until_the_deadline(self):
        rec = c.hand_off(DATA["handoff"], 0)
        self.assertEqual(c.owner_at(rec, 60, None), "rebooking")
        self.assertIn("deadline", c.owner_at(rec, 90, None))

    def test_an_answer_in_time_hands_the_state_back(self):
        rec = c.hand_off(DATA["handoff"], 0)
        self.assertEqual(c.owner_at(rec, 70, 45), "triage")


class TestAdapter(unittest.TestCase):
    def test_the_adapter_speaks_before_the_agent_answers(self):
        self.assertLess(c.CACHED_START_MS, DATA["existing"]["answer_ms"])

    def test_links_are_texted_not_spoken(self):
        steps, links = c.speakable_steps(DATA["existing"]["answer"])
        self.assertEqual((steps, links), (3, 1))


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(c.report("mock").splitlines()[1:],
                         c.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
