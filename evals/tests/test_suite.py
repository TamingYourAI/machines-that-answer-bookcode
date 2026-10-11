"""The suite's tests: its statistics, its scenarios, its checks, its line conditions, and one text
run against the companion app on a fixed clock."""
from __future__ import annotations

import asyncio
import datetime as dt
import socket
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from voice_eval import conditions, records
from voice_eval.checks import Ctx, family_verdict, run_checks
from voice_eval.report import summarize
from voice_eval.scenarios import Caller, Scenario, load
from voice_eval.stats import percentile, wilson

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


# ------------------------------------------------------------------ statistics

def test_wilson_is_honest_near_the_ends():
    lo, hi = wilson(20, 20)
    assert hi == 1.0 and 0.83 < lo < 0.85          # twenty clean runs still allow ~16 percent
    lo, hi = wilson(0, 20)
    assert lo == 0.0 and 0.16 < hi < 0.17
    lo, hi = wilson(10, 20)
    assert 0.29 < lo < 0.31 and 0.69 < hi < 0.71


def test_percentile_is_a_real_value():
    assert percentile([100, 200, 300, 400], 95) == 400
    assert percentile([], 95) is None


# ------------------------------------------------------------------ scenarios

def test_every_shipped_scenario_passes_the_books_validator():
    scs = load([SCENARIOS])
    assert len(scs) >= 8
    assert [s.id for s in scs if s.problems] == []


def test_a_pause_inside_a_turn_keeps_the_turn_open():
    sc = Scenario({"caller": {"lines": [["Twelve", 500, 700], ["Maple Street.", 900, 0],
                                        ["Jordan.", 600, 0]]}})
    turns = sc.turns()
    assert [t.text for t in turns] == ["Twelve Maple Street.", "Jordan."]
    assert turns[0].pieces[0][2] == 700


def test_the_caller_answers_the_question_asked():
    sc = Scenario({"caller": {"lines": [["My drain is blocked.", 1000, 0]],
                              "answers": [["address", "12 Maple Street."], ["name", "Jordan."],
                                          ["shall i book", "No."], ["shall i book", "Yes."]]}})
    c = Caller(sc)
    assert c.reply(["How can I help?"]).text == "My drain is blocked."
    assert c.reply(["Thanks.", "And your name?"]).text == "Jordan."
    assert c.reply(["What's the address?"]).text == "12 Maple Street."
    assert c.reply(["What's the address?"]).text == "12 Maple Street."   # asked again
    assert c.reply(["Shall I book it?"]).text == "No."
    assert c.reply(["Shall I book it?"]).text == "Yes."
    assert c.reply(["Anything else?"]) is None


# ------------------------------------------------------------------ checks

def record(turns, ops=(), outcome="", messages=()):
    return {"call": {"id": "c", "outcome": outcome},
            "turns": [{"who": w, "text": x, "speech": "", "t": t, "terms": []}
                      for w, x, t in turns],
            "operations": list(ops), "messages": list(messages)}


BOOK = {"tool": "book_visit", "state": "committed", "terms": {}, "created_at": 9.0,
        "updated_at": 10.0}


def test_the_fee_before_the_yes_and_booked_after_the_commit():
    good = record([("agent", "Shall I book it? There's a $60 call-out charge.", 8.0),
                   ("caller", "Yes.", 9.0), ("agent", "You're booked for Wednesday.", 10.5)],
                  [BOOK])
    res = run_checks({"booked": "wednesday", "fee_before_yes": True,
                      "confirmed_after_commit": True}, Ctx(good, "text", {}, []))
    assert all(r["passed"] for r in res)


def test_booked_before_the_commit_is_caught():
    early = record([("agent", "Shall I book it? It's $60.", 8.0), ("caller", "Yes.", 9.0),
                    ("agent", "You're booked for Wednesday.", 9.5)], [BOOK])
    res = run_checks({"confirmed_after_commit": True}, Ctx(early, "text", {}, []))
    assert res[0]["passed"] is False
    told = record([("agent", "You're booked for Wednesday.", 9.5)])
    res = run_checks({"confirmed_after_commit": True}, Ctx(told, "text", {}, []))
    assert res[0]["passed"] is False and "without a booking" in res[0]["detail"]


def test_a_loop_is_counted_in_turns():
    loop = record([("caller", "No.", 1), ("agent", "Shall I book Thursday?", 2),
                   ("caller", "No.", 3), ("agent", "Shall I book Thursday?", 4),
                   ("caller", "No.", 5), ("agent", "Shall I book Thursday?", 6)])
    res = run_checks({"same_turn_max": 2}, Ctx(loop, "text", {}, []))
    assert res[0]["passed"] is False and "3 time(s)" in res[0]["detail"]


def test_a_turn_recorded_as_two_is_a_cut_off():
    split = record([("caller", "12.", 1), ("agent", "And your name?", 2),
                    ("caller", "Maple Street.", 3)])
    res = run_checks({"cut_off": False}, Ctx(split, "audio", {"cut_offs": 0}, [], spoken=1))
    assert res[0]["passed"] is False
    whole = record([("caller", "12 Maple Street.", 1)])
    res = run_checks({"cut_off": False}, Ctx(whole, "audio", {"cut_offs": 0}, [], spoken=1))
    assert res[0]["passed"] is True


def test_audio_checks_do_not_count_against_a_text_run():
    res = run_checks({"turns_max": 5, "gap_p95_ms_max": 800},
                     Ctx(record([("caller", "Hi.", 1)]), "text", {}, []))
    assert family_verdict(res, "experience") is True
    assert res[1]["applies"] is False


def test_an_unknown_key_is_never_a_pass():
    res = run_checks({"made_up": True}, Ctx(record([]), "text", {}, []))
    assert res[0]["passed"] is None and res[0]["family"] == "unknown"


def test_too_few_runs_are_not_judged():
    sc = Scenario({"id": "x", "title": "t", "line": "river plumbing", "conditions": {},
                   "runs": {"n": 20, "pass": "all"}})
    ok = {"checks": [{"key": "booked", "family": "task", "passed": True}], "error": ""}
    assert summarize(sc, [ok] * 3)["met_rule"] is None
    assert summarize(sc, [ok] * 20)["met_rule"] is True


# ------------------------------------------------------------------ the line's conditions

def test_the_phone_codec_noise_and_loss():
    rng = np.random.default_rng(1)
    t = np.arange(16000) / 16000
    pcm = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16).tobytes()
    coded = conditions.apply(pcm, {"codec": "g711"}, rng)
    assert len(coded) == len(pcm) and coded != pcm
    assert conditions.snr_db({"noise": "quiet"}) is None
    assert conditions.snr_db({"noise": "a loud street"}) == 10.0
    assert conditions.snr_db({"noise": "speakerphone in a kitchen"}) == 15.0
    lost = np.frombuffer(conditions.apply(pcm, {"loss": 1.0}, rng), dtype=np.int16)
    assert not lost.any()
    assert conditions.background(100, {"noise": "quiet"}, rng) == bytes(3200)


# ------------------------------------------------------------------ one run against the app

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def app_url(tmp_path):
    uvicorn = pytest.importorskip("uvicorn")
    from ova.providers import Providers
    from ova.runtime import Clock
    from ova.store import Store
    from ova_server.app import build_runtime, create_app
    from ova_server.settings import Settings
    monday = dt.datetime(2026, 9, 28, 10, 15)
    settings = Settings(data_dir=tmp_path, secret="test-secret", public_url="http://ova.test")
    providers = Providers()
    rt = build_runtime(settings, providers, store=Store(), clock=Clock(fixed=monday))
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(settings, providers, rt),
                                           host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    th.join(timeout=5)


def test_the_text_runner_books_a_visit_on_the_companion_app(app_url):
    from voice_eval.runners import text
    sc = load([SCENARIOS / "river-plumbing" / "or-01-book-a-visit.json"])[0]
    res = asyncio.run(text.run(app_url, sc))
    assert res.error == "" and res.call_id
    rec = records.from_ova(app_url, res.call_id, "", res.say_terms)
    checks = run_checks(sc.data["expect"], Ctx(rec, "text", res.measures, res.events,
                                               len(res.caller_turns)))
    assert family_verdict(checks, "task") is True, checks
    assert family_verdict(checks, "experience") is True, checks
