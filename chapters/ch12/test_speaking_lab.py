"""Tests for the Chapter 12 speaking lab. Run: python3 -m unittest test_speaking_lab.py"""
from __future__ import annotations

import re
import unittest

import speaking_lab as s

DATA = s.inputs("mock")
TOKS = s.tokens(DATA["bill"])


class TestStreaming(unittest.TestCase):
    def test_each_chunking_starts_sooner(self):
        firsts = [s.first_audio_ms(TOKS, how) for how in s.HOWS]
        self.assertEqual(firsts, sorted(firsts, reverse=True))

    def test_streaming_starts_one_span_after_the_first_token(self):
        self.assertEqual(s.first_audio_ms(TOKS, "streamed"), s.TTFB_MS)

    def test_no_safe_chunk_ends_inside_an_amount(self):
        for how in s.HOWS:
            for _, text in s.chunks(TOKS, how):
                self.assertNotRegex(text, r"\$\d+\.?$")

    def test_a_careless_chunker_splits_the_amount(self):
        first = s.chunks(TOKS, "by clause, careless")[0][1]
        self.assertTrue(first.endswith("$184."))


class TestBuffer(unittest.TestCase):
    def test_normal_load_never_stutters(self):
        self.assertEqual(s.play(DATA["line_ms"], 0, loaded=False)[1], 0)

    def test_load_stutters_until_the_buffer_covers_it(self):
        zero, big = s.play(DATA["line_ms"], 0, True), s.play(DATA["line_ms"], 400, True)
        self.assertGreater(zero[1], 0)
        self.assertEqual(big[1], 0)
        self.assertGreater(big[0], zero[0])


class TestFormatter(unittest.TestCase):
    def test_english_words_and_ordinals(self):
        self.assertEqual(s.words(184), "one hundred eighty-four")
        self.assertEqual(s.ordinal(30), "thirtieth")

    def test_german_puts_the_units_first(self):
        self.assertEqual(s.de_words(84), "vierundachtzig")
        self.assertEqual(s.de_words(21), "einundzwanzig")

    def test_the_german_day_takes_the_sentence_case(self):
        self.assertEqual(s.de_ordinal_dative(30), "dreißigsten")
        self.assertEqual(s.de_ordinal_dative(7), "siebten")

    def test_each_locale_says_the_time_its_own_way(self):
        self.assertEqual(s.say("time", "19:40", "en-GB"), "at nineteen forty")
        self.assertIn("in the evening", s.say("time", "19:40", "en-US"))
        self.assertEqual(s.say("money", "EUR 84.50", "de-DE"), "vierundachtzig Euro fünfzig")
        self.assertEqual(s.say("money", "EUR 84.50", "en-US"),
                         "eighty-four euros and fifty cents")


class TestLexicon(unittest.TestCase):
    def test_one_entry_three_forms(self):
        entry = DATA["lexicon"]["Alder"]
        self.assertIn(entry["x-sampa"], s.compile_lexicon("Alder", entry, "takes phoneme tags"))
        self.assertEqual(s.compile_lexicon("Alder", entry, "takes plain text only"), "AL-der")


class TestSpeakable(unittest.TestCase):
    def test_nothing_unspeakable_reaches_the_voice(self):
        said, found = s.speakable(DATA["model_text"])
        self.assertNotRegex(said, r"https?://|\*\*|\d")
        self.assertIn("a link (never read aloud; sent by text)", found)

    def test_at_most_three_options_are_spoken(self):
        said, _ = s.speakable(DATA["model_text"])
        self.assertNotIn("Saturday", said)
        self.assertIn("I'll text you the full list.", said)

    def test_a_long_turn_is_flagged_not_cut(self):
        said, found = s.speakable(DATA["model_text"])
        self.assertIn("sixty dollars", said)
        self.assertTrue(any("design finding" in f for f in found))


class TestPanel(unittest.TestCase):
    def test_the_update_sounds_better_and_is_heard_worse(self):
        pinned, updated = DATA["panel"].values()
        mos = [s.mean_ci([x for row in p["scores"] for x in row])[0] for p in (pinned, updated)]
        heard = [sum(map(sum, p["heard"])) / 32 for p in (pinned, updated)]
        self.assertGreater(mos[1], mos[0])
        self.assertGreaterEqual(heard[0], DATA["line"])
        self.assertLess(heard[1], DATA["line"])


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(s.report("mock").splitlines()[1:],
                         s.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
