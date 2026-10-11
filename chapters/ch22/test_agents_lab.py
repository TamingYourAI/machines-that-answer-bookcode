"""Tests for the Chapter 22 lab. Run: python3 -m unittest test_agents_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import agents_lab as lab

DATA = lab.inputs("fixture")


class Kinds(unittest.TestCase):
    def test_a_synthetic_sounding_voice_is_still_a_person(self):
        caller = next(c for c in DATA["callers"] if "text-to-speech" in c["who"])
        self.assertEqual(lab.kind(caller), "a person")

    def test_an_assistant_without_a_delegation_gets_no_account_data(self):
        caller = {"who": "x", "says_automated": True}
        self.assertIn("office details only", lab.POLICY[lab.kind(caller)])

    def test_a_partner_agent_is_sent_to_the_structured_door(self):
        self.assertEqual(lab.kind({"channel": "agent protocol"}), "a partner's agent")


class Delegation(unittest.TestCase):
    def setUp(self):
        self.d = DATA["delegation"]

    def check(self, action="move_visit", account="7305", agent="assistant.example",
              at=18 * 60 + 41, revoked=()):
        return lab.check_delegation(self.d, agent, action, account, at, set(revoked))

    def test_a_move_inside_the_scope_is_allowed_and_bound(self):
        ok, why = self.check()
        self.assertTrue(ok)
        self.assertIn("d-7305-1", why)

    def test_an_assistant_never_pays(self):
        self.assertFalse(self.check(action="pay")[0])

    def test_another_account_is_refused(self):
        self.assertFalse(self.check(account="7306")[0])

    def test_another_agent_is_refused(self):
        self.assertFalse(self.check(agent="other-assistant.example")[0])

    def test_it_ends_on_time(self):
        self.assertFalse(self.check(at=19 * 60 + 5)[0])

    def test_the_customer_can_revoke_it(self):
        self.assertIn("revoked", self.check(revoked={"d-7305-1"})[1])


class Holds(unittest.TestCase):
    def setUp(self):
        self.m = DATA["market"]
        self.reqs = lab.market_requests(self.m)

    def test_a_per_call_limit_lets_one_platform_hold_everything(self):
        r = lab.holds(self.reqs, self.m["slots"], self.m["minutes"], self.m["hold_min"], None)
        self.assertGreater(r["blocked"], self.m["minutes"] // 2)

    def test_caps_per_principal_and_platform_keep_slots_open(self):
        r = lab.holds(self.reqs, self.m["slots"], self.m["minutes"], self.m["hold_min"],
                      self.m["caps"])
        self.assertEqual(r["blocked"], 0)


class Tasks(unittest.TestCase):
    def test_a_completed_task_is_committed_and_the_promise_kept(self):
        lines = lab.follow(DATA["tasks"][0], DATA["promise_by"], DATA["fallback_at"])
        self.assertTrue(lines[-1][2].startswith("promise kept"))

    def test_a_silent_partner_still_gets_the_passenger_a_person_in_time(self):
        lines = lab.follow(DATA["tasks"][1], DATA["promise_by"], DATA["fallback_at"])
        at, _, text = lines[-1]
        self.assertIn("a person calls", text)
        self.assertLess(at, DATA["promise_by"])


class Modes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        strip = lambda t: t.split("\n", 1)[1]
        self.assertEqual(strip(lab.report("mock")), strip(lab.report("fixture")))

    def test_output_fits_78_columns(self):
        for line in lab.report("mock").splitlines():
            self.assertLessEqual(len(line), 78, line)

    def test_frozen_output(self):
        for mode in ("mock", "fixture"):
            frozen = (lab.OUTPUTS / f"agents_lab.{mode}.out.txt").read_text()
            self.assertEqual(lab.report(mode), frozen)


if __name__ == "__main__":
    unittest.main()
