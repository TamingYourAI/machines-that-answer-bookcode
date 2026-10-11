"""Tests for the Chapter 2 lab. Run: python3 -m unittest test_seat_lab.py

One claim from the chapter per test.
"""
from __future__ import annotations

import unittest

import seat_lab as lab


def seat(name):
    return next(s for s in lab.SEATS if s.name == name)


class Seats(unittest.TestCase):
    def test_front_of_the_acd_meets_the_service_lines_needs(self):
        self.assertTrue(all(ok for _, ok in lab.evaluate(seat("front of the ACD"))))

    def test_overlay_gives_up_interruptions_and_audio(self):
        failed = [label for label, ok in lab.evaluate(seat("overlay")) if not ok]
        self.assertEqual(failed, ["controls interruptions", "hears the caller's own audio"])

    def test_cpaas_native_is_a_different_business(self):
        self.assertEqual(seat("CPaaS-native").number, "you")
        self.assertFalse(seat("CPaaS-native").attached_data)


class Checker(unittest.TestCase):
    def setUp(self):
        self.sound, self.mixed = lab.load_designs("fixture")

    def test_the_sound_design_passes(self):
        self.assertEqual(lab.check_design(self.sound), [])

    def test_a_mixed_seat_breaks_six_contracts(self):
        self.assertEqual(len(lab.check_design(self.mixed)), 6)

    def test_a_second_recording_is_caught(self):
        self.assertTrue(any("second recording" in p for p in lab.check_design(self.mixed)))

    def test_every_screen_pop_field_is_required(self):
        d = lab.sound_design()
        d["transfer"]["attached"] = d["transfer"]["attached"][:-1]
        self.assertEqual(len(lab.check_design(d)), 1)


class OneCall(unittest.TestCase):
    def setUp(self):
        self.sound, self.mixed = lab.load_designs("fixture")
        self.call = lab.load_call("fixture")

    def test_the_sound_design_keeps_every_step_the_seat_owns(self):
        self.assertEqual(lab.kept(self.sound, self.call), (7, 7))

    def test_a_mixed_seat_breaks_five_of_them(self):
        self.assertEqual(lab.kept(self.mixed, self.call), (2, 7))


class Modes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(lab.report("mock").splitlines()[1:], lab.report("fixture").splitlines()[1:])

    def test_frozen_output(self):
        for mode in ("mock", "fixture"):
            frozen = (lab.OUTPUTS / f"seat_lab.{mode}.out.txt").read_text()
            self.assertEqual(lab.report(mode), frozen)


if __name__ == "__main__":
    unittest.main()
