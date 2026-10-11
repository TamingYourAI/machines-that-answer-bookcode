"""Tests for the Chapter 7 telephony lab. Run: python3 -m unittest test_telephony_lab.py"""
from __future__ import annotations

import unittest

import telephony_lab as t


class TestInvite(unittest.TestCase):
    def test_the_invite_is_read(self):
        inv = t.parse_invite(t.INVITE)
        self.assertEqual((inv["from"], inv["attest"], inv["ptime"]),
                         ("+13125550142", "A", 20))

    def test_the_answer_picks_a_shared_codec_and_events(self):
        ans = t.answer(t.parse_invite(t.INVITE))
        self.assertEqual(ans["codec"], "PCMU/8000")
        self.assertTrue(ans["dtmf"].startswith("events"))

    def test_a_private_audio_address_is_flagged(self):
        self.assertTrue(t.answer(t.parse_invite(t.INVITE))["nat"])


class TestAudio(unittest.TestCase):
    def test_the_phone_path_removes_what_is_above_4_khz(self):
        x = t.voice()
        self.assertGreater(t.high_share(x), 0.3)
        self.assertLess(t.high_share(t.phone_path(x)), 0.01)

    def test_converting_twice_costs_quality(self):
        x = t.voice()
        ref = t.lowpass(x, 3800)
        once = t.phone_path(x)
        self.assertGreater(t.snr_db(ref, once), t.snr_db(ref, t.phone_path(once)))

    def test_a_bigger_buffer_loses_fewer_packets(self):
        d = t.network()
        shares = [t.late_share(d, b) for b in t.BUFFERS_MS]
        self.assertEqual(shares, sorted(shares, reverse=True))


class TestTouchTones(unittest.TestCase):
    def test_clean_and_g711_tones_are_detected(self):
        pkts = t.tone_packets(t.DIGITS)
        self.assertEqual(t.detect(pkts), t.DIGITS)
        self.assertEqual(t.detect(t.g711(pkts)), t.DIGITS)

    def test_a_burst_merges_two_presses_in_the_audio_but_not_as_events(self):
        lost = {3, 4, 5}
        self.assertEqual(t.detect(t.lossy(t.tone_packets(t.DIGITS), lost)), "231#")
        self.assertEqual(t.events(t.DIGITS, lost), t.DIGITS)


class TestGates(unittest.TestCase):
    def test_emergency_numbers_are_never_dialed(self):
        for n in ("911", "112", "999"):
            self.assertIn("never", t.gate({"to": n, "hour": 10, "kind": "owner"}, 0, 0))

    def test_the_hourly_limit_holds(self):
        a = {"to": "+13125551000", "hour": 14, "kind": "customer"}
        self.assertEqual(t.gate(a, t.LIMITS["per_hour"], 0), "refused: hourly limit")

    def test_an_unregistered_number_is_filtered(self):
        m = {"from": "+13125550101", "to": "+13125550142", "kind": "confirmation"}
        self.assertIn("unregistered", t.may_text(m, {"+13125550142"}, set()))


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree(self):
        self.assertEqual(t.report("mock").split("\n", 1)[1],
                         t.report("fixture").split("\n", 1)[1])

    def test_output_fits_78_columns(self):
        self.assertTrue(all(len(line) <= 78 for line in t.report("mock").splitlines()))

    def test_frozen_outputs_match(self):
        for mode in ("mock", "fixture"):
            self.assertEqual(t.report(mode),
                             (t.OUTPUTS / f"telephony_lab.{mode}.out.txt").read_text())


if __name__ == "__main__":
    unittest.main()
