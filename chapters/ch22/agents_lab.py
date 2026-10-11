"""Builders' Chapter 22 lab: agents on the line.

Four steps:

  1. who is calling       six callers, what each says about itself, and
                          what the policy lets each one do
  2. delegated authority  a customer's assistant moves a visit: every yes
                          checked against a delegation record
  3. holds per principal  a marketplace's assistants hold River Plumbing's
                          slots: capped per call, per principal, and per
                          platform
  4. a task to a partner  the Disruption Desk hands two rebookings to a
                          partner airline's agent; each becomes a tracked
                          promise to the passenger

Modes (select with AGENTS_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point step 2 at your own delegation records,
           and step 4 at a partner's agent-protocol endpoint in its test
           environment (evidence class: live laboratory).

  python3 agents_lab.py                  run and print the report
  python3 agents_lab.py --write-fixture  regenerate fixtures/
  python3 agents_lab.py --check          compare with the frozen output

Evidence class: simulated for step 3 (the marketplace's requests are
stand-ins); none for the checks, which apply rules to stand-in records.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ------------------------------------------------ 1. who is calling

POLICY = {  # what each kind of caller may do on the Service Line
    "a person": "anything the proof ladder allows",
    "an assistant, no delegation": "outage status and office details only",
    "an assistant with a delegation": "what the delegation's scope allows",
    "a partner's agent": "the structured door: tasks, not calls",
}


def kind(caller: dict) -> str:
    """What the policy treats the caller as. A voice that sounds made is
    not a machine: only what the caller says, or proves, decides."""
    if caller.get("channel") == "agent protocol":
        return "a partner's agent"
    if caller.get("says_automated"):
        if caller.get("delegation"):
            return "an assistant with a delegation"
        return "an assistant, no delegation"
    return "a person"


# ------------------------------------------------ 2. delegated authority

NEVER = {"pay", "change_contact_details", "close_account"}


def check_delegation(d: dict, agent: str, action: str, account: str,
                     now: int, revoked: set) -> tuple[bool, str]:
    """A delegation is checked like a verification level (INT-7)."""
    if action in NEVER:
        return False, f"refused: {action} is never done for an assistant"
    if d["id"] in revoked:
        return False, "refused: the customer revoked it"
    if agent != d["agent"]:
        return False, f"refused: issued to {d['agent']}, not {agent}"
    if account != d["principal"]:
        return False, f"refused: the delegation is for {d['principal']}"
    if now >= d["until"]:
        return False, f"refused: it ended at {clock(d['until'])}"
    if action not in d["scope"]:
        return False, f"refused: {action} is outside its scope"
    return True, f"allowed, bound to delegation {d['id']}"


def clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ------------------------------------------------ 3. holds per principal

def holds(requests: list, slots: int, minutes: int, hold_min: int,
          caps: dict | None, trace: list | None = None) -> dict:
    """Holds on the open slots, minute by minute, and the minutes in which
    a person calling would find every slot held."""
    active, blocked, refused = [], 0, 0
    for t in range(minutes):
        active = [h for h in active if h["until"] > t]
        for r in (x for x in requests if x["at"] == t):
            if caps:
                mine = sum(h["principal"] == r["principal"] for h in active)
                theirs = sum(h["platform"] == r["platform"] for h in active)
                if (mine >= caps["per_principal"]
                        or theirs >= caps["per_platform"]):
                    refused += 1
                    continue
            if len(active) < slots:
                active.append(dict(r, until=t + hold_min))
        blocked += len(active) >= slots
        if trace is not None:               # slots held, for Figure 22.3
            trace.append(len(active))
    return {"blocked": blocked, "refused": refused}


# ------------------------------------------------ 4. a task to a partner

TO_OPERATION = {  # the partner's task states, as your operation sees them
    "submitted": "proposed", "working": "pending",
    "input-required": "pending: the passenger's yes is needed",
    "completed": "committed", "failed": "failed", "rejected": "failed",
    "canceled": "canceled"}


def follow(task: dict, promise_by: int,
           fallback_at: int) -> list[tuple[int, str, str]]:
    """Your side of a partner's task: an operation, and a promise kept
    whether or not the partner finishes."""
    lines = [(at, state, TO_OPERATION[state] + (f"; {note}" if note else ""))
             for at, state, note in task["events"]]
    at, state, _ = lines[-1]
    if state == "completed":
        lines.append((at, "", "promise kept: the text says what the "
                      "partner confirmed, and only that"))
    elif at < fallback_at:
        lines.append((fallback_at, "", "no answer from the partner: a "
                      "person calls the passenger, before "
                      f"{clock(promise_by)} as promised"))
    return lines


# ---------------------------------------------------------------- data

CALLERS = [
    {"who": "a caller about a blank meter", "says_automated": False},
    {"who": "a caller who speaks through a text-to-speech device",
     "says_automated": False, "sounds_synthetic": True},
    {"who": "a search assistant asking about an outage",
     "says_automated": True},
    {"who": "a customer's assistant moving a visit",
     "says_automated": True, "delegation": "d-7305-1"},
    {"who": "a partner airline's agent", "channel": "agent protocol"},
    {"who": "an unannounced machine reading out prices",
     "says_automated": False, "sounds_synthetic": True}]
DELEGATION = {"id": "d-7305-1", "principal": "7305",
              "agent": "assistant.example", "scope": ["read_visit",
                                                      "move_visit"],
              "proof": "approved by the customer in the app at 18:02",
              "until": 19 * 60}
ASKS = [  # minute, agent, action, account
    (18 * 60 + 40, "assistant.example", "read_visit", "7305"),
    (18 * 60 + 41, "assistant.example", "move_visit", "7305"),
    (18 * 60 + 42, "assistant.example", "pay", "7305"),
    (18 * 60 + 43, "assistant.example", "move_visit", "7306"),
    (18 * 60 + 44, "other-assistant.example", "move_visit", "7305"),
    (19 * 60 + 5, "assistant.example", "move_visit", "7305")]
MARKET = {"slots": 4, "minutes": 30, "hold_min": 2, "principals": 12,
          "per_minute": 3,
          "platform": "a home-services marketplace",
          "caps": {"per_principal": 1, "per_platform": 2}}
TASKS = [
    {"passenger": "a passenger rebooked on the partner's 07:10",
     "events": [(20 * 60 + 12, "submitted", ""),
                (20 * 60 + 13, "working", ""),
                (20 * 60 + 19, "input-required",
                 "the partner offers seat 14C"),
                (20 * 60 + 20, "working", "the passenger said yes"),
                (20 * 60 + 31, "completed", "seat 14C confirmed")]},
    {"passenger": "a passenger whose rebooking the partner never answers",
     "events": [(20 * 60 + 12, "submitted", ""),
                (20 * 60 + 13, "working", "")]}]
PROMISE_BY, FALLBACK_AT = 21 * 60, 20 * 60 + 45


def market_requests(m: dict) -> list[dict]:
    """A stand-in flood from one platform: a few hold requests a minute,
    taking its customers in turn."""
    n = m["per_minute"]
    return [{"at": t, "platform": m["platform"],
             "principal": f"customer {(t * n + i) % m['principals'] + 1}"}
            for t in range(m["minutes"]) for i in range(n)]


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"callers": CALLERS, "delegation": DELEGATION, "asks": ASKS,
                "market": MARKET, "tasks": TASKS,
                "promise_by": PROMISE_BY, "fallback_at": FALLBACK_AT}
    if mode == "fixture":
        return json.loads((FIXTURES / "agents.json").read_text())
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
    put(f"agents lab, mode={mode}; evidence class: simulated (step 3)")
    put("")
    put("1. who is calling, and what the policy lets each one do")
    for c in data["callers"]:
        k = kind(c)
        put(f"   {c['who']}")
        block(put, "     ", f"treated as {k}: {POLICY[k]}")
    put("")
    d = data["delegation"]
    put("2. delegated authority: a customer's assistant and one delegation")
    block(put, "   ", f"delegation {d['id']}: customer {d['principal']} to "
          f"{d['agent']}, scope {' and '.join(d['scope'])}, until "
          f"{clock(d['until'])}; {d['proof']}")
    for at, agent, action, account in data["asks"]:
        _, why = check_delegation(d, agent, action, account, at, set())
        put(f"   {clock(at)}  {action} {account} by {agent}")
        block(put, "          ", why)
    _, why = check_delegation(d, d["agent"], "move_visit", d["principal"],
                              18 * 60 + 50, {d["id"]})
    put(f"   18:50  move_visit {d['principal']}, after the customer "
        "revoked it in the app")
    block(put, "          ", why)
    put("")
    m = data["market"]
    put(f"3. holds per principal: {m['platform']}, "
        f"{m['principals']} customers")
    block(put, "   ", f"({m['per_minute']} hold requests a minute for "
          f"{m['minutes']} minutes; {m['slots']} open slots; holds of "
          f"{m['hold_min']} minutes; stand-in requests)")
    reqs = market_requests(m)
    put(f"   {'limits on holds':<37}{'minutes all held':>18}{'refused':>9}")
    for label, caps in (("one hold per call", None),
                        ("one per customer, two per platform",
                         m["caps"])):
        r = holds(reqs, m["slots"], m["minutes"], m["hold_min"], caps)
        put(f"   {label:<37}{r['blocked']:>12} of {m['minutes']}"
            f"{r['refused']:>9}")
    put("")
    put("4. a task to a partner: each rebooking tracked as a promise")
    block(put, "   ", "(the promise to each passenger: \"I'll text you by "
          f"{clock(data['promise_by'])} with the partner's answer.\")")
    for task in data["tasks"]:
        put(f"   {task['passenger']}")
        for at, state, text in follow(task, data["promise_by"],
                                      data["fallback_at"]):
            block(put, f"     {clock(at)}  {state:<15}", text)
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("AGENTS_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"agents_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "agents.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/agents.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("AGENTS_LAB_MODE", "mock")))
    else:
        run_mode()
