"""Builders' Chapter 21 lab: handoff to people.

Four steps:

  1. the handoff record    what the desk sees when a call arrives: one
                           schema for every transfer, checked
  2. the loop finder       the contact center's routing rules as a graph,
                           searched for a way back to the agent
  3. the truthful queue    a storm evening, minute by minute: the old
                           overflow rule against a stated wait and a
                           callback kept on time
  4. verification carried  what the desk accepts from the agent, by age
                           and by the next action

Modes (select with HANDOFF_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Export your platform's routing rules into
           step 2's schema, and a real evening's queue into step 3's.

  python3 handoff_lab.py                  run and print the report
  python3 handoff_lab.py --write-fixture  regenerate fixtures/
  python3 handoff_lab.py --check          compare with the frozen output

Evidence class: simulated for the storm evening (the arrivals, the desk's
capacity, and callers' patience are stand-ins); none for the checks.
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


# ------------------------------------------------ 1. the handoff record

FIELDS = ("account", "intent", "verified", "last two turns", "ticket id")


def problems(record: dict, whisper_words: int = 15) -> list[str]:
    """What stops a person from carrying on without asking again."""
    out = [f"missing: {f}" for f in FIELDS if not record.get(f)]
    v = record.get("verified", "")
    if v and " at " not in v:
        out.append("verified, but not how or when")
    if record.get("intent", "").count("_"):
        out.append("intent is a code, not words a person reads")
    words = len(record.get("whisper", "").split())
    if words > whisper_words:
        out.append(f"whisper of {words} words (at most {whisper_words})")
    return out


# ------------------------------------------------ 2. the loop finder

def loops(routes: dict, start: str) -> list[list[str]]:
    """Every path from start that comes back to it: a caller's loop."""
    found, stack = [], [(start, [start])]
    while stack:
        node, path = stack.pop()
        for nxt, _ in routes.get(node, []):
            if nxt == start:
                found.append(path + [nxt])
            elif nxt not in path:
                stack.append((nxt, path + [nxt]))
    return sorted(found)


# ------------------------------------------------ 3. the truthful queue

def per_minute(profile: list, minute: int) -> int:
    """Callers asking for a person in one minute, from a stand-in rate."""
    for start, end, rate in profile:
        if start <= minute < end:
            return int(rate * (minute + 1)) - int(rate * minute)
    return 0


def evening(policy: str, d: dict, trace: list | None = None) -> dict:
    """One storm evening, minute by minute, on one line of places. Under
    the old rule a place that waits 12 minutes goes back to the agent;
    under the truthful queue the agent states the wait, and a caller who
    takes a callback keeps her place without holding."""
    rng = random.Random(d["seed"])
    line, done, stated = [], [], []
    for t in range(d["minutes"]):
        for _ in range(per_minute(d["profile"], t)):
            wait = len(line) / d["per_minute"]
            c = {"arrive": t, "joined": t, "loops": 0, "callback": None,
                 "patience": rng.randint(*d["patience"])}
            if policy == "truthful queue":
                c["told"] = round(wait)
                if wait > d["offer_after"] and rng.random() < d["accept"]:
                    c["callback"] = t + round(wait) + d["margin"]
            line.append(c)
        still = []
        for c in line:                      # holders who give up
            if c["callback"] is None and t - c["arrive"] >= c["patience"]:
                done.append(dict(c, served=None))
            else:
                still.append(c)
        line = still
        if policy == "old overflow":        # the rule written before
            back = [c for c in line if t - c["joined"] >= d["overflow"]]
            line = [c for c in line if c not in back]
            line += [dict(c, joined=t + 1, loops=c["loops"] + 1)
                     for c in back]         # to the agent, and in again
        if trace is not None:                # the stated wait, for Figure 21.4
            trace.append(len(line) / d["per_minute"])
        for _ in range(min(d["per_minute"], len(line))):
            c = line.pop(0)
            done.append(dict(c, served=t))
            if "told" in c and c["callback"] is None:
                stated.append(abs(t - c["arrive"] - c["told"]))
    held = [c["served"] - c["arrive"] for c in done
            if c["served"] is not None and c["callback"] is None]
    cbs = [c for c in done if c["callback"] is not None]
    return {"policy": policy, "longest": max(held),
            "over": sum(w > d["overflow"] for w in held),
            "looped": sum(c["loops"] > 0 for c in done),
            "gave_up": sum(c["served"] is None for c in done),
            "callbacks": len(cbs),
            "kept": sum(c["served"] <= c["callback"] for c in cbs),
            "stated": (sum(e <= 3 for e in stated), len(stated))}


# ------------------------------------------------ 4. verification carried

LADDER = ["none", "pin", "pin + code"]
NEEDS = {"explain_bill": "pin", "book_visit": "pin",
         "change_address": "pin + code"}


def desk_accepts(level: str, age_min: int, action: str,
                 fresh_min: int) -> str:
    """The desk's rule: fresh and in scope, or a step up (INT-3)."""
    if level == "none":
        return "the desk verifies: nothing to carry"
    if age_min > fresh_min:
        return f"the desk verifies again: {age_min} minutes old"
    if LADDER.index(level) < LADDER.index(NEEDS[action]):
        return f"a step-up: {action} needs {NEEDS[action]}"
    return "carried: no questions again"


# ---------------------------------------------------------------- data

RECORDS = {
    "the Service Line's transfer": {
        "account": "5108", "intent": "a person about a doubled bill",
        "verified": "PIN at 10:42", "last two turns":
        "\"My bill doubled.\" / \"I'll put you through to billing.\"",
        "ticket id": "T-88213",
        "whisper": "Verified by PIN. Bill doubled after a meter swap. "
                   "Wants a person."},
    "the prototype's transfer": {
        "account": "5108", "intent": "billing_question_v2",
        "verified": "yes", "last two turns": "", "ticket id": "T-88213",
        "whisper": "The caller, who was verified earlier in the call "
                   "using her account number and PIN, says that her "
                   "latest bill is roughly double the previous one and "
                   "would now like to speak with a member of the billing "
                   "team."}}
ROUTES = {  # the storm evening's rules: target, and the rule that sends
    "service number": [("agent", "every call")],
    "agent": [("billing queue", "the caller asks for a person"),
              ("gas emergency team", "a gas smell")],
    "billing queue": [("service number", "overflow after 12 minutes"),
                      ("billing voicemail", "desk closed")],
    "gas emergency team": []}
ROUTES_FIXED = dict(ROUTES, **{
    "billing queue": [("callback list", "overflow after 12 minutes"),
                      ("billing voicemail", "desk closed")]})
EVENING = {"minutes": 240, "profile": [(0, 40, 3.5), (40, 120, 6.5),
                                       (120, 180, 3.0)],
           "per_minute": 5, "overflow": 12, "patience": (20, 45),
           "offer_after": 10, "accept": 0.7, "margin": 10, "seed": 21}
CARRIED = [("pin", 3, "explain_bill"), ("pin", 14, "explain_bill"),
           ("pin", 2, "change_address"), ("none", 0, "explain_bill")]
FRESH_MIN = 10


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"records": RECORDS, "routes": ROUTES,
                "routes_fixed": ROUTES_FIXED, "evening": EVENING,
                "carried": CARRIED, "fresh_min": FRESH_MIN}
    if mode == "fixture":
        return json.loads((FIXTURES / "handoff.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    """Print text after a lead, wrapped at the page width and aligned."""
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"handoff lab, mode={mode}; evidence class: simulated (step 3)")
    put("")
    put("1. the handoff record: what the desk sees")
    for name, record in data["records"].items():
        found = problems(record)
        plural = "" if len(found) == 1 else "s"
        put(f"   {name}: {len(found)} problem{plural}")
        for p in found:
            put(f"     - {p}")
    put("")
    put("2. the loop finder: the routing rules, searched from the agent")
    for label, routes in (("the storm evening's rules", data["routes"]),
                          ("after the fix", data["routes_fixed"])):
        found = loops(routes, "agent")
        put(f"   {label}: {len(found)} loop{'' if len(found) == 1 else 's'}")
        for path in found:
            block(put, "     ", " > ".join(path))
    put("")
    d = data["evening"]
    put("3. the truthful queue: a storm evening, 18:00 to 22:00")
    block(put, "   ", f"(stand-ins: the desk answers {d['per_minute']} "
          f"calls a minute; callers ask for a person at up to "
          f"{max(r for *_, r in d['profile'])} a minute; they wait "
          f"{d['patience'][0]} to {d['patience'][1]} minutes)")
    put(f"   {'':<18}{'longest':>8}{'over 12':>9}{'looped':>8}"
        f"{'gave up':>9}{'callbacks':>11}{'kept':>6}")
    for policy in ("old overflow", "truthful queue"):
        r = evening(policy, d)
        put(f"   {policy:<18}{r['longest']:>5} min{r['over']:>9}"
            f"{r['looped']:>8}{r['gave_up']:>9}{r['callbacks']:>11}"
            f"{r['kept']:>6}")
    ok, n = evening("truthful queue", d)["stated"]
    put(f"   waits stated to callers who held: {ok} of {n} right to within "
        "three minutes")
    put("")
    put("4. verification carried across the transfer "
        f"(fresh: {data['fresh_min']} minutes)")
    for level, age, action in data["carried"]:
        verdict = desk_accepts(level, age, action, data["fresh_min"])
        put(f"   {level:<6}{age:>3} min  {action:<16}{verdict}")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("HANDOFF_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"handoff_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "handoff.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/handoff.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("HANDOFF_LAB_MODE", "mock")))
    else:
        run_mode()
