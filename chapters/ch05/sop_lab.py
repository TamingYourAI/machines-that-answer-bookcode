"""Builders' Chapter 5 lab: which calls first, then the procedure compiled into a flow.

Five steps:

  1. call drivers     a month of the Service Line's call reasons, ranked by volume times fit,
                      with risk as a gate: first, next, later, spike, never
  2. the SOP compiler the written procedure and the desk's observed practice, compiled into
                      building blocks with every system touch marked; drift is flagged
  3. variations       inbound status, booking, and an outbound reminder, as block sequences
  4. outbound gate    River Plumbing's reminder list checked for consent, opt-out, and the
                      local calling window before any call is placed
  5. one call         the recurring caller's call, block by block, checked against the
                      compiled procedure's order

Modes (select with SOP_LAB_MODE or run_mode(mode=...)):
  mock     the data is built in this file (default)
  fixture  it is loaded from fixtures/ (committed; same schema)
  live     not in this lab. Export your platform's call reasons and your SOPs in the
           fixtures' schema and run the same steps.

  python3 sop_lab.py                  run and print the report
  python3 sop_lab.py --write-fixture  regenerate fixtures/ from the data here
  python3 sop_lab.py --check          compare with the frozen output in outputs/

Evidence class: none for the ranking and compiler (they are methods applied to composite
data); the call volumes are the Service Line's composite planning figures.
"""
from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ---------------------------------------------------------------- 1. call drivers

def drivers() -> list[dict]:
    """A month of call reasons. fit: the share the agent could finish, as judged from fifty
    coded calls; risk: low, medium, high; served: what answers the call today."""
    return [
        {"reason": "outage status", "calls": 40000, "fit": 0.2, "risk": "low",
         "served": "menu message", "spike": True},
        {"reason": "payment", "calls": 35000, "fit": 0.7, "risk": "high",
         "served": "desk"},
        {"reason": "billing question", "calls": 30000, "fit": 0.6, "risk": "medium",
         "served": "desk"},
        {"reason": "moving home", "calls": 25000, "fit": 0.4, "risk": "medium",
         "served": "desk"},
        {"reason": "technician visit", "calls": 20000, "fit": 0.7, "risk": "medium",
         "served": "desk"},
        {"reason": "meter reading", "calls": 15000, "fit": 0.8, "risk": "low",
         "served": "desk"},
        {"reason": "complaint", "calls": 8000, "fit": 0.0, "risk": "never",
         "served": "desk"},
        {"reason": "bill dispute", "calls": 6000, "fit": 0.0, "risk": "never",
         "served": "desk"},
        {"reason": "bereavement", "calls": 1500, "fit": 0.0, "risk": "never",
         "served": "desk"},
        {"reason": "other", "calls": 19500, "fit": 0.0, "risk": "unknown",
         "served": "desk"},
    ]


def rank(rows: list[dict], first: int = 2) -> list[tuple[dict, int, str]]:
    """Score = calls the agent could finish. Risk gates the score; it never adds to it."""
    out = []
    for r in rows:
        score = round(r["calls"] * r["fit"])
        if r["risk"] == "never":
            decision = "never: the counter-atlas"
        elif r["risk"] == "unknown":
            decision = "listen: code more calls"
        elif r["risk"] == "high":
            decision = "later: after its controls"
        elif r.get("spike"):
            decision = "spike variant only"
        else:
            decision = ""
        out.append((r, score, decision))
    open_ = sorted((x for x in out if not x[2]), key=lambda x: -x[1])
    for n, (r, score, _) in enumerate(open_):
        idx = out.index((r, score, ""))
        out[idx] = (r, score, "first" if n < first else "next")
    return sorted(out, key=lambda x: -x[1])


# ---------------------------------------------------------------- 2. the SOP compiler

def sop_document() -> list[str]:
    """The written procedure, as the operations team wrote it."""
    return [
        "1. Answer the call and give your name.",
        "2. Verify the customer with the account number and the first line of the address.",
        "3. Ask what the meter shows and record it on a fault ticket.",
        "4. If the customer smells gas, read the gas safety script and transfer to the "
        "emergency team.",
        "5. Offer the first available visit and state the call-out fee.",
        "6. Book the visit when the customer agrees.",
        "7. Send the confirmation text.",
        "8. Close the call and set the disposition.",
    ]


def sop_practice() -> list[str]:
    """What the desk actually does, from a day of sitting beside it."""
    return [
        "2a. Check the outage map for the address; if there is an outage, give the "
        "restoration time and do not book.",
        "5a. If the meter was replaced in the last 30 days, ask a supervisor to waive the "
        "call-out fee.",
    ]


BLOCKS = [  # (building block, words that signal it), checked in this order
    ("escalate", ("transfer", "supervisor")),
    ("greet", ("answer the call",)),
    ("identify", ("verify the customer",)),
    ("verify", ("check the", "confirm the")),
    ("capture", ("ask what", "record it")),
    ("collect", ("offer",)),
    ("act", ("book the",)),
    ("confirm", ("send the confirmation",)),
    ("close", ("close the call",)),
]
TOUCHES = [  # (system touch, words that signal it)
    ("read crm", ("account number",)),
    ("read outage map", ("outage map",)),
    ("write ticket", ("fault ticket",)),
    ("read calendar", ("first available",)),
    ("write booking", ("book the visit",)),
    ("write text", ("confirmation text",)),
    ("write disposition", ("disposition",)),
    ("human", ("transfer", "supervisor")),
]


def classify(step: str, table: list) -> str:
    low = step.lower()
    return next((name for name, keys in table if any(k in low for k in keys)), "-")


def compile_sop(document: list[str], practice: list[str]) -> list[dict]:
    """Each step becomes a block with its system touches; practice not in the document is
    drift, inserted where the desk does it and flagged."""
    steps = [(s, "document") for s in document] + [(s, "practice") for s in practice]
    def order(item):
        num = re.match(r"(\d+)([a-z]?)", item[0])
        return int(num.group(1)), num.group(2)
    compiled = []
    for text, source in sorted(steps, key=order):
        compiled.append({"step": text.split(".")[0], "block": classify(text, BLOCKS),
                         "touch": classify(text, TOUCHES), "source": source,
                         "safety": "gas" in text.lower()})
    return compiled


# ---------------------------------------------------------------- 3. variations

VARIATIONS = {
    "inbound status": ["greet", "identify", "act: read", "close"],
    "booking": ["greet", "identify", "verify", "capture", "collect", "act", "confirm",
                "close"],
    "outbound reminder": ["verify who answered", "confirm: keep or change", "act",
                          "close"],
}


# ---------------------------------------------------------------- 4. outbound gate

def reminder_list() -> list[dict]:
    """River Plumbing's reminder queue for tomorrow's visits. local is when the dialer
    would place each call, at the called party's location; the queue ran late."""
    return [
        {"to": "555 0142", "consent": "booking call", "opted_out": False, "local": "18:05"},
        {"to": "555 0177", "consent": "booking call", "opted_out": False, "local": "18:12"},
        {"to": "555 0118", "consent": "web form", "opted_out": False, "local": "21:05"},
        {"to": "555 0134", "consent": None, "opted_out": False, "local": "18:20"},
        {"to": "555 0156", "consent": "booking call", "opted_out": True, "local": "18:26"},
        {"to": "555 0171", "consent": "booking call", "opted_out": False, "local": "07:40"},
    ]


def may_call(c: dict, start: str = "08:00", end: str = "21:00") -> str:
    """Asked before every outbound call; the dialer never decides this."""
    if c["opted_out"]:
        return "skip: opted out"
    if not c["consent"]:
        return "skip: no consent on record"
    if not start <= c["local"] < end:
        return f"defer: {c['local']} is outside {start} to {end} local"
    return "call now"


# ---------------------------------------------------------------- 5. one call, end to end

def the_call() -> dict:
    """The recurring caller's call, block by block. Times are the chapter's story. The last
    field says whether Part II designed the step: a line from the brief or the dialogue
    object, or a block of the compiled procedure."""
    return {"steps": [
        ["20:10:06", "greet", "\"This is the utility's automated assistant. How can I "
         "help?\"", True],
        ["20:10:09", "greet", "she says her meter's display has gone blank", False],
        ["20:10:12", "identify", "\"To find your account, what's the number on your "
         "bill?\"", True],
        ["20:10:16", "identify", "she asks for a moment; the agent holds, checking in "
         "every 30 seconds", True],
        ["20:11:40", "identify", "\"That's two two, three one. Is that right?\"", True],
        ["20:11:48", "identify", "\"Is the visit for fourteen Alder Road?\"", True],
        ["20:11:53", "verify", "no outage at fourteen Alder Road; nothing is said", True],
        ["20:11:55", "capture", "her first sentence goes on a fault ticket; nothing is "
         "asked twice", True],
        ["20:12:10", "capture", "\"I've texted a link to the number you're calling from, "
         "for a photo of the meter.\"", True],
        ["20:13:02", "capture", "the photo lands on the fault ticket", False],
        ["20:13:08", "capture", "\"Thanks, that's come through. Is the power on in the "
         "rest of the house?\"", True],
        ["20:14:20", "capture", "she checks the lights: it is", False],
        ["20:14:30", "collect", "\"The first opening is Tuesday at nine. There's a "
         "forty-dollar call-out fee. Shall I book it?\"", True],
        ["20:14:40", "act", "\"Yes, go ahead.\" The booking is made", False],
        ["20:14:42", "confirm", "\"You're booked for Tuesday at nine.\"", True],
        ["20:15:00", "confirm", "the confirmation text goes", False],
        ["20:15:20", "close", "the disposition: visit booked by the agent", False]],
        "not_reached": {"4": "no gas smell", "5a": "the meter is two years old"}}


def in_order(steps: list[list], compiled: list[dict]) -> bool:
    """The call's blocks follow the compiled procedure, leaving out escalations."""
    blocks = [b for n, (_, b, *_) in enumerate(steps) if n == 0 or steps[n - 1][1] != b]
    return blocks == [c["block"] for c in compiled if c["block"] != "escalate"]


# ---------------------------------------------------------------- report

def load(mode: str):
    if mode == "mock":
        return drivers(), sop_document(), sop_practice(), reminder_list(), the_call()
    if mode == "fixture":
        return tuple(json.loads((FIXTURES / f"{n}.json").read_text())
                     for n in ("drivers", "sop_document", "sop_practice", "reminders",
                               "call"))
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def report(mode: str) -> str:
    rows, document, practice, reminders, call = load(mode)
    out: list[str] = []
    say = out.append
    say(f"sop lab, mode={mode}; composite call volumes; methods, not measurements")
    say("")
    total = sum(r["calls"] for r in rows)
    say(f"1. call drivers: {total:,} calls a month, ranked by calls the agent could finish")
    say(f"   {'reason':<18}{'calls':>7}{'fit':>6}{'score':>8}  decision")
    for r, score, decision in rank(rows):
        say(f"   {r['reason']:<18}{r['calls']:>7,}{r['fit']:>6.1f}{score:>8,}  {decision}")
    say("")
    compiled = compile_sop(document, practice)
    say("2. the SOP compiled: meter fault, book a technician visit")
    say(f"   {'step':<6}{'block':<10}{'touch':<19}source")
    for c in compiled:
        flag = "  <- drift: not in the document" if c["source"] == "practice" else ""
        say(f"   {c['step']:<6}{c['block']:<10}{c['touch']:<19}{c['source']}{flag}")
    reads = sum(c["touch"].startswith("read") for c in compiled)
    writes = sum(c["touch"].startswith("write") for c in compiled)
    humans = sum(c["touch"] == "human" for c in compiled)
    say(f"   touches: {reads} reads, {writes} writes, {humans} human steps; "
        f"drift: {len(practice)} steps")
    say("")
    say("3. variations: the same blocks in different orders")
    for name, seq in VARIATIONS.items():
        lines = textwrap.wrap(" > ".join(seq), 56)
        say(f"   {name:<19}{lines[0]}")
        for more in lines[1:]:
            say(f"   {'':<19}{more}")
    say("")
    say("4. outbound gate: River Plumbing's reminder queue for tomorrow's visits")
    for c in reminders:
        say(f"   {c['to']:<10}{may_call(c)}")
    calls = sum(may_call(c) == "call now" for c in reminders)
    say(f"   {calls} of {len(reminders)} may be called now")
    say("")
    say("5. one call, end to end: the recurring caller, block by block")
    say(f"   {'time':<10}  {'block':<10}what she hears, or what happens (* Part II)")
    for time, block, what, designed in call["steps"]:
        text = textwrap.wrap(what, 53)
        say(f"   {time:<10}{'*' if designed else ' '} {block:<10}{text[0]}")
        for more in text[1:]:
            say(f"   {'':<10}  {'':<10}{more}")
    say(f"   the blocks follow the compiled order: "
        f"{'yes' if in_order(call['steps'], compiled) else 'no'}")
    skipped = "; ".join(f"{k} ({why})" for k, why in call["not_reached"].items())
    say(f"   escalations not reached: {skipped}")
    return "\n".join(out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("SOP_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"sop_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        for name, data in (("drivers", drivers()), ("sop_document", sop_document()),
                           ("sop_practice", sop_practice()), ("reminders", reminder_list()),
                           ("call", the_call())):
            (FIXTURES / f"{name}.json").write_text(json.dumps(data, indent=1))
        print("wrote fixtures/drivers, sop_document, sop_practice, reminders, call (.json)")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("SOP_LAB_MODE", "mock")))
    else:
        run_mode()
