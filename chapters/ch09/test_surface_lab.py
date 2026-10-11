"""Tests for the Chapter 9 surface lab. Run: python3 -m unittest test_surface_lab.py"""
from __future__ import annotations

import unittest

import surface_lab as s

DATA = s.inputs("mock")
NOW = DATA["now"]


class TestTokens(unittest.TestCase):
    def test_a_fresh_token_opens_a_session_for_its_user(self):
        tok = s.mint({"account": "5108"}, NOW)
        self.assertTrue(s.open_session(tok, NOW).startswith("accepted"))
        self.assertIn("5108", s.open_session(tok, NOW))

    def test_a_late_token_is_refused(self):
        tok = s.mint({"account": "5108"}, NOW)
        late = NOW + s.START_WITHIN_S + 1
        self.assertIn("expired", s.open_session(tok, late))

    def test_edited_claims_break_the_signature(self):
        tok = s.tamper(s.mint({"account": "5108"}, NOW), "sub", "2231")
        self.assertIn("signature", s.open_session(tok, NOW))

    def test_the_token_locks_the_tools(self):
        tok = s.mint({"account": "5108"}, NOW)
        out = s.open_session(tok, NOW, {"tools": ["refund"]})
        self.assertIn("locks the tools", out)

    def test_the_scan_finds_the_prototype_key_only(self):
        self.assertEqual(s.scan(s.BUNDLES["prototype"]),
                         ["config/speech.json"])
        self.assertEqual(s.scan(s.BUNDLES["release"]), [])


class TestScreen(unittest.TestCase):
    def test_every_event_has_a_visible_state(self):
        for kind, state, _ in s.screen(s.EVENTS):
            self.assertTrue(state)

    def test_the_card_shows_what_the_voice_says(self):
        both, extra = s.agree(s.EVENTS)
        self.assertGreater(both, 0)
        self.assertEqual(extra, 0)

    def test_a_card_with_an_unspoken_fact_is_caught(self):
        bad = s.EVENTS + [{"kind": "offer", "card": "Wednesday 9:00"}]
        self.assertEqual(s.agree(bad)[1], 1)     # Wednesday was never said


class TestConfirm(unittest.TestCase):
    def test_a_tap_and_a_yes_book_once(self):
        booked = {}
        s.confirm(DATA["offer"], "tap", 2, booked)
        again = s.confirm(DATA["offer"], "voice", 2, booked)
        self.assertEqual(len(booked), 1)
        self.assertIn("repeat", again)

    def test_a_stale_card_is_refused(self):
        self.assertIn("stale", s.confirm(DATA["offer"], "tap", 1, {}))


class TestClients(unittest.TestCase):
    def test_the_kill_switch_reaches_every_version(self):
        for c in s.CLIENTS:
            self.assertNotIn("full", s.session_for(c, False))
            self.assertNotIn("voice;", s.session_for(c, False))

    def test_an_unsupported_version_is_refused_gracefully(self):
        self.assertIn("update", s.session_for({"contract": 1}, True))


class TestDevice(unittest.TestCase):
    def test_the_device_adds_to_what_the_server_measures(self):
        for d in s.DEVICES:
            self.assertGreater(s.voice_to_voice(d), s.SERVER_SPANS_MS)

    def test_bluetooth_media_crosses_the_wall(self):
        worst = max(s.voice_to_voice(d) for d in s.DEVICES)
        self.assertGreater(worst, 800)


class TestTyping(unittest.TestCase):
    def test_typed_and_spoken_reach_the_same_turn(self):
        self.assertEqual(s.turn(DATA["question"], "spoken"),
                         s.turn(DATA["question"], "typed"))


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(s.report("mock").splitlines()[1:],
                         s.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
