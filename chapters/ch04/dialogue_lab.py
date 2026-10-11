"""Builders' Chapter 4 lab: a dialogue object, a repair catalog, and confirmation by risk.

Four steps:

  1. the dialogue object   the Service Line's "book a technician visit" flow, as data
  2. confirmation by risk  how the agent confirms each slot, chosen by the slot's risk
  3. two designs, five calls
                           the same scripted callers through a flow with one repair line
                           (v1) and through a repair catalog with fail-over (v2)
  4. the read-aloud test   the happy path as the agent says it, checked line by line

Each caller turn is labeled with the act the recognizer and understanding delivered (a value,
a yes, unclear speech, silence, a request for a person, a question out of scope, touch-tones),
so the lab tests the dialogue design and nothing else.

Modes (select with DIALOGUE_LAB_MODE or run_mode(mode=...)):
  mock     the flow and the callers are built in this file (default)
  fixture  both are loaded from fixtures/ (committed; same schema)
  live     not in this lab. Code your own calls in the callers' schema and replay them.

  python3 dialogue_lab.py                  run and print the report
  python3 dialogue_lab.py --write-fixture  regenerate fixtures/ from the data here
  python3 dialogue_lab.py --check          compare with the frozen output in outputs/

Evidence class: simulated. The callers are scripted to show each failure; nothing here
estimates how often any failure happens.
"""
from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ---------------------------------------------------------------- 1. the dialogue object

def book_visit_flow() -> dict:
    """The flow as data: slots in order, each with its question and its risk."""
    return {
        "name": "book a technician visit",
        "slots": [
            {"name": "intent", "risk": "low",
             "ask": "This is the utility's automated assistant. How can I help?"},
            {"name": "account", "risk": "identifier", "keypad": True,
             "ask": "What's your account number?"},
            {"name": "address", "risk": "high",
             "ask": "Is the visit for fourteen Alder Road?"},
            {"name": "issue", "risk": "low",
             "ask": "What's happening with the meter?"},
            {"name": "time", "risk": "commitment",
             "ask": "The first opening is Tuesday at nine. Shall I book it, with the "
                    "forty-dollar call-out fee?"},
        ],
        "done": "You're booked for Tuesday at nine. I've sent a text with the details.",
        "handover": "Putting you through now, with what you've told me.",
        "max_failures": 2,
        "person_wait_min": 6,
    }


# ---------------------------------------------------------------- 2. confirmation by risk

CONFIRM = {
    "low": "none: move to the next question",
    "identifier": "read back in groups, then a yes",
    "high": "the question is the read-back; a yes",
    "commitment": "the terms in the question; the yes binds one operation",
}
DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def grouped(d: str) -> str:
    words = [DIGITS[int(c)] for c in d]
    size = 2 if len(words) == 4 else 3
    return ", ".join(" ".join(words[i:i + size]) for i in range(0, len(words), size))


def read_back(slot: dict, value: str) -> str | None:
    """The confirmation line for a value the caller gave, or None if none is needed."""
    if slot["risk"] == "identifier":
        return f"That's {grouped(value)}. Is that right?"
    return None


# ---------------------------------------------------------------- 3. two designs

def callers() -> dict:
    v = lambda said, value=None: {"act": "value", "said": said, "value": value or said}
    yes = {"act": "yes", "said": "Yes."}
    return {
        "happy path": [v("My meter's display has gone blank."), v("two two three one", "2231"),
                       yes, yes, v("It's just blank."), yes],
        "misheard number": [v("My meter's display has gone blank."),
                            {"act": "unclear", "said": "two two ... [crosstalk]"},
                            {"act": "unclear", "said": "two two three... one"},
                            {"act": "keypad", "said": "[DTMF 2231]", "value": "2231"},
                            yes, yes, v("It's blank."), yes],
        "asks for a person": [{"act": "person", "said": "Agent."},
                              {"act": "person", "said": "Agent, please."}],
        "silence": [v("My meter's display has gone blank."),
                    {"act": "silence", "said": "[silence 5 s]"},
                    {"act": "silence", "said": "[silence 5 s]"},
                    {"act": "silence", "said": "[silence 5 s]"}],
        "out of scope": [{"act": "out of scope", "said": "Can you tell me about solar rebates?"},
                         {"act": "person", "said": "OK, a person then."}],
    }


FAILURES = ("unclear", "silence", "out of scope", "person")
REPAIRS = {  # the first, then the second, line for each kind of failure
    "unclear": ["Sorry, I missed part of that. Could you say it again, a "
                "few digits at a time?",
                "You can also type it on your keypad now."],
    "silence": ["Are you still there?",
                "I can text you a link to finish this, or you can call "
                "back any time."],
    "out of scope": ["I can't help with that one here. I can book visits "
                     "and answer billing questions, or put you through to "
                     "a person."],
    "person": ["I can put you through now; the wait is about {wait} "
               "minutes. Or I can book the visit with you in about a "
               "minute."],
}
OFFERS_A_PERSON = ("out of scope", "person")
TEXT_AND_END = "I've sent you that link by text. Goodbye for now."


@dataclass
class Result:
    lines: list = field(default_factory=list)
    outcome: str = "hung up"
    repeats: int = 0

    def agent(self, line: str) -> None:
        if line in [t for who, t in self.lines if who == "Agent"]:
            self.repeats += 1                  # the same words, said again
        self.lines.append(("Agent", line))


def last_sentence(line: str) -> str:
    return re.split(r"(?<=[.?!])\s+", line)[-1]


def run(flow: dict, turns: list[dict], catalog: bool) -> Result:
    """v1 (catalog=False) has one repair line for every failure. v2 picks from
    the catalog, never repeats a repair, and fails over to a keypad, a text,
    or a person."""
    r = Result()
    slots = flow["slots"]
    i, pending, offered, v1_fails = 0, None, False, 0
    fails: dict[str, int] = {}
    r.agent(slots[0]["ask"])
    for t in turns:
        r.lines.append(("Caller", t["said"]))
        act = "unclear" if t["act"] == "keypad" and not catalog else t["act"]
        if act in FAILURES and not catalog:
            v1_fails += 1
            if v1_fails > flow["max_failures"]:
                r.outcome = "hung up in a loop"
                return r
            again = last_sentence(slots[i]["ask"])
            r.agent(f"Sorry, I didn't catch that. {again}")
            continue
        if act in FAILURES:
            n = fails[act] = fails.get(act, 0) + 1
            exhausted = n > len(REPAIRS[act])
            if exhausted or act == "person" and offered:
                if act == "silence":
                    r.agent(TEXT_AND_END)
                    r.outcome = "text sent, call ended"
                else:
                    r.agent(flow["handover"])
                    r.outcome = "handed over with context"
                return r
            r.agent(REPAIRS[act][n - 1].format(wait=flow["person_wait_min"]))
            offered = offered or act in OFFERS_A_PERSON
            continue
        fails, v1_fails = {}, 0
        if act in ("value", "keypad") and read_back(slots[i], t["value"]):
            pending = t["value"]
            r.agent(read_back(slots[i], pending))
            continue
        if act == "yes" or slots[i]["risk"] == "low":
            i, pending = i + 1, None
        if i == len(slots):
            r.agent(flow["done"])
            r.outcome = "booked"
            return r
        r.agent(slots[i]["ask"])
    return r


# ---------------------------------------------------------------- 4. the read-aloud test

def read_aloud(lines: list[str], max_words: int = 20) -> list[str]:
    problems = []
    for n, line in enumerate(lines, 1):
        parts = [p for p in re.split(r"(?<=[.?!])\s+", line) if p]
        if len(parts) > 2:
            problems.append(f"line {n}: {len(parts)} sentences")
        problems += [f"line {n}: {len(p.split())} words in a sentence"
                     for p in parts if len(p.split()) > max_words]
    return problems


# ---------------------------------------------------------------- report

def load(mode: str) -> tuple[dict, dict]:
    if mode == "mock":
        return book_visit_flow(), callers()
    if mode == "fixture":
        return (json.loads((FIXTURES / "flow.json").read_text()),
                json.loads((FIXTURES / "callers.json").read_text()))
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def report(mode: str) -> str:
    flow, script = load(mode)
    out: list[str] = []
    say = out.append
    say(f"dialogue lab, mode={mode}; evidence class: simulated (scripted callers)")
    say("")
    say(f"1. the dialogue object: {flow['name']}")
    say(f"   {'slot':<9}{'risk':<12}asks")
    for s in flow["slots"]:
        say(f"   {s['name']:<9}{s['risk']:<12}{last_sentence(s['ask'])}")
    say(f"   after {flow['max_failures']} failures of one kind: keypad, text, or a person")
    say("")
    say("2. confirmation by risk")
    for s in flow["slots"][1:]:
        example = read_back(s, "2231") or s["ask"]
        say(f"   {s['risk']:<12}{CONFIRM[s['risk']]}")
        for piece in textwrap.wrap(f"\"{example}\"", 62):
            say(f"   {'':<12}{piece}")
    say("")
    say("3. two designs, five calls (agent turns in brackets)")
    say(f"   {'call':<19}{'v1: one repair line':<26}v2: the catalog")
    repeats = {False: 0, True: 0}
    for name, turns in script.items():
        cells = []
        for catalog in (False, True):
            r = run(flow, turns, catalog)
            repeats[catalog] += r.repeats
            n = sum(1 for who, _ in r.lines if who == "Agent")
            cells.append(f"{r.outcome} ({n})")
        say(f"   {name:<19}{cells[0]:<26}{cells[1]}")
    say(f"   agent lines repeated word for word: v1 {repeats[False]}, v2 {repeats[True]}")
    say("")
    say("4. the read-aloud test: the happy path, as the agent says it")
    r = run(flow, script["happy path"], True)
    agent_lines = [t for who, t in r.lines if who == "Agent"]
    for n, line in enumerate(agent_lines, 1):
        for k, piece in enumerate(textwrap.wrap(line, 70, break_on_hyphens=False)):
            say(f"   {str(n) + '.' if k == 0 else '':<3}{piece}")
    say(f"   problems: {len(read_aloud(agent_lines))} (at most two sentences, 20 words each)")
    return "\n".join(out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("DIALOGUE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"dialogue_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "flow.json").write_text(json.dumps(book_visit_flow(), indent=1))
        (FIXTURES / "callers.json").write_text(json.dumps(callers(), indent=1))
        print("wrote fixtures/flow.json and fixtures/callers.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("DIALOGUE_LAB_MODE", "mock")))
    else:
        run_mode()
