"""Builders' Chapter 6 lab: the stack, one turn at a time.

Five steps:

  1. the contracts      each layer's input, output, cancel rule, and clock, as data, and a
                        conformance check run on four stand-in adapters
  2. where time goes    one turn traced on the call clock and attributed to layers; then the
                        same turn with each vendor's own timestamps
  3. the event timeline the Service Line's fee read-back, cut by a barge-in: what the
                        pipeline records, and what a speech-to-speech session reports
  4. two architectures  the same dialogue, 400 turns each: voice-to-voice at the caller, time
                        to stop after a barge-in, and what each can no longer observe
  5. the ecosystem map  who owns, bills, answers for, and ports each boundary of the pilot

Modes (select with STACK_LAB_MODE or run_mode(mode=...)):
  mock     timings generated from seeded random numbers (default; runs anywhere)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. The companion app writes the same per-layer timestamps on the
           call clock; export a call's spans in the fixture schema to put it on this ruler.

  python3 stack_lab.py                  run and print the report
  python3 stack_lab.py --write-fixture  regenerate fixtures/ from the mock seeds
  python3 stack_lab.py --check          compare with the frozen output in outputs/

Evidence class of every number printed: simulated. Stage timings are stand-ins chosen to show
the shape of each architecture; they measure no product, model, or network.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

N_TURNS = 400        # turns per architecture in step 4
WALL_MS = 800        # the wall (a dated working value, builders' Chapter 1)
CANCEL_MS = 50       # a layer must stop within this after a cancel (a working value)
WORDS_PER_MIN = 150  # the Service Line's voice brief


# ---------------------------------------------------------------- 1. the contracts

CONTRACTS = [
    # layer, what goes in, what comes out
    ("transport", "caller audio", "20 ms frames; audio out; call control"),
    ("hearing", "20 ms frames", "partials, then a final with timestamps"),
    ("turn-taking", "frames, partials", "end of turn; barge-in"),
    ("thinking", "final text, state", "tokens and tool calls, streamed"),
    ("speaking", "text for the ear", "audio chunks, each tagged with a line"),
    ("systems of record", "an operation", "a result, or a failure class"),
    ("orchestration", "every event above", "cancels; the event timeline"),
    ("observability", "every span", "one trace per call, on one clock"),
]
RULES = ("streams its output", f"stops within {CANCEL_MS} ms of a cancel",
         "stamps the call clock", "classifies its errors")


@dataclass(frozen=True)
class Adapter:
    name: str
    streams: bool
    cancel_ms: int | None       # None: it cannot be cancelled; it plays or runs to the end
    clock: str                  # "call": our clock at the boundary; "vendor": theirs
    errors: str                 # "classified" or "free text"


ADAPTERS = [
    Adapter("hearing, stand-in A", True, 15, "call", "classified"),
    Adapter("speaking, stand-in B", True, None, "call", "classified"),
    Adapter("thinking, stand-in C", True, 30, "vendor", "free text"),
    Adapter("speaking, stand-in D", False, 20, "call", "classified"),
]


def conformance(a: Adapter) -> list[str]:
    """What stops an adapter from standing behind a layer's contract."""
    fails = []
    if not a.streams:
        fails.append("waits for the whole reply")
    if a.cancel_ms is None or a.cancel_ms > CANCEL_MS:
        fails.append("cannot be stopped in time")
    if a.clock != "call":
        fails.append("vendor timestamps only")
    if a.errors != "classified":
        fails.append("errors are free text")
    return fails


# ---------------------------------------------------------------- 2. where time goes

# One turn, as the orchestrator saw each boundary: ms on the call clock.
TURN = {"caller stops speaking": 41_210, "end of turn decided": 41_430,
        "final transcript": 41_470, "first token": 41_640, "first audio byte": 41_725,
        "audio leaves the server": 41_735}
NET_IN_MS, NET_OUT_MS = 40, 45        # carrier and jitter buffer, each way (stand-ins)
# The same boundaries in each vendor's own timestamps: skewed clocks.
SKEW_MS = {"final transcript": 85, "first token": 0, "first audio byte": -120}


def attribute(t: dict[str, int]) -> list[tuple[str, str, int]]:
    """Consecutive boundaries become spans; each span belongs to one layer."""
    names = list(t)
    owners = ["turn-taking", "hearing", "thinking", "speaking", "transport"]
    return [(owners[i], f"{names[i]} -> {names[i + 1]}", t[names[i + 1]] - t[names[i]])
            for i in range(len(names) - 1)]


def skewed(t: dict[str, int]) -> dict[str, int]:
    return {k: v + SKEW_MS.get(k, 0) for k, v in t.items()}


# ---------------------------------------------------------------- 3. the event timeline

FEE_LINE = [("The first opening is ", None), ("Tuesday at nine", "slot"),
            (". There's a ", None), ("forty-dollar call-out fee", "fee"),
            (". Shall I book it?", None)]
BARGE_IN_MS = 3300    # the caller says "yes, book it" this far into the line


def spans(parts) -> tuple[str, dict[str, tuple[int, int]]]:
    text, where = "", {}
    for piece, term in parts:
        if term:
            where[term] = (len(text), len(text) + len(piece))
        text += piece
    return text, where


def chars_played(text: str, ms: int) -> int:
    """Characters of the line played by ms, at the brief's speaking rate."""
    words = len(text.split())
    total_ms = words / WORDS_PER_MIN * 60_000
    return min(len(text), int(len(text) * ms / total_ms))


def timeline(parts, barge_ms: int) -> dict:
    text, where = spans(parts)
    played = chars_played(text, barge_ms)
    heard = sorted(t for t, (_, end) in where.items() if end <= played)
    return {"text": text, "played": played, "heard": heard, "terms": sorted(where)}


# ---------------------------------------------------------------- 4. two architectures

PIPELINE = {"net_in": 35, "endpoint": 180, "stt": 35, "model": 150, "tts": 75,
            "net_out": 40}
SPEECH_TO_SPEECH = {"net_in": 35, "endpoint": 220, "model_audio": 200, "net_out": 40}
SIGMA = 0.3
OBSERVE = [
    ("time per layer", "five spans", "one span"),
    ("what the caller said", "the recognizer's text", "a side transcript"),
    ("the words spoken", "the text we sent", "a side transcript"),
    ("terms heard, after a cut", "from word offsets", "estimated, from ms"),
    ("swap one layer", "yes", "three move together"),
]


def simulate(stages: dict[str, int], seed: int) -> list[int]:
    """Voice to voice at the caller. Tool turns are left out: a short spoken line covers
    them in both architectures (builders' Chapter 17)."""
    rng = random.Random(seed)
    return [round(sum(rng.lognormvariate(math.log(m), SIGMA) for m in stages.values()))
            for _ in range(N_TURNS)]


def pct(xs: list[int], p: float) -> int:
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


# ---------------------------------------------------------------- 5. the ecosystem map

ECOSYSTEM = [
    # boundary, who owns it, who bills it, who answers when it fails, portability class
    ("caller to platform", "utility", "platform", "platform", "with work"),
    ("platform to hearing", "provider A", "speech vendor", "provider A", "swappable"),
    ("hearing to thinking", "provider A", "provider A", "provider A", "coupled"),
    ("thinking to rules", "utility", "model vendor", "utility", "swappable"),
    ("rules to systems", "utility", "nobody", "utility", "ours"),
    ("thinking to speaking", "provider A", "speech vendor", "provider A", "swappable"),
    ("every span to traces", "utility", "nobody", "utility", "ours"),
]


# ---------------------------------------------------------------- inputs and report

def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"pipeline": simulate(PIPELINE, 6),
                "speech-to-speech": simulate(SPEECH_TO_SPEECH, 7)}
    if mode == "fixture":
        return json.loads((FIXTURES / "turns.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    say = out.append
    say(f"stack lab, mode={mode}; evidence class: simulated (stand-in timings)")
    say("")
    say("1. the contracts: every layer, the same four rules")
    say(f"   {'layer':<18}{'in':<19}out")
    for layer, i, o in CONTRACTS:
        say(f"   {layer:<18}{i:<19}{o}")
    say(f"   rules: {'; '.join(RULES[:2])};")
    say(f"          {'; '.join(RULES[2:])}")
    for a in ADAPTERS:
        fails = conformance(a)
        say(f"   {a.name:<22}{'passes' if not fails else 'fails: ' + '; '.join(fails)}")
    say("")
    say("2. where time goes: one turn, call clock (ms)")
    total = NET_IN_MS + (TURN["audio leaves the server"] - TURN["caller stops speaking"]) \
        + NET_OUT_MS
    say(f"   {'layer':<13}{'span':<44}{'ms':>5}")
    say(f"   {'transport':<13}{'carrier and jitter buffer, in':<44}{NET_IN_MS:>5}")
    for layer, span, ms in attribute(TURN):
        say(f"   {layer:<13}{span:<44}{ms:>5}")
    say(f"   {'transport':<13}{'carrier and jitter buffer, out':<44}{NET_OUT_MS:>5}")
    say(f"   voice to voice at the caller: {total} ms")
    say("   the same boundaries in each vendor's own timestamps:")
    for layer, span, ms in attribute(skewed(TURN))[1:4]:
        flag = "  impossible" if ms < 0 else ""
        say(f"   {layer:<13}{span:<44}{ms:>5}{flag}")
    say("")
    say(f"3. the event timeline: a barge-in {BARGE_IN_MS} ms into the fee line")
    tl = timeline(FEE_LINE, BARGE_IN_MS)
    say(f"   \"{tl['text'][:37]}")
    say(f"    {tl['text'][37:]}\"")
    heard = ", ".join(tl["heard"]) or "none"
    unheard = ", ".join(t for t in tl["terms"] if t not in tl["heard"])
    say(f"   pipeline: played {tl['played']} of {len(tl['text'])} characters; "
        f"heard: {heard}")
    say(f"   the caller's yes covers {heard} only; the agent reads the {unheard} "
        "again")
    say(f"   speech-to-speech: {BARGE_IN_MS} ms of audio played; the words behind")
    say("   them come from a side transcript; the terms heard are an estimate")
    say("")
    say(f"4. two architectures, the same dialogue ({N_TURNS} turns each, ms)")
    say(f"   {'':<18}{'p50':>6}{'p95':>6}{'over the wall':>15}")
    for arch in ("pipeline", "speech-to-speech"):
        xs = data[arch]
        over = sum(x > WALL_MS for x in xs) / len(xs) * 100
        say(f"   {arch:<18}{pct(xs, .5):>6}{pct(xs, .95):>6}{over:>14.1f}%")
    say(f"   {'what you can see':<26}{'pipeline':<23}speech-to-speech")
    for what, p, s in OBSERVE:
        say(f"   {what:<26}{p:<23}{s}")
    say("")
    say("5. the ecosystem map: the Service Line's pilot")
    say(f"   {'boundary':<22}{'owns':<12}{'bills':<15}{'answers':<12}class")
    for b, own, bill, fix, port in ECOSYSTEM:
        say(f"   {b:<22}{own:<12}{bill:<15}{fix:<12}{port}")
    return "\n".join(out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("STACK_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"stack_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "turns.json").write_text(json.dumps(inputs("mock")))
        print("wrote fixtures/turns.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("STACK_LAB_MODE", "mock")))
    else:
        run_mode()
