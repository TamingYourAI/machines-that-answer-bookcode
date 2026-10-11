"""Tests for the Chapter 27 lab. Run: python3 -m unittest test_deploy_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import deploy_lab as lab

DATA = lab.inputs("fixture")
M31 = lab.manifest(DATA["parts"], 31, DATA["settings"])
M32 = lab.manifest(DATA["parts"], 32, DATA["settings"])
IDS = {31: M31["id"], 32: M32["id"]}


class TheManifest(unittest.TestCase):
    def test_a_changed_part_changes_the_id(self):
        self.assertNotEqual(M31["id"], M32["id"])

    def test_the_same_parts_in_another_order_give_the_same_id(self):
        again = lab.manifest(list(reversed(DATA["parts"])), 32,
                             DATA["settings"])
        self.assertEqual(again["id"], M32["id"])

    def test_production_differs_by_one_hand_edit(self):
        diffs = lab.drift(M32, DATA["environments"]["production"])
        self.assertEqual(diffs, [("voice speaking rate", "1.1", "1.0")])

    def test_endpoints_keys_and_region_may_differ(self):
        self.assertEqual(lab.drift(M32, DATA["environments"]["staging"]), [])


class Shadow(unittest.TestCase):
    def test_by_a_flag_the_tool_that_never_checks_it_writes(self):
        out = lab.run_shadow(DATA["shadow"]["proposed"], at_tool_layer=False)
        self.assertEqual(out["reached"], {"send_receipt": 72})

    def test_at_the_tool_layer_no_write_leaves(self):
        out = lab.run_shadow(DATA["shadow"]["proposed"], at_tool_layer=True)
        self.assertEqual(out["reached"], {})

    def test_refused_writes_are_counted_by_tool(self):
        out = lab.run_shadow(DATA["shadow"]["proposed"], at_tool_layer=True)
        self.assertEqual(sum(out["refused"].values()), 148)

    def test_reads_still_run_in_shadow(self):
        out = lab.run_shadow(DATA["shadow"]["proposed"], at_tool_layer=True)
        self.assertEqual(out["read"]["lookup_account"], 598)


class TheGate(unittest.TestCase):
    def test_evidence_for_another_manifest_does_not_count(self):
        rows = lab.gate(DATA["evidence"], M32["id"], IDS)
        self.assertEqual([r[0] for r in rows if r[4] != "ok"],
                         ["phone: 40 test calls"])

    def test_stale_evidence_does_not_count(self):
        old = [["text: 200 scenarios", 32, 9, "200 of 200", True]]
        self.assertEqual(lab.gate(old, M32["id"], IDS)[0][4], "stale")


class TheCanary(unittest.TestCase):
    def test_all_callers_continue_while_the_second_language_stops(self):
        verdicts = {r[0]: r[7] for r in lab.judge(DATA["canary"]["groups"])}
        self.assertEqual(verdicts, {"all callers": "continue",
                                    "first language": "continue",
                                    "second language": "STOP"})


class Drain(unittest.TestCase):
    def test_restarting_changes_every_call_in_progress(self):
        self.assertEqual(lab.swap(DATA["in_progress"], "restart")
                         ["changed_mid_call"], 14)

    def test_draining_changes_none_and_ends_with_the_last_call(self):
        d = lab.swap(DATA["in_progress"], "drain")
        self.assertEqual(d["changed_mid_call"], 0)
        self.assertEqual(lab.clock(d["old_stops"]), "14:11:20")


class TheReport(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").split("\n", 1)[1],
                         lab.report("fixture").split("\n", 1)[1])

    def test_every_line_fits_the_page(self):
        for line in lab.report("fixture").splitlines():
            self.assertLessEqual(len(line), 78, line)


class TheEmergencyStop(unittest.TestCase):
    def setUp(self):
        self.calls = DATA["stop"]["calls"]

    def test_a_drain_lets_a_harmful_release_keep_harming(self):
        self.assertEqual(lab.stop_paths(self.calls, "drain")["harm_after"], 4)

    def test_the_emergency_stop_refuses_the_action_at_once(self):
        em = lab.stop_paths(self.calls, "stop")
        self.assertEqual(em["harm_after"], 0)
        self.assertEqual(em["moved"], 4)

    def test_writes_in_flight_are_read_back_never_assumed_cancelled(self):
        em = lab.stop_paths(self.calls, "stop")
        self.assertEqual((em["in_flight"], em["landed"]), (2, 1))

    def test_neither_path_changes_a_call_mid_call(self):
        for path in ("drain", "stop"):
            self.assertEqual(
                lab.stop_paths(self.calls, path)["changed_mid_call"], 0)


if __name__ == "__main__":
    unittest.main()
