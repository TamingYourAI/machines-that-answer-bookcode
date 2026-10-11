"""Tests for the Chapter 15 model lab. Run: python3 -m unittest test_model_lab.py"""
from __future__ import annotations

import json
import random
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import model_lab as m

DATA = m.inputs("mock")
T = m.ttft_table(DATA)


class TestTimeToFirstToken(unittest.TestCase):
    def p95(self, model, cached, load):
        return m.pct(T[(model, cached, load)], 95)

    def test_load_stretches_the_tail_more_than_the_middle(self):
        xs, ys = T[("large", True, "quiet")], T[("large", True, "storm")]
        self.assertGreater(m.pct(ys, 95) - m.pct(xs, 95), m.pct(ys, 50) - m.pct(xs, 50))

    def test_a_cached_prefix_starts_sooner(self):
        for model in DATA["models"]:
            self.assertLess(self.p95(model, True, "evening"), self.p95(model, False, "evening"))

    def test_the_published_figure_flatters_every_model(self):
        for name, model in DATA["models"].items():
            self.assertLess(model["base_ms"], m.pct(T[(name, True, "quiet")], 50))

    def test_one_request_is_one_sample(self):
        rng = random.Random(1)
        x = m.ttft(DATA["models"]["small"], DATA["prompt"], True, 0, rng)
        self.assertGreater(x, 0)


class TestPlacement(unittest.TestCase):
    def test_only_the_small_model_meets_the_wall_on_the_turn(self):
        small = m.voice_to_voice(DATA, "small", "evening", seed=2)
        large = m.voice_to_voice(DATA, "large", "evening", seed=2)
        self.assertLessEqual(m.pct(small, 95), m.WALL_MS)
        self.assertGreater(m.pct(large, 95), m.WALL_MS)

    def test_the_summary_waits_seconds_not_the_caller(self):
        self.assertGreater(m.summary_ready_s(DATA), 1.0)


class TestToolCalls(unittest.TestCase):
    def test_pass_k_is_never_above_pass_1(self):
        for model in DATA["models"]:
            r = m.pass_k(DATA, model)
            self.assertLessEqual(r["passk"], r["pass1"])

    def test_the_expected_pass_8_comes_from_the_rates(self):
        r = m.pass_k(DATA, "small")
        want = sum(sc["small"] ** 8 for sc in DATA["scenarios"]) / len(DATA["scenarios"])
        self.assertAlmostEqual(r["expected"], want)


class TestCanary(unittest.TestCase):
    def stats(self, ttft95, v2v95, pass8=0.8, first=0.9, second=0.9, refused=0.001):
        return {"ttft95": ttft95, "v2v95": v2v95, "pass8": pass8,
                "right": {"first": first, "second": second}, "refused": refused}

    def test_a_better_but_slower_model_is_stopped(self):
        rows = m.canary(DATA, self.stats(300, 740), self.stats(1300, 1600, pass8=0.95))
        self.assertFalse(all(ok for *_, ok, _ in rows))

    def test_a_faster_model_that_answers_worse_in_one_language_is_stopped(self):
        rows = m.canary(DATA, self.stats(300, 740), self.stats(250, 700, second=0.8))
        failed = [gate for gate, _, _, ok, _ in rows if not ok]
        self.assertEqual(failed, ["billing answers, second language"])


class TestLadder(unittest.TestCase):
    def test_every_turn_ends_somewhere(self):
        c = m.ladder(DATA)
        self.assertEqual(sum(c.values()), DATA["ladder"]["turns"])

    def test_a_rate_limit_sends_turns_down_the_ladder(self):
        calm = dict(DATA, ladder=dict(DATA["ladder"], rate_limited_min=0))
        self.assertLess(m.ladder(calm)["fallback"], m.ladder(DATA)["fallback"])


class TestCost(unittest.TestCase):
    def test_a_cached_prefix_cuts_the_bill_not_the_tokens(self):
        for model in DATA["models"]:
            a, b = m.call_cost(DATA, model, False), m.call_cost(DATA, model, True)
            self.assertEqual(a["input"], b["input"])
            self.assertLess(b["dollars"], a["dollars"])

    def test_the_model_is_a_small_share_of_the_business_case(self):
        self.assertLess(m.call_cost(DATA, "small", True)["dollars"], 0.05 * DATA["case_per_call"])


class _Stream(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for chunk in ({"choices": [{"delta": {"role": "assistant"}}]},
                      {"choices": [{"delta": {"content": "Tuesday"}}]}):
            time.sleep(0.03)
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args):
        pass


class TestLiveProbe(unittest.TestCase):
    def test_the_probe_stops_the_clock_at_the_first_answer_text(self):
        server = HTTPServer(("127.0.0.1", 0), _Stream)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
            xs = m.probe(url, "test", "stand-in", [{"role": "user", "content": "hi"}],
                         n=4, concurrency=2)
        finally:
            server.shutdown()
        self.assertEqual(len(xs), 4)
        self.assertTrue(all(50 <= x < 2000 for x in xs))


class TestModes(unittest.TestCase):
    def test_mock_and_fixture_agree_apart_from_the_header(self):
        self.assertEqual(m.report("mock").splitlines()[1:], m.report("fixture").splitlines()[1:])


if __name__ == "__main__":
    unittest.main()
