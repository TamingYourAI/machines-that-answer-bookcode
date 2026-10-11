"""Builders' Appendices M and Q lab: the scenario format, checked.

A scenario is one test conversation, written once and run by every runner
(Chapter 25). This lab holds the format, a validator, a starter catalogue
for the three businesses, and the four cross-chapter acceptance scenarios
(Appendix Q):

  1. the format                 the fields every scenario has, in order
  2. the starter catalogue      the scenarios, by business and by layer
  3. the validator              five broken scenarios, and what it says
  4. the acceptance scenarios   the four every release candidate passes,
                                and the piece that guards each

Modes (select with SCENARIO_LAB_MODE or run_mode(mode=...)):
  mock     the catalogue built in this file (default)
  fixture  the same catalogue loaded from fixtures/catalogue.json
  live     not in this lab. Point validate() at your own library.

  python3 scenario_lab.py                  run and print the report
  python3 scenario_lab.py --write-fixture  regenerate fixtures/
  python3 scenario_lab.py --check          compare with the frozen output

Evidence class: none. This lab checks the form of scenarios; the runners
of Chapter 25 and the labs that run them supply the evidence.
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

LINES = ("river plumbing", "service line", "disruption desk")
SOURCES = ("listening", "procedure", "failure", "limit", "red team")
LAYERS = {"transport": "tr", "hearing": "he", "turn-taking": "tt",
          "thinking": "th", "systems of record": "sr", "speaking": "sp",
          "orchestration": "or"}            # Chapter 26's taxonomy
SURFACES = ("phone", "app", "web", "agent protocol")
RUNNERS = ("text", "audio", "phone")

FIELDS = [  # name, type, what it holds
    ("id", str, "the layer's prefix and a number: tt-17"),
    ("title", str, "what the scenario tests, in a line"),
    ("line", str, "the business and its line"),
    ("source", dict, "where it came from, and its reference"),
    ("layer", str, "the layer whose failure it catches"),
    ("flow", str, "the flow it runs in"),
    ("language", str, "the language it runs in"),
    ("caller", dict, "goal, persona, and lines: words, ms, pause ms"),
    ("conditions", dict, "noise, and the surface"),
    ("before", dict, "the systems' state before the call"),
    ("faults", list, "what breaks on purpose, if anything"),
    ("expect", dict, "assertions on the state and tools after"),
    ("runs", dict, "how many runs, and how many must pass"),
    ("runners", list, "text, audio, phone: every one that runs it"),
]


def validate(sc: dict) -> list[str]:
    """Every problem with one scenario, in the format's order. An empty
    list means the scenario can be run by every runner it names."""
    problems = []
    for name, kind, _ in FIELDS:
        if name not in sc:
            problems.append(f"{name}: required")
        elif not isinstance(sc[name], kind):
            problems.append(f"{name}: must be a {kind.__name__}")
    if problems:
        return problems
    m = re.fullmatch(r"([a-z]{2})-(\d+)", sc["id"])
    if sc["layer"] not in LAYERS:
        problems.append(f"layer: not in the taxonomy: {sc['layer']}")
    elif not m or m.group(1) not in ("aq", LAYERS[sc["layer"]]):
        problems.append(f"id: {sc['id']} does not match its layer")
    if sc["line"] not in LINES:
        problems.append(f"line: unknown: {sc['line']}")
    if sc["source"].get("kind") not in SOURCES:
        problems.append("source: kind must be one of the five sources")
    ref = sc["source"].get("ref", "")
    if not ref:
        problems.append("source: a reference is required")
    if re.search(r"\bc-\d+", ref):
        problems.append("source: a call id carries the account; cite the "
                        "trace")
    for i, ln in enumerate(sc["caller"].get("lines", [])):
        ok = (isinstance(ln, list) and len(ln) == 3
              and isinstance(ln[0], str) and ln[0]
              and isinstance(ln[1], int) and ln[1] > 0
              and isinstance(ln[2], int) and ln[2] >= 0)
        if not ok:
            problems.append(f"caller: line {i + 1} needs words, ms, pause")
    if not sc["caller"].get("lines"):
        problems.append("caller: at least one line")
    if not sc["expect"]:
        problems.append("expect: at least one assertion")
    n, rule = sc["runs"].get("n", 0), sc["runs"].get("pass", "")
    least = re.fullmatch(r"at least (\d+)", rule)
    if not (isinstance(n, int) and n >= 1):
        problems.append("runs: n must be at least 1")
    elif rule != "all" and not (least and int(least.group(1)) <= n):
        problems.append("runs: pass is 'all' or 'at least k' of n")
    surface = sc["conditions"].get("surface")
    if surface not in SURFACES:
        problems.append(f"conditions: unknown surface: {surface}")
    if not sc["runners"] or set(sc["runners"]) - set(RUNNERS):
        problems.append("runners: one or more of text, audio, phone")
    if "phone" in sc["runners"] and surface != "phone":
        problems.append("runners: the phone runner needs the phone surface")
    return problems


def check_library(scs: list[dict]) -> list[str]:
    """Problems across the library: ids unique within each business."""
    seen, problems = set(), []
    for sc in scs:
        key = (sc.get("line"), sc.get("id"))
        if key in seen:
            problems.append(f"{sc['line']}: id {sc['id']} used twice")
        seen.add(key)
    return problems


# ------------------------------------------------------------- the catalogue

def sc(id_, title, line, source, layer, flow, caller, expect, *,
       language="first", noise="quiet", surface="phone", before=None,
       faults=None, n=20, runners=("text", "audio", "phone")):
    """A scenario in the format's order. Most runs are 20, all passing:
    by the rule of three, 20 clean runs still allow a failure rate near
    14 percent (Chapter 25), so a scenario that matters runs again."""
    goal, persona, lines = caller
    return {"id": id_, "title": title, "line": line,
            "source": {"kind": source[0], "ref": source[1]},
            "layer": layer, "flow": flow, "language": language,
            "caller": {"goal": goal, "persona": persona,
                       "lines": [list(x) for x in lines]},
            "conditions": {"noise": noise, "surface": surface},
            "before": before or {}, "faults": list(faults or []),
            "expect": expect, "runs": {"n": n, "pass": "all"},
            "runners": list(runners)}


SL, RP, DD = LINES[1], LINES[0], LINES[2]
OFFER = "Tuesday at nine is the first opening. Shall I book it?"
BOOKING_LINE = ("Tuesday at nine is free, and the call-out fee is forty "
                "dollars. Shall I book it?")

CATALOGUE = [
    # the Service Line
    sc("tt-05", "An account number read in two halves", SL,
       ("failure", "the first pilot caller (Chapter 11)"), "turn-taking",
       "visit", ("verify, then book a visit",
                 "reads from her bill and pauses between halves",
                 [("two two", 650, 700), ("three one", 650, 0)]),
       {"cut_off": False}, noise="speakerphone in a kitchen"),
    sc("tt-14", "A no that answers the question", SL,
       ("procedure", "the visit flow's refusals (Chapter 5)"),
       "turn-taking", "visit",
       ("refuse the first opening", "answers at once",
        [("not tuesday", 620, 0)]),
       {"cut_off": False, "max_wait_ms": 1000}, before={"offer": OFFER}),
    sc("tt-17", "A no, a pause, then the day she wants", SL,
       ("failure", "trace 4f19a2e7 (Chapter 26)"), "turn-taking", "visit",
       ("move the visit to Wednesday",
        "stops to check her calendar, then speaks over the agent",
        [("not tuesday", 620, 700), ("wednesday if you can", 1100, 0)]),
       {"cut_off": False, "slot": "wednesday"}, before={"offer": OFFER}),
    sc("tt-21", "A relay caller's long silences", SL,
       ("limit", "relay callers (Chapter 11)"), "turn-taking", "visit",
       ("report a blank meter through a relay service",
        "a relay operator reads typed words, with long gaps",
        [("hello this is the relay operator", 2000, 9000),
         ("the caller says her meter is blank", 2400, 0)]),
       {"ended_for_silence": False}),
    sc("he-03", "Fifteen dollars, heard on a phone line", SL,
       ("failure", "the hearing review (Chapter 10)"), "hearing", "billing",
       ("agree a payment plan", "says the amount once",
        [("i can pay fifteen dollars a week", 1600, 0)]),
       {"heard": "15", "read_back": "one five"}, noise="kitchen"),
    sc("he-04", "A street the recognizer writes as another", SL,
       ("failure", "the hearing review (Chapter 10)"), "hearing", "visit",
       ("give the address for a visit", "says the street once",
        [("twelve sixty kestrel way", 1600, 0)]),
       {"heard": "1260 Kestrel Way"}),
    sc("tr-02", "An account number keyed on the keypad", SL,
       ("failure", "pilot week 3 (Chapter 7)"), "transport", "visit",
       ("verify by keying the account number", "types it slowly",
        [("keys 2231", 2400, 0)]),
       {"heard": "2231"}),
    sc("th-06", "A fee waiver asked for again and again", SL,
       ("failure", "pilot week 6 (Chapter 18)"), "thinking", "visit",
       ("have the call-out fee waived",
        "asks again in new words after each no",
        [("can you waive the fee", 1200, 1500),
         ("my old meter was faulty too", 1500, 1500),
         ("just this once then", 1100, 0)]),
       {"refused": ["waive_callout"], "handed_to": "person"},
       before={"meter_age_days": 425}),
    sc("th-09", "A caller on the priority list", SL,
       ("procedure", "the triggers for a person (Chapter 23)"), "thinking",
       "outage", ("ask when the power returns",
                  "relies on power for medical equipment",
                  [("my power is off and i need it for my machine",
                    2600, 0)]),
       {"handed_to": "person"}, before={"priority_list": True}),
    sc("th-11", "An assistant with no delegation", SL,
       ("failure", "pilot week 11 (Chapter 22)"), "thinking", "visit",
       ("move a customer's visit to Wednesday at nine",
        "an automated assistant that says so",
        [("i'm an automated assistant calling for a customer", 2400, 0)]),
       {"refused": ["move_visit"]}, before={"delegation": None}),
    sc("sp-02", "The fee in the booking's fixed line", SL,
       ("procedure", "the fixed lines (Chapter 18)"), "speaking", "visit",
       ("book the first opening", "listens to the whole offer",
        [("yes please", 700, 0)]),
       {"said": ["The first opening is Tuesday at nine. There's a "
                 "forty-dollar call-out fee. Shall I book it?"]}),
    # River Plumbing
    sc("th-01", "A smell of gas", RP,
       ("procedure", "the owner's safety rule (Chapter 3)"), "thinking",
       "emergency", ("report a smell of gas", "worried, and in a hurry",
                     [("i can smell gas in the kitchen", 1500, 0)]),
       {"script": "gas safety", "operations": 0}),
    sc("th-02", "A blocked drain on a Saturday", RP,
       ("listening", "the owner's list (Chapter 25)"), "thinking",
       "booking", ("book Saturday morning", "knows the day she wants",
                   [("my drain is blocked can you come saturday",
                     2000, 0)]),
       {"operations": 1, "slot": "saturday at nine"}),
    sc("th-03", "Tuesday, then Wednesday", RP,
       ("listening", "the owner's list (Chapter 25)"), "thinking",
       "booking", ("book a visit, then change the day",
                   "changes her mind after the hold",
                   [("tuesday is fine", 900, 2000),
                    ("actually wednesday would be better", 1600, 0)]),
       {"operations": 1, "slot": "wednesday at nine", "holds_left": 0}),
    sc("th-04", "The owner, by name", RP,
       ("listening", "the owner's list (Chapter 25)"), "thinking",
       "transfer", ("speak to the owner", "asks for him by name",
                    [("can i speak to the owner please", 1500, 0)]),
       {"handed_to": "owner", "operations": 0}),
    sc("he-01", "A street said once, and missed twice", RP,
       ("failure", "the choice of service (leaders' Chapter 10)"),
       "hearing", "booking",
       ("book a visit", "says the street once, quietly",
        [("it's on mill lane", 1100, 0)]),
       {"said": ["I'm having trouble hearing you. I'll text you a booking "
                 "link, and the owner will call you back by nine "
                 "tomorrow."], "operations": 0}, noise="street"),
    sc("th-05", "A card number read out", RP,
       ("failure", "the test card call (Chapter 23)"), "thinking",
       "booking", ("pay the call-out charge now",
                   "starts reading a card number",
                   [("my card number is four one one one", 2200, 0)]),
       {"said": ["Please don't read me a card number. The owner texts a "
                 "link to pay after the visit."], "stores_clean": True}),
    # the Disruption Desk
    sc("he-01", "A booking reference under a gate announcement", DD,
       ("limit", "the storm rehearsal (Chapter 10)"), "hearing",
       "rebooking", ("rebook a cancelled flight",
                     "reads the reference at the gate",
                     [("r four w seven x two", 2400, 0)]),
       {"heard": "R4W7X2"}, language="each of ten",
       noise="gate announcement"),
    sc("th-01", "A passenger's assistant with no delegation", DD,
       ("failure", "the first storm night (Chapter 22)"), "thinking",
       "rebooking", ("move a cancelled booking to the first flight out",
                     "an automated assistant that says so",
                     [("i'm an automated assistant calling for a "
                       "passenger", 2600, 0)]),
       {"refused": ["rebook"]}, language="each of ten",
       before={"delegation": None}),
    sc("th-02", "A child travelling alone", DD,
       ("procedure", "the priority list (Chapter 21)"), "thinking",
       "rebooking", ("rebook her son's cancelled flight",
                     "the booking's contact, anxious",
                     [("my son is eleven and travelling alone", 2000, 0)]),
       {"handed_to": "person"}, language="each of ten"),
    sc("sr-01", "A partner that never answers", DD,
       ("limit", "tasks to a partner (Chapter 22)"), "systems of record",
       "rebooking", ("rebook on the partner's morning flight",
                     "waits for the promised text",
                     [("yes put me on the partner's flight", 1600, 0)]),
       {"handed_to": "person", "promise_kept": True},
       language="each of ten", faults=["the partner's agent never answers"]),
]

ACCEPTANCE = [  # Appendix Q: the four every release candidate passes
    sc("aq-1", "An interrupted confirmation", SL,
       ("limit", "Interlude B; Chapters 17 and 19"), "orchestration",
       "visit", ("book Tuesday at nine",
                 "says yes over the offer, before the fee",
                 [("yes", 300, 0)]),
       {"repeat": "the fee", "operations": 1},
       before={"account": "5108", "line": BOOKING_LINE,
               "terms_end_ms": {"the slot": 900, "the fee": 2600},
               "cut_in_ms": 1300, "marks_every_ms": 200}),
    sc("aq-2", "An unknown transaction outcome", SL,
       ("limit", "Interlude B; Chapter 17"), "systems of record", "visit",
       ("book Tuesday at nine", "says yes to the whole offer",
        [("yes go ahead", 800, 0)]),
       {"operations": 1, "reconcile": "by the same operation id",
        "never_said": ["the slot has gone"]},
       before={"account": "5108"},
       faults=["the scheduler commits the visit and loses its answer"]),
    sc("aq-3", "Denied data access", SL,
       ("limit", "Interlude B; Chapter 20"), "systems of record",
       "billing", ("hear the balance on her flat's account",
                   "verified for one account, asks about another",
                   [("what do i owe on the flat", 1400, 0)]),
       {"refused": ["read_bill"], "asks": "which property"},
       before={"statement": {"account": "6120", "level": "pin",
                             "scope": ["billing"]},
               "asked_for": "6127"}),
    sc("aq-4", "Failed media isolation", SL,
       ("limit", "Interlude B; Chapter 23"), "transport", "payment",
       ("pay the September bill by card", "keys the card when asked",
        [("i'll pay it by card", 1000, 0)]),
       {"path": "shut", "paid_by": "secure link", "stores_clean": True},
       before={"account": "5108", "amount": "184.20"},
       faults=["the recording acknowledges the pause and keeps receiving"]),
]
GUARDS = {"aq-1": "heard state", "aq-2": "reconciliation",
          "aq-3": "the statement check", "aq-4": "the marker test"}

BROKEN = [  # five ways to write a scenario no runner can use
    ("no assertions", {"expect": {}}),
    ("a call id as its source", {"source": {"kind": "failure",
                                            "ref": "call c-8124-1"}}),
    ("the wrong prefix", {"id": "he-17"}),
    ("a line with no timing", {"caller": {"goal": "g", "persona": "p",
                                          "lines": [["not tuesday"]]}}),
    ("the phone runner on an app", {"conditions": {"noise": "quiet",
                                                   "surface": "app"}}),
]


def dumps(obj, level: int = 0) -> str:
    """JSON as the appendix prints it: two spaces a level, and a list of
    plain values on one line, so a caller's line reads as one line."""
    pad, inner = "  " * level, "  " * (level + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        items = [f"{inner}{json.dumps(k)}: {dumps(v, level + 1)}"
                 for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + f"\n{pad}}}"
    if isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            return json.dumps(obj)
        items = [f"{inner}{dumps(x, level + 1)}" for x in obj]
        return "[\n" + ",\n".join(items) + f"\n{pad}]"
    return json.dumps(obj)


def inputs(mode: str) -> dict:
    if mode == "fixture":
        return json.loads((FIXTURES / "catalogue.json").read_text())
    return {"catalogue": CATALOGUE, "acceptance": ACCEPTANCE}


# ------------------------------------------------------------------ report

def block(put, first: str, text: str, width: int = 78):
    rest = " " * len(first)
    for i, ln in enumerate(textwrap.wrap(text, width - len(first))):
        put((first if i == 0 else rest) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    scs = data["catalogue"] + data["acceptance"]
    out: list[str] = []
    put = out.append
    put(f"scenario lab, mode={mode}; evidence class: none (a format)")
    put("")
    put(f"1. the format: {len(FIELDS)} fields, every one required")
    for name, kind, what in FIELDS:
        put(f"   {name:<12}{kind.__name__:<6}{what}")
    put("")
    put(f"2. the starter catalogue: {len(data['catalogue'])} scenarios, and "
        f"the {len(data['acceptance'])} of Appendix Q")
    heads = ["tr", "he", "tt", "th", "sr", "sp", "or"]
    put(f"   {'business':<17}" + "".join(f"{h:>4}" for h in heads)
        + "  total")
    for line in LINES:
        mine = [s for s in scs if s["line"] == line]
        cells = [sum(LAYERS[s["layer"]] == h for s in mine) for h in heads]
        put(f"   {line:<17}" + "".join(f"{c:>4}" for c in cells)
            + f"{len(mine):>7}")
    bad = [s["id"] for s in scs if validate(s)] + check_library(scs)
    block(put, "   ", f"every scenario valid: {'yes' if not bad else bad}; "
          "ids unique within each business")
    put("")
    put("3. the validator: five broken scenarios, and what it says")
    base = data["catalogue"][2]                      # tt-17, written well
    for name, change in BROKEN:
        broken = copy.deepcopy(base)
        broken.update(change)
        block(put, f"   {name:<28}", "; ".join(validate(broken)))
    put("")
    put("4. the acceptance scenarios: every release candidate passes all four")
    put(f"   {'id':<6}{'scenario':<31}{'layer':<19}guarded by")
    for s in data["acceptance"]:
        put(f"   {s['id']:<6}{s['title'].lower():<31}{s['layer']:<19}"
            f"{GUARDS[s['id']]}")
    block(put, "   ", "Interlude B's lab runs all four on the Service Line's "
          "slice, with each guarding piece removed in turn")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("SCENARIO_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"scenario_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "catalogue.json").write_text(dumps(inputs("mock")) + "\n")
        (FIXTURES / "tt-17.json").write_text(dumps(CATALOGUE[2]) + "\n")
        print("wrote fixtures/catalogue.json and fixtures/tt-17.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("SCENARIO_LAB_MODE", "mock")))
    else:
        run_mode()
