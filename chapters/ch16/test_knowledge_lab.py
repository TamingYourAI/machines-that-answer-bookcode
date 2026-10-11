"""Tests for the Chapter 16 knowledge lab. Run: python3 -m unittest test_knowledge_lab.py"""
from __future__ import annotations

import unittest
from datetime import date

import knowledge_lab as k

DATA = k.inputs("mock")
ITEMS = DATA["items"]
ON = date.fromisoformat(DATA["asked_on"])
AFTER = date.fromisoformat(DATA["day_after"])
CALLER = DATA["caller"]


def item(i):
    return next(it for it in ITEMS if it["id"] == i)


class TestCompiledSteps(unittest.TestCase):
    def test_every_step_names_its_tools_and_its_checks(self):
        text = k.instruction(DATA["steps"][2])
        self.assertIn("outage_status", text)
        self.assertIn("account found", text)

    def test_the_outage_check_comes_before_the_ticket(self):
        ids = [st["id"] for st in DATA["steps"]]
        self.assertLess(ids.index("2a"), ids.index("3"))


class TestEvidence(unittest.TestCase):
    def test_another_callers_record_is_never_evidence(self):
        s = k.settle(DATA["question"], ITEMS, CALLER, ON)
        self.assertIn("acct-7719", [it["id"] for it in s["found"]])
        self.assertFalse(k.allowed(item("acct-7719"), CALLER))
        self.assertEqual(s["record"]["id"], CALLER)

    def test_the_policy_memo_outranks_the_web_page(self):
        s = k.settle(DATA["question"], ITEMS, CALLER, ON)
        self.assertEqual(s["winner"]["id"], "memo-114")
        self.assertEqual([it["id"] for it in s["flagged"]], ["web-storm-page"])

    def test_the_naive_best_match_is_the_page(self):
        self.assertEqual(k.search(DATA["question"], ITEMS)[0]["id"], "web-storm-page")

    def test_precedence_stays_within_a_topic(self):
        s = k.settle("What is the call-out fee for a technician visit?", ITEMS, CALLER, ON)
        self.assertEqual(s["winner"]["id"], "price-list")

    def test_an_item_without_an_owner_is_never_spoken(self):
        orphan = dict(item("price-list"), owner=None)
        self.assertEqual(k.valid(orphan, ON), "no owner")


class TestRendering(unittest.TestCase):
    def test_the_answer_keeps_its_exception_in_two_short_sentences(self):
        line = k.render(k.settle(DATA["question"], ITEMS, CALLER, ON))
        c = k.checks(line, DATA["terms"])
        self.assertEqual(c["lost"], [])
        self.assertLessEqual(c["sentences"], 2)
        self.assertLessEqual(c["longest"], 20)

    def test_the_memo_as_written_fails_the_ear(self):
        self.assertGreater(len(item("memo-114")["text"].split()), 20)


class TestFreshness(unittest.TestCase):
    def test_an_ended_policy_is_not_spoken(self):
        self.assertIn("ended", k.valid(item("memo-114"), AFTER))

    def test_a_derived_page_ends_with_its_source(self):
        self.assertIsNone(k.valid(item("web-storm-page"), ON, ITEMS))
        self.assertIn("its source", k.valid(item("web-storm-page"), AFTER, ITEMS))

    def test_the_day_after_says_it_ended(self):
        s = k.settle(DATA["question"], ITEMS, CALLER, AFTER)
        self.assertIn("ended on 30 September", k.after_the_end(s, ITEMS, AFTER))


class TestAbstaining(unittest.TestCase):
    def test_uncovered_questions_abstain_and_covered_ones_answer(self):
        got = [k.answer_or_abstain(q, ITEMS, CALLER, ON, DATA["floor"]) for q in DATA["others"]]
        self.assertEqual(got, ["price-list", "billing-guide", "abstain", "abstain"])


class TestLongCall(unittest.TestCase):
    def test_a_summary_keeps_the_context_flat(self):
        lc = DATA["long_call"]
        whole, kept = k.context_tokens(lc["turns"], lc["per_turn"], lc["keep"], lc["summary"])
        self.assertLess(kept, whole / 10)


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(k.report("mock").splitlines()[1:], k.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
