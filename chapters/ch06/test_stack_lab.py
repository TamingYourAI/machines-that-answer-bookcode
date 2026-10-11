"""Tests for the Chapter 6 stack lab. Run: python3 -m unittest test_stack_lab.py"""
from __future__ import annotations

import unittest

import stack_lab as s


class TestContracts(unittest.TestCase):
    def test_only_the_conforming_adapter_passes(self):
        results = {a.name: s.conformance(a) for a in s.ADAPTERS}
        self.assertEqual([n for n, f in results.items() if not f], ["hearing, stand-in A"])

    def test_an_adapter_that_cannot_be_cancelled_fails(self):
        a = s.Adapter("x", True, None, "call", "classified")
        self.assertIn("cannot be stopped in time", s.conformance(a))

    def test_every_layer_has_a_contract(self):
        self.assertEqual(len(s.CONTRACTS), 8)


class TestAttribution(unittest.TestCase):
    def test_call_clock_spans_add_up_to_the_turn(self):
        spans = s.attribute(s.TURN)
        total = s.TURN["audio leaves the server"] - s.TURN["caller stops speaking"]
        self.assertEqual(sum(ms for _, _, ms in spans), total)
        self.assertTrue(all(ms >= 0 for _, _, ms in spans))

    def test_vendor_clocks_produce_an_impossible_span(self):
        self.assertTrue(any(ms < 0 for _, _, ms in s.attribute(s.skewed(s.TURN))))


class TestTimeline(unittest.TestCase):
    def test_the_fee_was_not_heard(self):
        tl = s.timeline(s.FEE_LINE, s.BARGE_IN_MS)
        self.assertEqual(tl["heard"], ["slot"])

    def test_the_whole_line_is_heard_when_nobody_interrupts(self):
        tl = s.timeline(s.FEE_LINE, 60_000)
        self.assertEqual(tl["heard"], ["fee", "slot"])


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(s.report("mock").split("\n", 1)[1],
                         s.report("fixture").split("\n", 1)[1])

    def test_output_fits_78_columns(self):
        self.assertTrue(all(len(line) <= 78 for line in s.report("mock").splitlines()))

    def test_frozen_outputs_match(self):
        for mode in ("mock", "fixture"):
            self.assertEqual(s.report(mode),
                             (s.OUTPUTS / f"stack_lab.{mode}.out.txt").read_text())


if __name__ == "__main__":
    unittest.main()
