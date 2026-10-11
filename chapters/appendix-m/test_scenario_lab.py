"""Tests for the Appendices M and Q lab. Run:
python3 -m unittest test_scenario_lab.py

One claim from the appendices per test. Two tests read the Chapter 26 and
Interlude B labs, so the catalogue cannot drift from the chapters.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

import scenario_lab as lab

DATA = lab.inputs("fixture")
ALL = DATA["catalogue"] + DATA["acceptance"]
BY_ID = {(s["line"], s["id"]): s for s in ALL}
TT17 = BY_ID[("service line", "tt-17")]
BUILDERS = Path(__file__).resolve().parent.parent


def changed(**change) -> dict:
    s = copy.deepcopy(TT17)
    s.update(change)
    return s


class TheFormat(unittest.TestCase):
    def test_every_catalogue_scenario_is_valid(self):
        for s in ALL:
            self.assertEqual(lab.validate(s), [], s["id"])

    def test_ids_are_unique_within_each_business(self):
        self.assertEqual(lab.check_library(ALL), [])
        twice = ALL + [copy.deepcopy(TT17)]
        self.assertEqual(lab.check_library(twice),
                         ["service line: id tt-17 used twice"])

    def test_the_printed_example_is_the_catalogues_tt_17(self):
        path = lab.FIXTURES / "tt-17.json"
        self.assertEqual(json.loads(path.read_text()), TT17)

    def test_a_missing_field_is_named(self):
        s = copy.deepcopy(TT17)
        del s["runs"]
        self.assertEqual(lab.validate(s), ["runs: required"])


class TheValidator(unittest.TestCase):
    def test_a_scenario_without_assertions_is_refused(self):
        self.assertIn("expect: at least one assertion",
                      lab.validate(changed(expect={})))

    def test_a_call_id_is_never_a_source(self):
        bad = changed(source={"kind": "failure", "ref": "call c-8124-1"})
        self.assertTrue(any("call id" in p for p in lab.validate(bad)))

    def test_the_prefix_follows_the_layer(self):
        self.assertIn("id: he-17 does not match its layer",
                      lab.validate(changed(id="he-17")))

    def test_the_phone_runner_needs_the_phone_surface(self):
        bad = changed(conditions={"noise": "quiet", "surface": "app"})
        self.assertIn("runners: the phone runner needs the phone surface",
                      lab.validate(bad))


class TheChaptersAgree(unittest.TestCase):
    def test_tt_17_is_chapter_26s_promoted_scenario(self):
        sys.path.insert(0, str(BUILDERS / "ch26"))
        import observe_lab
        promoted = observe_lab.promote(observe_lab.BAD_CALL)
        self.assertEqual(TT17["caller"]["lines"], promoted["caller"])
        self.assertEqual(TT17["expect"], promoted["expect"])
        self.assertIn(promoted["from"], TT17["source"]["ref"])
        self.assertEqual(TT17["layer"], promoted["layer"])
        library = {s["id"]: s for s in observe_lab.SUITE}
        for sid in ("tt-05", "tt-14"):
            mine = BY_ID[("service line", sid)]
            self.assertEqual(mine["caller"]["lines"], library[sid]["caller"])

    def test_the_acceptance_scenarios_match_interlude_bs_slice(self):
        path = BUILDERS / "interlude-b" / "fixtures" / "slice.json"
        slice_ = json.loads(path.read_text())
        aq1 = BY_ID[("service line", "aq-1")]["before"]
        self.assertEqual(aq1["line"], slice_["booking_line"]["text"])
        ends = {t["term"]: t["ends_ms"]
                for t in slice_["booking_line"]["terms"]}
        self.assertEqual(aq1["terms_end_ms"], ends)
        self.assertEqual(aq1["cut_in_ms"], slice_["cut_ms"])
        self.assertEqual(aq1["marks_every_ms"], slice_["marks_every"])
        aq4 = BY_ID[("service line", "aq-4")]["before"]
        self.assertEqual(aq4["amount"], slice_["bills"]["5108"]["sep"])

    def test_one_acceptance_scenario_per_guard(self):
        ids = [s["id"] for s in DATA["acceptance"]]
        self.assertEqual(ids, ["aq-1", "aq-2", "aq-3", "aq-4"])
        self.assertEqual(len(set(lab.GUARDS.values())), 4)


class Output(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        mock = lab.report("mock").split("\n", 1)[1]
        fixture = lab.report("fixture").split("\n", 1)[1]
        self.assertEqual(mock, fixture)

    def test_output_fits_78_columns(self):
        for line in lab.report("fixture").splitlines():
            self.assertLessEqual(len(line), 78, line)

    def test_frozen_output(self):
        for mode in ("mock", "fixture"):
            frozen = (lab.OUTPUTS / f"scenario_lab.{mode}.out.txt").read_text()
            self.assertEqual(lab.report(mode), frozen)


if __name__ == "__main__":
    unittest.main()
