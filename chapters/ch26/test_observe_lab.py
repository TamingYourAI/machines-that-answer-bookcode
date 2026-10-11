"""Tests for the Chapter 26 lab. Run: python3 -m unittest test_observe_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import observe_lab as lab

DATA = lab.inputs("fixture")
CALL = DATA["bad_call"]
NEW = lab.promote(CALL)


class TheBadCall(unittest.TestCase):
    def test_the_turn_ended_while_she_was_still_speaking(self):
        r = lab.play(CALL["answer"], "v2.3")
        self.assertTrue(r["cut_off"])
        self.assertEqual(r["wait"], 200)


class NameTheLayer(unittest.TestCase):
    def test_the_taxonomy_names_turn_taking(self):
        layer, _, _ = lab.name_layer(CALL)
        self.assertEqual(layer, "turn-taking")

    def test_the_first_match_wins_in_a_fixed_order(self):
        order = [layer for layer, _ in lab.TAXONOMY]
        self.assertLess(order.index("hearing"), order.index("turn-taking"))

    def test_a_gap_no_layer_owns_is_named_orchestration_and_only_last(self):
        self.assertEqual(lab.first_match({"orchestration": True})[0],
                         "orchestration")
        self.assertEqual(lab.first_match({"hearing": True,
                                          "orchestration": True})[0],
                         "hearing")


class PromoteIt(unittest.TestCase):
    def test_the_scenario_carries_no_personal_data(self):
        text = str(NEW)
        self.assertNotIn(CALL["account"], text)

    def test_the_scenario_keeps_the_words_and_the_pause(self):
        self.assertEqual(NEW["caller"], CALL["answer"])


class TheSuiteCatchesIt(unittest.TestCase):
    def test_the_new_scenario_fails_before_the_fix_and_passes_after(self):
        self.assertFalse(lab.run_scenario(NEW, "v2.3")[0])
        self.assertTrue(lab.run_scenario(NEW, "v2.4")[0])

    def test_no_older_scenario_breaks(self):
        for sc in DATA["suite"]:
            for rules in ("v2.3", "v2.4"):
                self.assertTrue(lab.run_scenario(sc, rules)[0], sc["id"])

    def test_plain_answers_still_end_at_200_ms(self):
        for sc in DATA["suite"]:
            if sc["expect"].get("max_wait") == 200:
                self.assertEqual(lab.play(sc["caller"], "v2.4")["wait"], 200)

    def test_a_refused_slot_alone_waits_longer_after_the_fix(self):
        self.assertEqual(lab.wait_ms("not tuesday", "v2.4"), 1000)
        self.assertEqual(lab.wait_ms("not tuesday", "v2.3"), 200)


class TheWeeksReview(unittest.TestCase):
    def test_every_flagged_call_named_a_known_layer(self):
        layers = {layer for layer, _ in lab.TAXONOMY}
        for layer, _ in DATA["week"]:
            self.assertIn(layer, layers)

    def test_one_promotion_took_longer_than_a_week(self):
        self.assertEqual(sum(d > 7 for _, d in DATA["week"]), 1)


class TheReport(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").split("\n", 1)[1],
                         lab.report("fixture").split("\n", 1)[1])

    def test_every_line_fits_the_page(self):
        for line in lab.report("fixture").splitlines():
            self.assertLessEqual(len(line), 78, line)


if __name__ == "__main__":
    unittest.main()
