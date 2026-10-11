"""Tests for the Chapter 8 entry lab. Run: python3 -m unittest test_entry_lab.py"""
from __future__ import annotations

import json
import unittest

import entry_lab as e

DATA = e.inputs("mock")


class TestContract(unittest.TestCase):
    def test_mu_law_round_trips_within_its_quantization(self):
        for v in (0, 100, 1000, -1000, 8000, -20000):
            self.assertLess(abs(e.ulaw_decode(e.ulaw_encode(v)) - v),
                            max(8, abs(v) // 16))

    def test_every_entry_point_delivers_the_same_contract(self):
        shapes = []
        for a in (e.SipEntry(), e.WebSocketEntry(), e.WebRtcEntry()):
            frames, keys, shape = e.summary(list(e.entry_events(a, DATA)))
            self.assertEqual((frames, keys), (100, 1))
            shapes.append(shape)
        self.assertTrue(all(s == shapes[0] for s in shapes))

    def test_sip_and_websocket_carry_identical_audio(self):
        sip = [x.data for x in e.entry_events(e.SipEntry(), DATA)
               if x.kind == "audio"]
        ws = [x.data for x in e.entry_events(e.WebSocketEntry(), DATA)
              if x.kind == "audio"]
        self.assertEqual(sip, ws)

    def test_three_end_packets_make_one_digit(self):
        ev = list(e.SipEntry().receive({}, e.rtp_packets("2")))
        self.assertEqual([x.data for x in ev if x.kind == "dtmf"], ["2"])


class TestMatrix(unittest.TestCase):
    def test_claims_without_an_adapter_are_untested(self):
        self.assertEqual(e.conformance(None, DATA), {})

    def test_live_adapters_pass_what_they_claim(self):
        ok = e.conformance(e.SipEntry(), DATA)
        self.assertEqual(len(ok), 6)
        self.assertTrue(all(ok.values()))

    def test_clear_drops_what_has_not_played(self):
        a = e.WebSocketEntry()
        a.play(1000)
        self.assertEqual(json.loads(a.clear()), {"event": "clear"})
        self.assertEqual(a.queued_ms, 0)


class TestLoss(unittest.TestCase):
    def test_udp_loses_and_tcp_delays(self):
        lost = set(DATA["lost"])
        udp = e.play_out(e.udp_arrivals(3000, lost), e.BUFFER_MS)
        tcp = e.play_out(e.tcp_arrivals(3000, lost), e.BUFFER_MS)
        self.assertAlmostEqual(udp["missing"], 0.01)
        self.assertEqual((udp["late"], tcp["missing"]), (0, 0))
        self.assertGreater(tcp["late"], udp["missing"])

    def test_tcp_delivers_in_order(self):
        arr = e.tcp_arrivals(200, {10, 50})
        self.assertEqual(arr, sorted(arr))


class TestBargeIn(unittest.TestCase):
    def test_marks_never_claim_more_than_was_heard(self):
        own = int(e.barge_in("sip", 3300)[1].split()[0])
        marks = int(e.barge_in("ws-clear", 3300)[1].split()[0])
        self.assertLessEqual(marks, own)

    def test_without_clear_the_rest_of_the_line_plays(self):
        ms, rec = e.barge_in("ws-no-clear", 3300)
        self.assertEqual(ms, e.line_ms(e.FEE_LINE) - 3300)
        self.assertIn("not heard", rec)


class TestContext(unittest.TestCase):
    def test_a_header_does_not_survive_the_second_leg(self):
        first, second = e.transfer_twice(e.FIELDS, "header")
        self.assertNotIn("last two turns", first)
        self.assertEqual(second, {})

    def test_attached_data_survives_both_transfers(self):
        first, second = e.transfer_twice(e.FIELDS, "attached")
        self.assertEqual(first, e.FIELDS)
        self.assertEqual(second, e.FIELDS)


class TestAfter(unittest.TestCase):
    def test_a_released_agent_pays_nothing(self):
        self.assertEqual(e.bridged_cost(True), (0, 0.0))
        self.assertEqual(e.bridged_cost(False), (14, 2.52))

    def test_webhooks_are_verified_and_applied_once(self):
        out = e.apply_webhooks(e.deliveries(), {"CA-0142": "c-5108"})
        self.assertIn("applied", out[0])
        self.assertIn("ignored", out[1])
        self.assertIn("refused", out[2])


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        mock = e.report("mock").splitlines()[1:]
        fixture = e.report("fixture").splitlines()[1:]
        self.assertEqual(mock, fixture)


if __name__ == "__main__":
    unittest.main()
