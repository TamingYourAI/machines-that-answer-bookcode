"""Builders' Chapter 19 lab: orchestration, and the swap.

Seven steps:

  1. one interruption, two   an interruption behind 1,000 ms of queued
     queues                  audio, as a data frame and as a system frame
  2. playback truth          marks and the clear on the fee line: what the
                             marks prove, and the echo that proves nothing
  3. the interruption race   500 seeded races: a material term cut off,
     suite                   stale frames, late results, and reconnects
  4. speculative generation  200 stand-in turns: the reply started before
                             the end of the turn is confirmed
  5. spans on your own clock the same turn before and after a platform
                             release, as the vendor sees it and as you do
  6. the latency playbook    one turn, from cold and far to warm, near,
                             streamed, and speculative
  7. one call, end to end    the recurring caller's booking turn across
                             every boundary, with Part IV's pieces marked

Modes (select with ORCH_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point step 2 at your transport's own marks and
           clears, and run step 3's races against your orchestrator
           (evidence class: live laboratory).

  python3 orch_lab.py                  run and print the report
  python3 orch_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 orch_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The timings are
stand-ins from Chapters 6, 8, 11, and 14; they describe no product.
"""
from __future__ import annotations

import json
import os
import random
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

FRAME_MS = 20                    # one audio frame
CHUNK_MS = 200                   # a mark after each chunk (Chapter 8)


# ------------------------------------------- 1. one interruption, two queues

def interruption_delay(queued_ms: int, lane: str) -> int:
    """Audio the caller hears after the barge-in, before the interruption
    reaches the output transport and stops it."""
    if lane == "data":                  # in line behind the queued audio
        return queued_ms
    return FRAME_MS                     # ahead of the queue: one frame


# ----------------------------------------------------- 2. playback truth

def line_ms(text: str, wpm: int) -> int:
    return round(len(text.split()) / wpm * 60_000)


def chars_at(text: str, ms: float, total_ms: int) -> int:
    return min(len(text), int(len(text) * ms / total_ms))


def playback(fee: dict, barge_in: int, count_echoes: bool) -> dict:
    """What the marks say was played when a barge-in cuts the fee line.
    The transport echoes a mark when its chunk has played, and echoes every
    waiting mark at once when a clear empties its buffer."""
    total = line_ms(fee["line"], fee["wpm"])
    sent = min(total // CHUNK_MS, (barge_in + fee["ahead_ms"]) // CHUNK_MS)
    lands = barge_in + fee["one_way_ms"]            # the clear arrives
    played = min(sent, lands // CHUNK_MS)            # echoed while playing
    counted = sent if count_echoes else played
    heard = chars_at(fee["line"], counted * CHUNK_MS, total)
    return {"sent": sent, "played": played, "cleared": sent - played,
            "heard": heard, "total": total, "lands": lands,
            "fee_heard": heard > fee["line"].index(fee["term"])}


# --------------------------------------------- 3. the interruption race suite

def race(fee: dict, rng: random.Random) -> dict:
    """One seeded race: when the caller cuts in, and what else goes wrong."""
    return {"barge_in": rng.randint(1_000, 6_000),
            "in_flight_ms": rng.randint(0, 300),     # audio still coming
            "late_result": rng.random() < 0.5,
            "reconnect": rng.random() < 0.2}


def run_race(r: dict, fee: dict, correct: bool) -> set[str]:
    """The invariants one race breaks; a correct orchestrator breaks none."""
    broken = set()
    truth = playback(fee, r["barge_in"], count_echoes=False)
    seen = playback(fee, r["barge_in"], count_echoes=not correct)
    if seen["fee_heard"] and not truth["fee_heard"]:
        broken.add("unheard")             # a yes would cover the fee
    if not correct:
        if r["in_flight_ms"] >= FRAME_MS:
            broken.add("canceled")        # stale frames, forwarded
        if r["reconnect"] and truth["cleared"]:
            broken.add("canceled")        # resent after the clear was lost
        if r["late_result"]:
            broken.add("late")            # spoken, though its reply died
    return broken


def race_suite(fee: dict, runs: int, seed: int) -> dict:
    rng = random.Random(seed)
    races = [race(fee, rng) for _ in range(runs)]
    out = {}
    for name, correct in (("naive", False), ("correct", True)):
        counts = {"canceled": 0, "unheard": 0, "late": 0}
        for r in races:
            for k in run_race(r, fee, correct):
                counts[k] += 1
        out[name] = counts
    return out


# ------------------------------------------------ 4. speculative generation

SETTINGS = ["no speculation", "speculate the model",
            "speculate the model and the voice",
            "play before the turn is confirmed"]


def turn_spans(rng: random.Random, s: dict) -> dict:
    return {"stable": rng.randint(40, 80),       # a stable transcript
            "eot": max(120, round(rng.gauss(s["eot_ms"], 30))),
            "first_token": max(100, round(rng.gauss(s["first_token_ms"],
                                                    30))),
            "first_audio": max(50, round(rng.gauss(s["first_audio_ms"], 15))),
            "resume": rng.randint(400, 900)}      # if the caller goes on


def speculate(t: dict, s: dict, setting: str) -> tuple[int, bool]:
    """Voice to voice at the caller, and whether audio would play over a
    caller who goes on talking."""
    confirmed = t["eot"] + s["final_ms"]          # the turn, and its words
    start = t["stable"] if setting != "no speculation" else confirmed
    token = start + t["first_token"]
    if setting in ("no speculation", "speculate the model"):
        audio = max(confirmed, token) + t["first_audio"]
    else:                                          # the voice runs early too
        ready = token + t["first_audio"]
        audio = ready if setting.startswith("play") else max(confirmed,
                                                              ready)
    over = setting.startswith("play") and token + t["first_audio"] < \
        t["resume"]
    return s["carrier_in_ms"] + audio + s["send_ms"] + s["carrier_out_ms"], \
        over


def pct(xs: list[int], q: float) -> int:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def speculation(s: dict, seed: int) -> list[dict]:
    rng = random.Random(seed)
    turns = [turn_spans(rng, s) for _ in range(s["turns"])]
    goes_on = set(rng.sample(range(s["turns"]), s["goes_on"]))
    rows = []
    for setting in SETTINGS:
        v2v, over, wasted = [], 0, 0
        for i, t in enumerate(turns):
            ms, talks_over = speculate(t, s, setting)
            if i in goes_on:
                over += talks_over
                if setting != "no speculation":   # generated, then dropped
                    wasted += max(0, t["resume"] - t["stable"]
                                  - t["first_token"]) // s["ms_per_token"]
            else:
                v2v.append(ms)
        rows.append({"setting": setting, "p50": pct(v2v, 0.5),
                     "p95": pct(v2v, 0.95), "over": over,
                     "discarded": 0 if setting == "no speculation"
                     else len(goes_on), "wasted": wasted})
    return rows


# ------------------------------------------------ 5. spans on your own clock

def spans(t: dict, hold_ms: int) -> list[tuple[str, str, int, bool]]:
    """One turn on the utility's clock. The last field says whether the
    vendor's per-part dashboard shows the span."""
    return [("transport", "carrier and platform, in", t["in"], False),
            ("turn-taking", "caller stops -> end of turn", t["eot"], True),
            ("hearing", "end of turn -> final transcript", t["final"], True),
            ("thinking", "final transcript -> first token",
             t["first_token"], True),
            ("orchestration", "first token -> text sent to voice", hold_ms,
             False),
            ("speaking", "text sent -> first audio byte", t["first_audio"],
             True),
            ("transport", "first audio -> audio leaves", t["send"], False),
            ("transport", "carrier and platform, out", t["out"], False)]


# ------------------------------------------------ 6. the latency playbook

def playbook(p: dict) -> list[tuple[str, int]]:
    """One turn, lever by lever: each row is the turn after that lever."""
    rtt_far, rtt_near = p["rtt_far_ms"], p["rtt_near_ms"]
    cold = p["handshake_rtts"] * rtt_far          # TCP, then TLS 1.3
    ms = p["turn_ms"] + cold + (rtt_far - rtt_near) + p["sentence_hold_ms"]
    rows = [("cold, far, whole sentences, no speculation", ms)]
    for label, saving in (("connections kept warm", cold),
                          ("the model near the carrier",
                           rtt_far - rtt_near),
                          ("text streamed to the voice",
                           p["sentence_hold_ms"]),
                          ("the reply speculated", p["speculation_ms"])):
        ms -= saving
        rows.append(("+ " + label, ms))
    return rows


# ------------------------------------------------ 7. one call, end to end

def end_to_end(events: list) -> list[tuple[int, str, str, bool]]:
    return [(e[0], e[1], e[2], e[3]) for e in events]


# ---------------------------------------------------------------- the data

FEE = {"line": "The first opening is Tuesday at nine. There's a forty-dollar "
               "call-out fee. Shall I book it?",
       "term": "forty-dollar", "wpm": 150, "ahead_ms": 1_000,
       "one_way_ms": 40, "barge_in": 3_300}
SPEC = {"turns": 200, "goes_on": 26, "stable_ms": 60, "eot_ms": 220,
        "final_ms": 40, "first_token_ms": 170, "first_audio_ms": 85,
        "send_ms": 10, "carrier_in_ms": 40, "carrier_out_ms": 45,
        "ms_per_token": 10}
TURN = {"in": 40, "eot": 220, "final": 40, "first_token": 170,
        "first_audio": 85, "send": 10, "out": 45}
PLAYBOOK = {"turn_ms": 610, "rtt_far_ms": 140, "rtt_near_ms": 15,
            "handshake_rtts": 2, "sentence_hold_ms": 200,
            "speculation_ms": 170}
EVENTS = [  # the recurring caller's booking turn (ms from her last word)
    (0, "transport", "\"Yes, go ahead.\" leaves the caller", False),
    (40, "transport", "her audio reaches the agent", False),
    (240, "turn-taking", "end of turn: the words answer the question",
     False),
    (280, "hearing", "final transcript: \"yes, go ahead\"", False),
    (281, "thinking", "state loaded; the read-back was played in full, "
     "by marks: 91 of 91", True),
    (283, "thinking", "policy layer: book_visit allowed; the yes covers "
     "slot, address, fee", True),
    (284, "thinking", "op 7f3a journaled and the state saved, before the "
     "request leaves", True),
    (285, "systems", "book_visit sent to the scheduler", False),
    (295, "speaking", "\"Booking that now.\" from the line cache; checked: "
     "commits nothing", True),
    (350, "transport", "the caller hears the filler", False),
    (1_685, "systems", "the scheduler commits op 7f3a; the state is saved",
     True),
    (1_690, "speaking", "\"You're booked for Tuesday at nine.\" rendered "
     "from the state; checked: op 7f3a committed", True),
    (1_745, "transport", "the caller hears it; marks prove it played",
     True),
    (1_746, "thinking", "the explanation record for the turn is written",
     True)]


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"fee": FEE, "queued_ms": 1_000, "runs": 500, "spec": SPEC,
                "turn": TURN, "hold_ms": 200, "playbook": PLAYBOOK,
                "events": EVENTS}
    if mode == "fixture":
        return json.loads((FIXTURES / "orch.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ---------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    """Print text after a lead, wrapped at the page width and aligned."""
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    fee = data["fee"]
    out: list[str] = []
    put = out.append
    put(f"orchestration lab, mode={mode}; evidence class: simulated")
    put("")
    q = data["queued_ms"]
    put(f"1. one interruption, two queues ({q:,} ms of audio queued ahead "
        "of play-out)")
    put(f"   {'the interruption travels as':<44}"
        f"{'audio after the barge-in':>24}")
    for label, lane in (("a data frame, in line behind the audio", "data"),
                        ("a system frame, ahead of the queue", "system")):
        put(f"   {label:<44}{interruption_delay(q, lane):>18,} ms")
    put("")
    b = fee["barge_in"]
    first = playback(fee, b, count_echoes=False)
    naive = playback(fee, b, count_echoes=True)
    put(f"2. playback truth: the fee line ({len(fee['line'])} characters, "
        f"{first['total']:,} ms), a mark every {CHUNK_MS} ms")
    block(put, "   ", f"(the voice runs {fee['ahead_ms']:,} ms ahead of "
          f"play-out; the caller cuts in at {b:,} ms, and the clear reaches "
          f"the platform at {first['lands']:,} ms)")
    put(f"   marks sent {first['sent']}; echoed while playing "
        f"{first['played']}; echoed by the clear {first['cleared']}")
    put(f"   {'the orchestrator counts':<42}{'heard':<12}the fee")
    for label, r in (("every echoed mark as played", naive),
                     ("marks after the clear as cleared", first)):
        heard = f"{r['heard']} of {len(fee['line'])}"
        put(f"   {label:<42}{heard:<12}"
            f"{'counted as heard' if r['fee_heard'] else 'not heard'}")
    put(f"   heard: \"{fee['line'][:first['heard']].rstrip()}\"")
    put("")
    s = race_suite(fee, data["runs"], seed=19)
    put(f"3. the interruption race suite: {data['runs']} seeded races on "
        "the fee line")
    block(put, "   ", "(a barge-in anywhere from 1,000 to 6,000 ms; up to "
          "300 ms of audio still in flight from the voice; a late tool "
          "result in half the races; a reconnect in one in five)")
    put(f"   {'invariant broken':<44}{'naive':>10}{'correct':>10}")
    for key, label in (("canceled", "canceled audio reached the caller"),
                       ("unheard", "the fee counted as heard, unplayed"),
                       ("late", "a canceled reply's result spoken")):
        put(f"   {label:<44}{s['naive'][key]:>10}{s['correct'][key]:>10}")
    put("")
    sp = data["spec"]
    rows = speculation(sp, seed=19)
    put(f"4. speculative generation: {sp['turns']} stand-in turns, "
        f"{sp['goes_on']} of them paused mid-thought")
    put(f"   {'setting':<36}{'p50':>6}{'p95':>6}{'dropped':>9}"
        f"{'tokens':>8}{'over':>6}")
    for r in rows:
        put(f"   {r['setting']:<36}{r['p50']:>6}{r['p95']:>6}"
            f"{r['discarded']:>9}{r['wasted']:>8}{r['over']:>6}")
    block(put, "   ", "(voice to voice at the caller in ms, on the turns "
          "that ended; dropped: replies generated and discarded; tokens: "
          "generated for nothing; over: audio played over a caller who "
          "went on)")
    put("")
    t = data["turn"]
    put("5. spans on your own clock: one turn on provider A's platform, "
        "before and")
    put(f"   after a release that holds the text for a whole sentence")
    put(f"   {'layer':<14}{'span':<36}{'before':>8}{'after':>7}")
    before, after = spans(t, 0), spans(t, data["hold_ms"])
    for (layer, name, a, shown), (_, _, z, _) in zip(before, after):
        mark = "" if shown else " *"
        put(f"   {layer:<14}{name:<36}{a:>8}{z:>7}{mark}")
    put(f"   {'voice to voice at the caller':<50}"
        f"{sum(x[2] for x in before):>8}{sum(x[2] for x in after):>7}")
    vendor = [sum(x[2] for x in v if x[3]) for v in (before, after)]
    put(f"   {'the parts on the vendor dashboard':<50}{vendor[0]:>8}"
        f"{vendor[1]:>7}")
    put("   * not on the vendor's per-part dashboard; only your own clock "
        "sees it")
    put("")
    put("6. the latency playbook: one turn, lever by lever "
        "(ms at the caller)")
    for label, ms in playbook(data["playbook"]):
        put(f"   {label:<50}{ms:>8,}")
    p = data["playbook"]
    block(put, "   ", f"(round trips of {p['rtt_far_ms']} ms far and "
          f"{p['rtt_near_ms']} ms near; {p['handshake_rtts']} round trips "
          "to open a connection, TCP then TLS 1.3; stand-in values)")
    put("")
    put("7. one call, end to end: the recurring caller's booking turn")
    put(f"   {'ms':>6}    {'layer':<12}event (* added in Part IV)")
    for ms, layer, event, part4 in end_to_end(data["events"]):
        block(put, f"   {ms:>6,}  {'*' if part4 else ' '} {layer:<12}",
              event)
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("ORCH_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"orch_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "orch.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/orch.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("ORCH_LAB_MODE", "mock")))
    else:
        run_mode()
