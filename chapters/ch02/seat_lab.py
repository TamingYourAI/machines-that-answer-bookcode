"""Builders' Chapter 2 lab: where the agent sits, and the contracts the seat creates.

Four small steps:

  1. the four seats           what each seat owns and gives up, as data
  2. the Service Line's must   which seats meet the requirements, and why the others fail
  3. the design checker        a written seat design, checked against the contracts; one sound
                               design and one mixed-seat design
  4. one call, end to end      the recurring caller's call as the business sees it, with the
                               steps the seat keeps, checked against both designs

Modes (select with SEAT_LAB_MODE or run(mode=...)):
  mock     the designs are built in this file (default; runs anywhere)
  fixture  the designs and the call are loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point load_designs() at your own seat design, written in the same
           schema, and the checker reports what it breaks.

Other entry points:
  python3 seat_lab.py                  run in the selected mode and print the report
  python3 seat_lab.py --write-fixture  regenerate fixtures/ from the data here
  python3 seat_lab.py --check          compare with the frozen output in outputs/

Evidence class: none applies. This lab measures nothing; it checks written designs against
rules. The seat properties are typical of each seat as the chapter describes them; your
platform's documentation, and a test call, are what decide them for you.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "designs.json"
CALL_FIXTURE = HERE / "fixtures" / "call.json"
OUTPUTS = HERE / "outputs"


# ---------------------------------------------------------------- 1. the four seats

@dataclass(frozen=True)
class Seat:
    name: str
    number: str        # who owns the phone number: "platform" or "you"
    recorder: str      # who owns the recording
    barge_in: str      # control of interruptions: "full", "limited", or "none"
    raw_audio: bool    # does the agent get the caller's audio itself?
    attached_data: bool  # can context travel with a transfer?
    desk: str          # whose desk a person picks up on: "platform" or "yours"


SEATS = (
    Seat("front of the ACD", "platform", "platform", "full", True, True, "platform"),
    Seat("inside the IVR", "platform", "platform", "limited", True, True, "platform"),
    Seat("CPaaS-native", "you", "you", "full", True, False, "yours"),
    Seat("overlay", "platform", "platform", "none", False, True, "platform"),
)


# ---------------------------------------------------------------- 2. the Service Line's must

MUST = (
    ("keeps the published number", lambda s: s.number == "platform"),
    ("keeps the one recorder", lambda s: s.recorder == "platform"),
    ("controls interruptions", lambda s: s.barge_in == "full"),
    ("hears the caller's own audio", lambda s: s.raw_audio),
    ("carries context into a transfer", lambda s: s.attached_data),
    ("hands off to the existing desk", lambda s: s.desk == "platform"),
)


def evaluate(seat: Seat) -> list[tuple[str, bool]]:
    return [(label, rule(seat)) for label, rule in MUST]


# ---------------------------------------------------------------- 3. the design checker

SCREEN_POP = ("account", "intent", "verified level", "last two turns", "ticket id")
CONTRACTS = (
    ("one number and one recorder", "Ch. 7, 23"),
    ("five screen-pop fields on every transfer", "Ch. 21"),
    ("a disposition back from the desk", "Ch. 21, 26"),
    ("after-hours routing, written down", "Ch. 21"),
    ("the number porting lead time, known before launch", "Ch. 7"),
)


def sound_design() -> dict:
    """The Service Line in front of the ACD, written down as a design."""
    return {
        "name": "Service Line, front of the ACD",
        "seat": "front of the ACD",
        "numbers": ["the published service number"],
        "recorders": ["the platform recorder"],
        "transfer": {"method": "back into the billing and outage queues",
                     "attached": list(SCREEN_POP)},
        "disposition_back": True,
        "after_hours": "agent answers; callbacks for anything that needs a person",
        "porting_weeks": 0,
    }


def mixed_design() -> dict:
    """A shortcut: a new number for the agent, its own recorder, a cold transfer."""
    return {
        "name": "Service Line, mixed seat",
        "seat": "CPaaS-native",
        "numbers": ["the published service number", "a new agent number"],
        "recorders": ["the platform recorder", "the agent's own recorder"],
        "transfer": {"method": "a forward to the main number", "attached": ["intent"]},
        "disposition_back": False,
        "after_hours": "",
        "porting_weeks": None,
    }


def load_designs(mode: str) -> list[dict]:
    if mode == "mock":
        return [sound_design(), mixed_design()]
    if mode == "fixture":
        return json.loads(FIXTURE.read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def check_design(d: dict) -> list[str]:
    """Every contract a later chapter relies on, checked in one place."""
    problems = []
    if len(d["numbers"]) > 1:
        problems.append("a second number: callers and reports split in two")
    if len(d["recorders"]) > 1:
        problems.append("a second recording: two copies of sensitive audio")
    missing = [f for f in SCREEN_POP if f not in d["transfer"]["attached"]]
    if missing:
        problems.append(f"screen-pop fields missing ({len(missing)} of {len(SCREEN_POP)}):\n"
                        "       " + ", ".join(missing))
    if not d["disposition_back"]:
        problems.append("no disposition comes back from the desk")
    if not d["after_hours"]:
        problems.append("after-hours routing not written down")
    if d["porting_weeks"] is None:
        problems.append("number porting lead time unknown")
    return problems


# ---------------------------------------------------------------- 4. one call, end to end

SEAT_RULES = {  # what a step needs from the seat design
    "one number": lambda d: len(d["numbers"]) == 1,
    "front of the ACD": lambda d: d["seat"] == "front of the ACD",
    "one recorder": lambda d: len(d["recorders"]) == 1,
    "any seat": lambda d: True,
    "the platform's reports": lambda d: d["seat"] != "CPaaS-native",
    "five fields": lambda d: all(f in d["transfer"]["attached"] for f in SCREEN_POP),
}


def the_call() -> list[list]:
    """The recurring caller's call as the business sees it. Times are the chapter's story;
    the last field names the seat rule a step relies on (None: a later Part builds it)."""
    return [
        ["20:10:00", "carrier", "she dials the published service number", "one number"],
        ["20:10:00", "platform", "the ACD gives the agent the call, before any queue",
         "front of the ACD"],
        ["20:10:01", "platform", "the one recorder starts, and its notice plays",
         "one recorder"],
        ["20:10:01", "agent", "her number finds account 2231: a lookup, not proof",
         "any seat"],
        ["20:10:06", "agent", "\"This is the utility's automated assistant. How can I help?\"",
         None],
        ["20:11:40", "systems", "her record is read, and a fault ticket opened",
         "any seat"],
        ["20:12:10", "systems", "a photo link goes by text; the photo lands at 20:13", None],
        ["20:14:42", "systems", "the visit is booked for Tuesday at nine", None],
        ["20:15:00", "systems", "the confirmation text goes", None],
        ["20:15:20", "platform", "the call ends; the agent's disposition, \"visit booked by "
         "the agent,\" counts as a completed call in the platform's reports",
         "the platform's reports"],
        ["", "desk", "had she asked for a person: back into the queue, with five fields and "
         "a whisper", "five fields"],
    ]


def load_call(mode: str) -> list[list]:
    if mode == "mock":
        return the_call()
    if mode == "fixture":
        return json.loads(CALL_FIXTURE.read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def kept(design: dict, call: list[list]) -> tuple[int, int]:
    """How many of the seat's steps a design keeps, out of all of them."""
    steps = [rule for *_, rule in call if rule]
    return sum(SEAT_RULES[rule](design) for rule in steps), len(steps)


# ---------------------------------------------------------------- report

def report(mode: str) -> str:
    lines: list[str] = []
    say = lines.append
    say(f"seat lab, mode={mode}; a design check: no measurement, no evidence class")
    say("")
    say("1. the four seats")
    say(f"   {'seat':<18}{'number':<10}{'recorder':<10}{'barge-in':<10}"
        f"{'audio':<7}{'context':<9}desk")
    for s in SEATS:
        say(f"   {s.name:<18}{s.number:<10}{s.recorder:<10}{s.barge_in:<10}"
            f"{'yes' if s.raw_audio else 'no':<7}{'yes' if s.attached_data else 'no':<9}"
            f"{s.desk}")
    say("")
    say("2. the Service Line's requirements, seat by seat")
    for s in SEATS:
        failed = [label for label, ok in evaluate(s) if not ok]
        if not failed:
            say(f"   {s.name:<18}meets all six")
            continue
        say(f"   {s.name:<18}fails {len(failed)} of {len(MUST)}:")
        for label in failed:
            say(f"     - {label}")
    say("")
    say("3. the design checker")
    for d in load_designs(mode):
        problems = check_design(d)
        say(f"   {d['name']}: {len(problems)} problem"
            f"{'' if len(problems) == 1 else 's'}")
        for p in problems:
            say(f"     - {p}")
    say("")
    say("contracts the chosen seat creates, relied on in later chapters:")
    for contract, chapters in CONTRACTS:
        say(f"   {contract:<52}{chapters}")
    say("")
    call = load_call(mode)
    say("4. one call, end to end: the recurring caller, as the business sees it")
    say(f"   {'time':<10}  {'where':<10}what happens (* kept by the seat, Part I)")
    for time, where, what, rule in call:
        text = textwrap.wrap(what, 53)
        say(f"   {time:<10}{'*' if rule else ' '} {where:<10}{text[0]}")
        for more in text[1:]:
            say(f"   {'':<10}  {'':<10}{more}")
    for d in load_designs(mode):
        ok, of = kept(d, call)
        say(f"   {d['name']}: keeps {ok} of the {of} starred steps")
    return "\n".join(lines) + "\n"


def run(mode: str | None = None) -> str:
    mode = mode or os.environ.get("SEAT_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"seat_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps([sound_design(), mixed_design()], indent=1))
        CALL_FIXTURE.write_text(json.dumps(the_call(), indent=1))
        print(f"wrote {FIXTURE.relative_to(HERE)} and {CALL_FIXTURE.relative_to(HERE)}")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("SEAT_LAB_MODE", "mock")))
    else:
        run()
