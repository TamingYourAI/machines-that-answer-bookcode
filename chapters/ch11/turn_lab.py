"""Builders' Chapter 11 lab: turn-taking on the Service Line.

Five steps:

  1. the sweep        one silence timer against two thresholds chosen by the
                      words: false cut-offs and dead air over stand-in turns
  2. one turn         an account number read in two halves, traced on the
                      call clock under both detectors
  3. overlap          sounds while the agent speaks (backchannels, a
                      barge-in, a dog, the agent's own echo, a keypress, a
                      television) under three policies
  4. what was heard   the model's history after a barge-in, cut to the
                      words the caller heard
  5. silence          when the silence timers start, and for whom

Modes (select with TURN_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Replay your own recorded calls, with every pause
           labelled by a person as "inside the turn" or "the end" (evidence
           class: recorded replay).

  python3 turn_lab.py                  run and print the report
  python3 turn_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 turn_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The turns and their
pauses are stand-ins shaped like a service line's; the lab teaches the
trade-off under stated assumptions and does not set a production threshold.
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

FRAME_MS = 20            # one frame to notice that the silence started
SHORT_MS = 200           # wait when the words so far read as complete
LONG_MS = 1200           # wait when they do not
PILOT_TIMER_MS = 300     # the pilot's first setting: one silence timer
OTHER_SPANS_MS = 390     # the rest of Chapter 6's turn: 610 ms less 220
WALL_MS = 800            # the p95 wall at the caller (Chapter 1)

# ------------------------------------------------------------ 1. the sweep

DIGITS = {"zero", "oh", "one", "two", "three", "four", "five", "six",
          "seven", "eight", "nine"}
CONTINUES = {"and", "but", "because", "so", "or", "the", "a", "my", "is",
             "to", "of", "for", "with", "at", "um", "uh", "er", "if"}
STREET = {"road", "way", "street", "lane", "avenue", "drive"}


def complete(partial: str, asked: str) -> bool:
    """Do the words so far answer what the agent asked?"""
    words = partial.split()
    if not words or words[-1] in CONTINUES:
        return False
    if asked == "account":
        said = sum(w in DIGITS for w in words)
        return said == 0 or said >= 4        # "I don't have it" is an answer
    if asked == "address":
        return words[-1] in STREET
    return True


def wait_ms(partial: str, asked: str) -> int:
    return SHORT_MS if complete(partial, asked) else LONG_MS


def detect(turn: dict, timer_ms: int | None = None) -> tuple[bool, int]:
    """Cut off, and dead air after the true end: one timer, or the words."""
    words = []
    for text, pause in turn["segments"]:
        words.append(text)
        wait = timer_ms or wait_ms(" ".join(words), turn["asked"])
        if pause is None:
            return False, wait + FRAME_MS
        if pause > wait:
            return True, 0
    raise ValueError("a turn must end with a final segment")


def score(turns: list[dict], timer_ms: int | None = None) -> dict:
    cut, dead, why = 0, [], {}
    for t in turns:
        was_cut, air = detect(t, timer_ms)
        if was_cut:
            cut += 1
            why[t["kind"]] = why.get(t["kind"], 0) + 1
        else:
            dead.append(air)
    dead.sort()
    pct = lambda q: dead[min(len(dead) - 1, int(q * len(dead)))]
    return {"per_100": 100 * cut / len(turns), "p50": pct(0.50),
            "p95": pct(0.95), "max": dead[-1], "why": why,
            "long": sum(air > SHORT_MS + FRAME_MS for air in dead)}


# ---------------------------------------------------------------- 2. one turn


def trace(turn: dict, timer_ms: int | None = None) -> list[tuple[int, str]]:
    """Events on the call clock for one caller turn."""
    t, words, events = 0, [], []
    for text, pause in turn["segments"]:
        t += turn["speak_ms"][len(words)]
        words.append(text)
        partial = " ".join(words)
        wait = timer_ms or wait_ms(partial, turn["asked"])
        kind = "" if timer_ms else (
            "complete, " if wait == SHORT_MS else "not complete, ")
        tail = " ".join(partial.split()[-2:])
        events.append((t, f'stops after "...{tail}": {kind}waits {wait}'))
        if pause is None or pause > wait:
            events.append((t + wait + FRAME_MS, "end of turn: the agent "
                           "answers"))
            if pause is not None:
                events.append((t + pause, "the caller goes on: cut off"))
            return events
        t += pause
        events.append((t, "the caller goes on; the wait is cancelled"))
    return events


# ---------------------------------------------------------------- 3. overlap

BACKCHANNELS = {"mm-hm", "mm", "uh-huh", "right", "okay", "yeah", "sure",
                "i see"}
VOICE_MS = 100           # voice activity must last this long to count
WORDS_MS = 400           # the recognizer's first words, after the onset
DECIDE_MS = 600          # pause on voice: resume if nothing decides by then
TONE_MS = 40             # a keypress is known as an event, not from audio


def overlap(sound: dict, policy: str) -> tuple[str, int]:
    """What the agent does when a sound starts while it is speaking.

    Returns the action and, for a stop, how long the caller heard the
    agent over their own voice; for a resume, the gap they heard.
    """
    if sound["keypress"]:
        return "stop", TONE_MS
    words = sound["words"]
    own = bool(words) and words in sound["agent_words"]
    real = bool(words) and not own and words not in BACKCHANNELS
    if policy == "stop on voice":
        return "stop", VOICE_MS
    if policy == "stop on words":
        return ("stop", WORDS_MS) if real else ("keep talking", 0)
    if real:                                   # pause on voice, then decide
        return "stop", VOICE_MS
    return "resume", (WORDS_MS if words else DECIDE_MS) - VOICE_MS


# ---------------------------------------------------------------- 4. heard

FEE_LINE = ("The first opening is Tuesday at nine. There's a forty-dollar "
            "call-out fee. Shall I book it?")
WORDS_PER_MIN = 150                     # the voice brief (Chapter 3)


def line_ms(text: str) -> int:
    return round(len(text.split()) / WORDS_PER_MIN * 60_000)


def chars_at(text: str, ms: float) -> int:
    return min(len(text), int(len(text) * ms / line_ms(text)))


def history_after_cut(line: str, cut_ms: int, reply: str) -> list[dict]:
    """The model's history keeps what the caller heard, marked as cut."""
    heard = line[:chars_at(line, cut_ms)].rstrip()
    return [{"role": "agent", "text": heard, "cut_off": True},
            {"role": "caller", "text": reply}]


# ---------------------------------------------------------------- 5. silence

CHECK_S, OFFER_S, END_S = 5, 10, 15      # Chapter 4's working values
HOLD_EVERY_S, HOLD_MAX_S = 30, 120
RELAY_CHECK_S = 30                        # relay callers: never ended


def silence_plan(caller: str, played_s: float) -> list[tuple[float, str]]:
    """When each silence line fires, counted from the end of the question."""
    if caller == "relay":
        return [(played_s + RELAY_CHECK_S, "check in"),
                (played_s + 2 * RELAY_CHECK_S, "offer a text link"),
                (float("inf"), "never ended for silence")]
    if caller == "hold":
        return [(played_s + s, "check in")
                for s in range(HOLD_EVERY_S, HOLD_MAX_S + 1, HOLD_EVERY_S)]
    return [(played_s + CHECK_S, "are you still there?"),
            (played_s + OFFER_S, "offer a text link"),
            (played_s + END_S, "send the text, end kindly")]


# ---------------------------------------------------------------- inputs

YESNO = ["yes", "no", "yes please", "yes book it", "no thank you",
         "that's right", "yeah go ahead", "no that's not it"]
OPEN = ["the display on my meter has gone blank",
        "i want to ask why my bill doubled",
        "i'd like to book a technician", "is there an outage in ashby",
        "my power's been off since this morning",
        "i need to change my payment date"]
NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six",
                "seven", "eight", "nine"]


def spoken(n: int) -> str:
    return " ".join(NUMBER_WORDS[int(c)] for c in f"{n:04d}")


def stand_in_turns(seed: int = 11) -> list[dict]:
    """Two hundred answers from the middle of Service Line calls.

    Shares: 60 yes-or-no answers (two go on after "yes"), 50 account
    numbers (11 read in two halves, as in Chapter 4's coded calls), 30
    addresses (5 pause after the house number; 3 end without "road"), and
    60 answers to an open question (6 pause after "because" or "um", 2 go
    on after a finished sentence, 4 trail off on "um").
    """
    rng = random.Random(seed)
    turns = []

    def add(kind, asked, *segments):
        turns.append({"kind": kind, "asked": asked,
                      "segments": [list(s) for s in segments]})

    for i in range(60):
        if i < 2:
            add("a yes, then more", "yesno", ("yes", rng.randint(300, 700)),
                ("and can he call first", None))
        else:
            add("yes or no", "yesno", (rng.choice(YESNO), None))
    for i in range(50):
        n = rng.randint(1000, 9999)
        a, b = spoken(n).rsplit(" ", 2)[0], " ".join(spoken(n).split()[2:])
        if i < 11:
            add("a number in two halves", "account",
                (f"my account number is {a}", rng.randint(400, 1100)),
                (b, None))
        else:
            add("a number in one go", "account", (spoken(n), None))
    for i in range(30):
        street = rng.choice(["alder road", "kestrel way"])
        if i < 5:
            add("an address, a pause", "address",
                ("fourteen", rng.randint(300, 900)), (street, None))
        elif i < 8:
            add("an address, no 'road'", "address",
                (f"fourteen {street.split()[0]}", None))
        else:
            add("an address in one go", "address", (f"fourteen {street}",
                                                    None))
    for i in range(60):
        said = rng.choice(OPEN)
        if i < 6:
            head = rng.choice(["my bill has doubled because", "um"])
            add("an answer, a pause", "open",
                (head, rng.randint(300, 1000)), (said, None))
        elif i < 8:
            add("two sentences", "open", (said, rng.randint(250, 600)),
                ("and it was fine yesterday", None))
        elif i < 12:
            add("trails off", "open", (f"{said} um", None))
        else:
            add("one sentence", "open", (said, None))
    return turns


TRACED = {"kind": "a number in two halves", "asked": "account",
          "segments": [["my account number is two two", 700],
                       ["three one", None]],
          "speak_ms": [1900, 600]}

SOUNDS = [
    {"name": '"mm-hm"', "words": "mm-hm", "keypress": False},
    {"name": '"right"', "words": "right", "keypress": False},
    {"name": "a dog barks", "words": "", "keypress": False},
    {"name": "own voice, echoed", "words": "the first opening",
     "keypress": False},
    {"name": '"yes, book it"', "words": "yes book it", "keypress": False},
    {"name": '"no, Thursday"', "words": "no thursday", "keypress": False},
    {"name": "keypad 2", "words": "", "keypress": True},
    {"name": "a television", "words": "and in other news",
     "keypress": False}]
REAL = {'"yes, book it"', '"no, Thursday"', "keypad 2"}
POLICIES = ("stop on voice", "stop on words", "pause on voice")
BARGE_IN_MS = 3300


def inputs(mode: str) -> dict:
    if mode == "mock":
        agent = FEE_LINE.lower().replace(".", "").replace("?", "")
        sounds = [dict(s, agent_words=agent) for s in SOUNDS]
        return {"turns": stand_in_turns(), "traced": TRACED,
                "sounds": sounds, "fee_line": FEE_LINE,
                "barge_in_ms": BARGE_IN_MS}
    if mode == "fixture":
        return json.loads((FIXTURES / "turns.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ---------------------------------------------------------------- report


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    say = out.append
    say(f"turn lab, mode={mode}; evidence class: simulated")
    say("")
    turns = data["turns"]
    inside = sum(len(t["segments"]) > 1 for t in turns)
    say(f"1. the sweep: {len(turns)} stand-in turns, {inside} with a pause "
        "inside")
    timers = (300, 500, 700, 900, 1100, 1300)
    rows = {ms: score(turns, ms) for ms in timers}
    say("   one silence timer (ms)  " + "".join(f"{ms:>7}" for ms in timers))
    say("   cut off, per 100 turns  "
        + "".join(f"{rows[ms]['per_100']:>7.1f}" for ms in timers))
    say("   wait, p50 (ms)          "
        + "".join(f"{rows[ms]['p50']:>7}" for ms in timers))
    two = score(turns)
    say(f"   two thresholds ({SHORT_MS} ms when the words are complete, "
        f"{LONG_MS} when not)")
    say(f"   cut off, per 100 turns  {two['per_100']:>7.1f}")
    say(f"   wait (ms)               {two['p50']:>7} p50{two['p95']:>6} p95"
        f"{two['max']:>6} max")
    for kind, n in sorted(two["why"].items()):
        say(f"     cut off: {kind} ({n})")
    say(f"     waited {LONG_MS} ms: {two['long']} turns that sound "
        "unfinished and were not")
    match = next(ms for ms in timers if rows[ms]["per_100"]
                 <= two["per_100"])
    say(f"   voice to voice, adding the rest of Chapter 6's turn "
        f"({OTHER_SPANS_MS} ms):")
    say(f"     one timer at {match} ms, the first to cut off as few: "
        f"{rows[match]['p50'] + OTHER_SPANS_MS} ms")
    say(f"     two thresholds: {two['p50'] + OTHER_SPANS_MS} ms at p50, "
        f"{two['p95'] + OTHER_SPANS_MS} at p95 (wall {WALL_MS})")
    say("")
    segs = data["traced"]["segments"]
    say(f'2. one turn: "{segs[0][0]}" [{segs[0][1]} ms] "{segs[1][0]}"')
    for label, timer in ((f"one timer, {PILOT_TIMER_MS} ms", PILOT_TIMER_MS),
                         ("two thresholds", None)):
        say(f"   {label} (ms on the call clock)")
        for ms, what in trace(data["traced"], timer):
            say(f"   {ms:>7}  {what}")
    say("")
    say(f"3. sounds while the agent speaks: {len(POLICIES)} policies")
    say(f"   {'sound':<20}" + "".join(f"{p:>16}" for p in POLICIES))
    abandoned = {p: 0 for p in POLICIES}
    talked_over = {p: 0 for p in POLICIES}
    for s in data["sounds"]:
        cells = []
        for p in POLICIES:
            act, ms = overlap(s, p)
            if act == "stop" and s["name"] not in REAL:
                abandoned[p] += 1
            if act == "stop" and s["name"] in REAL and ms > talked_over[p]:
                talked_over[p] = ms
            cells.append({"stop": f"stops, {ms} ms", "keep talking":
                          "talks on", "resume": f"{ms} ms gap"}[act]
                         if s["name"] in REAL or act != "stop" else "stops")
        say(f"   {s['name']:<20}" + "".join(f"{c:>16}" for c in cells))
    say(f"   {'stopped for nothing':<20}"
        + "".join(f"{abandoned[p]:>16}" for p in POLICIES))
    say(f"   {'talked over (ms)':<20}"
        + "".join(f"{talked_over[p]:>16}" for p in POLICIES))
    say("")
    line, cut = data["fee_line"], data["barge_in_ms"]
    history = history_after_cut(line, cut, "Yes, book it.")
    say(f"4. what the caller heard: a barge-in {cut} ms into the fee line")
    for i, part in enumerate(textwrap.wrap(line, 56, break_on_hyphens=False)):
        say(f"   {'generated:' if i == 0 else '':<11}{part}")
    say(f"   {'heard:':<11}{history[0]['text']}")
    say(f"   {'':<11}({chars_at(line, cut)} of {len(line)} characters)")
    say("   the history the model reads next:")
    say(f"     agent   {history[0]['text']} [cut off]")
    say(f"     caller  {history[1]['text']}")
    say("   the fee is not in the history: the agent says it before "
        "booking")
    say("")
    played = line_ms(line) / 1000
    say(f"5. silence after a question: the fee line plays for "
        f"{played:.1f} s")
    say("   (seconds from the start of the line)")
    early = silence_plan("most", 0.2)[0][0]
    say(f"   timers from when the line was sent: the check fires at "
        f"{early:.1f} s,")
    say("   while the question is still playing")
    say(f"   {'timers from the end of play-out':<34}{'check':>7}"
        f"{'text offer':>12}{'end':>8}")
    for caller, label in (("most", "most callers"),
                          ("relay", "a relay caller")):
        plan = silence_plan(caller, played)
        cells = ["never" if t == float("inf") else f"{t:.1f} s"
                 for t, _ in plan]
        say(f"     {label:<32}{cells[0]:>7}{cells[1]:>12}{cells[2]:>8}")
    holds = ", ".join(f"{t:.0f}" for t, _ in silence_plan("hold", 0.0))
    say(f'   after "hang on": check in at {holds} s')
    return "\n".join(line.rstrip() for line in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("TURN_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"turn_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "turns.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/turns.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("TURN_LAB_MODE", "mock")))
    else:
        run_mode()
