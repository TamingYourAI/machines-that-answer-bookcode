"""Builders' Chapter 26 lab: observability, and the week you improve.

One bad call, followed from its trace to a scenario the suite runs forever:

  1. the bad call's trace       what the caller said, when the turn was
                                judged over, and what the agent did
  2. name the layer             the failure taxonomy's rules, applied to
                                every turn; the first failing turn names
                                the layer that owns the fix
  3. promote it to the suite    the call written as a scenario, with the
                                caller's words and pauses, and no personal
                                data
  4. the suite catches it       every turn-taking scenario on the rules
                                before and after the fix, and the guard
                                that the fix slowed nothing else
  5. the week's review          flagged calls by layer, and the days from
                                each call to its scenario

Modes (select with OBSERVE_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Feed step 1 a trace from your own orchestrator
           and step 5 a week of your flagged calls (evidence class: field).

  python3 observe_lab.py                  run and print the report
  python3 observe_lab.py --write-fixture  regenerate fixtures/
  python3 observe_lab.py --check          compare with the frozen output

Evidence class: simulated. The call, the rules, the suite, and the week
are stand-ins; the waits are the Service Line's working values.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

FIRST_AUDIO_MS = 650   # from the turn's end to the agent's first audio


# ------------------------------------------------- turn-taking rule sets

SLOTS = {"monday", "tuesday", "wednesday", "thursday", "friday",
         "saturday"}
ANSWERS = {"yes", "no", "yeah", "fine"} | SLOTS
NUMBER_WORDS = {"zero", "one", "two", "three", "four", "five", "six",
                "seven", "eight", "nine"}


def wait_ms(words: str, rules: str) -> int:
    """How long the end-of-turn decision waits after the caller stops,
    given the words so far. v2.3 is the pilot's rule: 200 ms when the words
    answer the question, 1,200 ms when not (Chapter 11). v2.4 adds one line:
    a slot refused without an alternative waits 1,000 ms, because callers
    who say "not Tuesday" usually say which day they want next."""
    w = words.lower().replace(",", "").split()
    if not w:
        return 1200
    if w[-1] in NUMBER_WORDS and len([x for x in w if x in NUMBER_WORDS]) < 4:
        return 1200                           # a number read in halves
    if rules == "v2.4" and "not" in w and not (set(w[w.index("not") + 2:])
                                               & SLOTS):
        return 1000                           # a refusal, no alternative yet
    if set(w) & ANSWERS:
        return 200
    return 1200


def play(segments: list[list], rules: str) -> dict:
    """Run one caller answer, given as spoken segments and the pauses after
    them, through a rule set. Returns where the turn ended and whether the
    agent's first audio started while the caller was still talking."""
    heard, t, ended_at, cut_off = "", 0, None, False
    for i, (text, dur, pause) in enumerate(segments):
        heard = (heard + " " + text).strip()
        t += dur
        wait = wait_ms(heard, rules)
        last = i == len(segments) - 1
        if last or pause > wait:
            ended_at = t + wait
            audio = ended_at + FIRST_AUDIO_MS
            resumes = t + pause if not last else None
            cut_off = resumes is not None and resumes < audio + 400
            return {"heard_at_end": heard, "ended_ms": ended_at,
                    "wait": wait, "cut_off": cut_off and not last,
                    "audio_ms": audio}
        t += pause
    return {"heard_at_end": heard, "ended_ms": ended_at, "wait": 0,
            "cut_off": cut_off, "audio_ms": None}


# ------------------------------------------------------ 1. the bad call

BAD_CALL = {
    "id": "c-8124-1", "trace": "4f19a2e7", "account": "8124",
    "rules": "v2.3",
    "offer": "Tuesday at nine is the first opening. Shall I book it?",
    "answer": [["not tuesday", 620, 700], ["wednesday if you can", 1100, 0]],
    "after": ["the agent stopped when she spoke over it, then offered Tuesday "
              "at one", "she said \"Wednesday\" again and was cut off after "
              "\"Wed\"", "she asked for a person; handed over at 01:52"],
}


# ------------------------------------------------ 2. name the layer

TAXONOMY = [  # the first rule that matches a turn names its layer
    ("transport", "no audio, or one-way, for over 2 s"),
    ("hearing", "a word said was written as another"),
    ("turn-taking", "the turn ended while the caller spoke"),
    ("thinking", "a proposal contradicts the state or rules"),
    ("systems of record", "a tool failed, or answered stale"),
    ("speaking", "what played differs from what was made"),
    ("orchestration", "a gap between spans that no layer owns"),
]


def first_match(checks: dict) -> tuple[str, str]:
    """The first rule, in the taxonomy's order, whose check matched. A gap
    no layer owns is checked last, after every layer had its chance."""
    for layer, rule in TAXONOMY:
        if checks.get(layer):
            return layer, rule
    return "none", ""


def name_layer(call: dict) -> tuple[str, str, dict]:
    """Apply the taxonomy to the call's first failing turn. The stand-in
    trace has clean audio and a correct transcript, so the first two rules
    pass and the third names the layer."""
    r = play(call["answer"], call["rules"])
    checks = {"transport": False, "hearing": False,
              "turn-taking": r["cut_off"], "thinking": False,
              "systems of record": False, "speaking": False,
              "orchestration": False}
    layer, rule = first_match(checks)
    return layer, rule, r


# ------------------------------------------ 3. promote it to the suite

def promote(call: dict) -> dict:
    """The bad call written as a scenario: the offer, the caller's words and
    pauses as recorded, and what must be true. It points back to the trace
    by its opaque id; the call id carries the account number, so it stays
    out, with the caller's number and name."""
    return {"id": "tt-17", "from": call["trace"], "layer": "turn-taking",
            "offer": call["offer"],
            "caller": [[t, d, p] for t, d, p in call["answer"]],
            "expect": {"cut_off": False, "slot": "wednesday"}}


SUITE = [  # the turn-taking scenarios already in the library
    {"id": "tt-01", "caller": [["yes", 300, 0]],
     "expect": {"cut_off": False, "max_wait": 200}},
    {"id": "tt-02", "caller": [["tuesday at nine is fine", 1200, 0]],
     "expect": {"cut_off": False, "max_wait": 200}},
    {"id": "tt-05", "caller": [["two two", 650, 700], ["three one", 650, 0]],
     "expect": {"cut_off": False}},
    {"id": "tt-08", "caller": [["no", 250, 0]],
     "expect": {"cut_off": False, "max_wait": 200}},
    {"id": "tt-11", "caller": [["um", 300, 900],
                               ["the lights are on", 1000, 0]],
     "expect": {"cut_off": False}},
    {"id": "tt-14", "caller": [["not tuesday", 620, 0]],
     "expect": {"cut_off": False, "max_wait": 1000}},
]


def run_scenario(sc: dict, rules: str) -> tuple[bool, dict]:
    r = play(sc["caller"], rules)
    ok = r["cut_off"] == sc["expect"]["cut_off"]
    if "max_wait" in sc["expect"]:
        ok = ok and r["wait"] <= sc["expect"]["max_wait"]
    if "slot" in sc["expect"]:
        ok = ok and sc["expect"]["slot"] in r["heard_at_end"]
    return ok, r


# ---------------------------------------------------- 5. the week's review

WEEK = [  # flagged calls this week: layer, days from the call to scenario
    ["hearing", 1], ["hearing", 2], ["hearing", 2], ["hearing", 3],
    ["hearing", 1], ["hearing", 4], ["hearing", 2], ["hearing", 6],
    ["turn-taking", 1], ["turn-taking", 2], ["turn-taking", 2],
    ["turn-taking", 3], ["turn-taking", 1],
    ["thinking", 3], ["thinking", 5], ["thinking", 4],
    ["systems of record", 2], ["systems of record", 9],
    ["speaking", 1], ["transport", 2],
]


def review(week: list[list]) -> list[tuple]:
    rows = []
    for layer, _ in TAXONOMY:
        days = [d for lyr, d in week if lyr == layer]
        if days:
            rows.append((layer, len(days), statistics.median(days),
                         max(days), sum(d > 7 for d in days)))
    return rows


# ------------------------------------------------------------ inputs

def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"bad_call": BAD_CALL, "suite": SUITE, "week": WEEK}
    if mode == "fixture":
        return json.loads((FIXTURES / "observe.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    call = data["bad_call"]
    put(f"observe lab, mode={mode}; evidence class: simulated")
    put("")
    put(f"1. the bad call's trace (call {call['id']}; turn-taking rules "
        f"{call['rules']})")
    put(f"   {'ms':>6}  event (from the end of the offer)")
    block(put, f"   {0:>6}  offer ends: ", f"\"{call['offer']}\"")
    r = play(call["answer"], call["rules"])
    first = call["answer"][0]
    put(f"   {first[1]:>6}  caller stops: \"{first[0]}\"")
    put(f"   {r['ended_ms']:>6}  turn ended: the words answer the question, "
        f"waited {r['wait']} ms")
    resumes = first[1] + first[2]
    put(f"   {resumes:>6}  caller resumes: \"{call['answer'][1][0]}\"")
    put(f"   {r['audio_ms']:>6}  agent's first audio starts over her")
    for line in call["after"]:
        block(put, f"   {'':>6}  then: ", line)
    put("")
    layer, rule, _ = name_layer(call)
    put("2. name the layer: the taxonomy, first match wins")
    for lyr, rl in TAXONOMY:
        mark = "<- named" if lyr == layer else ""
        put(f"   {lyr:<19}{rl:<44}{mark}".rstrip())
    put("")
    sc = promote(call)
    put("3. promote it to the suite: the scenario written from the call")
    put(f"   id {sc['id']}, from trace {sc['from']}, layer {sc['layer']}")
    for text, dur, pause in sc["caller"]:
        put(f"   caller says \"{text}\" ({dur} ms), then {pause} ms of "
            "silence" if pause else f"   caller says \"{text}\" ({dur} ms), "
            "then stops")
    put("   expect: no cut-off; the booking asks about wednesday")
    put("   left out: the call id (it carries the account), the caller's "
        "number")
    put("")
    put("4. the suite catches it: every turn-taking scenario, both rule sets")
    put(f"   {'scenario':<10}{'v2.3':<18}{'v2.4':<18}wait v2.3 / v2.4")
    fails = {"v2.3": 0, "v2.4": 0}
    for s in data["suite"] + [sc]:
        res = {}
        for rules in ("v2.3", "v2.4"):
            ok, rr = run_scenario(s, rules)
            res[rules] = (ok, rr)
            fails[rules] += not ok
        cell = lambda ok, rr: ("pass" if ok else
                               "FAIL: cut off" if rr["cut_off"] else "FAIL")
        put(f"   {s['id']:<10}{cell(*res['v2.3']):<18}"
            f"{cell(*res['v2.4']):<18}"
            f"{res['v2.3'][1]['wait']:>4} / {res['v2.4'][1]['wait']} ms")
    block(put, "   ", f"v2.3 fails {fails['v2.3']}, v2.4 fails "
          f"{fails['v2.4']}; the plain answers still end at 200 ms, and only "
          "a refused slot with nothing after it waits longer")
    put("")
    put("5. the week's review: flagged calls by the layer they named")
    put(f"   {'layer':<19}{'calls':>6}{'median days':>13}{'longest':>9}"
        f"{'over a week':>13}")
    for lyr, n, med, mx, late in review(data["week"]):
        put(f"   {lyr:<19}{n:>6}{med:>13g}{mx:>9}{late:>13}")
    total = len(data["week"])
    late = sum(d > 7 for _, d in data["week"])
    block(put, "   ", f"{total} flagged calls, each now a scenario; {late} "
          "took longer than a week, and goes on the review's agenda")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("OBSERVE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"observe_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "observe.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/observe.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("OBSERVE_LAB_MODE", "mock")))
    else:
        run_mode()
