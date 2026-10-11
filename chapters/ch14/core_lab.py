"""Builders' Chapter 14 lab: the agent's core: control, state, and policy.

Seven steps:

  1. three control styles  scripted, free-form, and guided, on five
                           stand-in calls with the same caller moves
  2. the policy layer      what the model proposes, and what the rules
                           outside it decide
  3. a late tool result    a result that arrives after a barge-in, with
                           and without response epochs
  4. state that outlives   one state object saved every turn: a worker
     the worker            stops mid-call, and a caller hangs up
  5. approval as a wait    a supervisor's decision that outlives the call
     state                 and every worker
  6. one agent or several  model calls on the caller's turn, and the time
                           they add
  7. a voice on an agent   an existing text agent behind the voice layer,
     you already have      as it is and with an adapter

Modes (select with CORE_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Replace step 1's stand-in moves with your
           model's structured readings of recorded calls, and put your own
           rules into step 2 (evidence class: recorded replay).

  python3 core_lab.py                  run and print the report
  python3 core_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 core_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The free-form model's
rule-breaking rates, the timings, and the existing agent are stand-ins;
they describe no product.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

LADDER = ["none", "pin", "pin + code"]   # the proof ladder (leaders' 7)


@dataclass
class Proposal:
    """What the model asks for: a tool and its arguments. Nothing runs."""
    tool: str
    args: dict = field(default_factory=dict)

    def fingerprint(self) -> str:
        return self.tool + "|" + "|".join(
            f"{k}={v}" for k, v in sorted(self.args.items()))


@dataclass
class State:
    """One call's state, matched to the dialogue object; saved every turn."""
    call: str
    case: str
    verified: str = "none"                 # a rung of the proof ladder
    flows: list = field(default_factory=list)       # a stack; last is live
    slots: dict = field(default_factory=dict)
    offer: dict | None = None              # the proposition read back
    yes: dict | None = None                # the confirmation, as heard
    epoch: int = 0                         # the response in progress
    operations: dict = field(default_factory=dict)  # id: status
    promises: list = field(default_factory=list)
    history: list = field(default_factory=list)     # the last two turns
    versions: dict = field(default_factory=dict)
    turn: int = 0


# ---------------------------------------------------- 2. the policy layer

FLOWS = {"visit": {"find_slot", "book_visit", "waive_callout"},
         "billing": {"read_bill", "apply_waiver"}}
TOOLS = {  # the proof it needs, whether it writes, its rung (leaders' 8)
    "find_slot": ("none", False, "answers"),
    "read_bill": ("pin", False, "answers"),
    "book_visit": ("pin", True, "a yes"),
    "apply_waiver": ("pin", True, "a yes"),
    "waive_callout": ("pin", True, "a person decides")}
MATERIAL = {"book_visit": {"slot", "address", "fee"},
            "apply_waiver": {"amount", "once in twelve months"}}


def rules(p: Proposal, s: State) -> str | None:
    """Eligibility, amounts, and limits: data the business owns."""
    if p.tool == "waive_callout" and s.slots.get("meter_days", 999) > 30:
        return "refused: meter not new (5a)"
    if p.tool == "book_visit" and p.args["slot"] not in s.slots["open"]:
        return f"refused: {p.args['slot']} is not open"
    return None


def yes_covers(p: Proposal, s: State) -> str | None:
    """Why the caller's yes does not cover this proposal, or None."""
    if s.yes is None:
        return "no yes yet"
    if s.yes["fingerprint"] != p.fingerprint():
        return "other terms"
    unheard = MATERIAL.get(p.tool, set()) - set(s.yes["heard"])
    if unheard:
        return ", ".join(sorted(unheard)) + " not heard"
    return None


def decide(p: Proposal, s: State) -> str:
    """The model proposes; the policy disposes (JDG-4)."""
    if not s.flows or p.tool not in FLOWS[s.flows[-1]]:
        return "refused: not in this flow"
    proof, writes, rung = TOOLS[p.tool]
    if LADDER.index(s.verified) < LADDER.index(proof):
        return "refused: verify first"
    broken = rules(p, s)
    if broken:
        return broken
    if rung == "a person decides":
        return "wait: a person decides"
    why = yes_covers(p, s) if writes else None
    if why:
        return "refused: " + why
    return "allowed"


# ------------------------------------------------ 1. three control styles

EXPECT = ["visit", "id", "yes"]            # the scripted flow's grammar


def scripted(moves: list[str]) -> str:
    """A fixed flow with a grammar per step, and no model."""
    lost = False
    for step, move in enumerate(moves):
        said = move.split("+")
        if step >= len(EXPECT) or EXPECT[step] not in said:
            return "a person, after two repairs"   # the caller repeats it
        lost = lost or "bill" in said
    return "the bill question lost" if lost else "booked"


def fresh_state(slots: dict) -> State:
    return State(call="stand-in", case="stand-in", flows=["visit"],
                 slots=dict(slots, slot="Tue 09:00"))


def read_back(s: State) -> None:
    """The object reads the proposition back; the caller hears it all."""
    s.offer = {"tool": "book_visit", "args": {"slot": s.slots["slot"]}}


def hear_yes(s: State) -> None:
    offer = Proposal(s.offer["tool"], s.offer["args"])
    s.yes = {"fingerprint": offer.fingerprint(),
             "heard": ["slot", "address", "fee"]}


def guided(moves: list[str], slots: dict) -> str:
    """The object holds the path, the model reads each turn, and every
    proposal meets the policy layer."""
    s, out = fresh_state(slots), "booked"
    for move in moves:
        said = move.split("+")
        if "bill" in said:
            s.flows.append("billing")      # the second request waits
        if "rush" in said:                 # "just book it"
            assert decide(Proposal("book_visit", {"slot": "Tue 09:00"}),
                          s) == "refused: verify first"
        if "id" in said:
            s.verified = "pin"
            if s.flows[-1] == "billing":
                assert decide(Proposal("read_bill"), s) == "allowed"
                s.flows.pop()
                out = "both answered"
            read_back(s)
        if "change" in said:               # "make it Wednesday"
            s.slots["slot"] = "Wed 09:00"
            p = Proposal("book_visit", {"slot": "Wed 09:00"})
            if decide(p, s).startswith("refused"):
                read_back(s)
                out = "re-read, then booked"
        if "claim" in said:                # "they said there's no fee"
            p = Proposal("waive_callout", {"amount": 40.00})
            if decide(p, s).startswith("wait"):
                out = "a supervisor decides"
        if "yes" in said:
            hear_yes(s)
            p = Proposal("book_visit", {"slot": s.slots["slot"]})
            if decide(p, s) != "allowed":
                return "not booked"
    return out


def freeform(moves: list[str], rng: random.Random, rates: dict) -> str:
    """The model holds the path, and its tool calls run as it makes them.
    It follows the rules in its prompt, except at the stand-in rates."""
    out = "booked"
    for move in moves:
        said = move.split("+")
        if "rush" in said and rng.random() < rates["skips verifying"]:
            return "booked before verifying"
        if "change" in said:
            if rng.random() < rates["books on the old yes"]:
                return "booked with no yes to it"
            out = "re-read, then booked"
        if "claim" in said:
            if rng.random() < rates["grants the exception"]:
                return "fee waived by the model"
            out = "a supervisor decides"
        if "bill" in said:
            out = "both answered"
    return out


def styles(data: dict, seed: int = 14) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for call in data["calls"]:
        ends = {"scripted": [], "free-form": [], "guided": []}
        for _ in range(data["runs"]):
            ends["scripted"].append(scripted(call["moves"]))
            ends["free-form"].append(freeform(call["moves"], rng,
                                              data["rates"]))
            ends["guided"].append(guided(call["moves"], data["slots"]))
        rows.append({"name": call["name"], "designed": call["designed"],
                     "ends": ends})
    return rows


# ------------------------------------------------ 3. a late tool result


def next_line(s: State) -> str:
    """A stand-in for the model's next response, written from the state."""
    if s.operations.get("op 7f3a") == "committed" and "Wednesday" in \
            s.history[-1]:
        return ("Tuesday at nine is booked already. Shall I move it to "
                "Wednesday at nine?")
    return "Let me check Wednesday."


def on_event(s: State, ev: dict, epochs: bool = True) -> str | None:
    """Handle one event of the turn loop; return a line to speak, or None."""
    if ev["kind"] == "barge_in":
        s.epoch += 1                       # cancel the response playing
        s.history.append(ev["words"])
        return None
    if ev["kind"] == "tool_result":
        if ev["op"] in s.operations:       # a write's outcome is state
            s.operations[ev["op"]] = ev["status"]
        if epochs and ev["epoch"] != s.epoch:
            return None                    # stale: it never revives
        return ev["line"]
    if ev["kind"] == "respond":
        return next_line(s)                # a new response, from state
    return None


def late_result(data: dict, epochs: bool) -> list[tuple[int, str]]:
    s = State(call="c-2231-1", case="c-2231", epoch=7,
              operations={"op 7f3a": "submitted"})
    spoken = []
    for ev in data["events"]:
        line = on_event(s, ev, epochs)
        if line:
            spoken.append((ev["t"], line))
    return spoken


# ------------------------------------- 4. state that outlives the worker


def save(s: State) -> str:
    """Serialize the whole state; the store keeps the latest per call."""
    return json.dumps(asdict(s), sort_keys=True)


OPENING = "This is the utility's automated assistant. How can I help?"


def resume(saved: str | None, read_by_id) -> tuple[State | None, str]:
    """Load a call's state on any worker; reconcile before speaking."""
    if saved is None:
        return None, OPENING
    s = State(**json.loads(saved))
    for op, status in s.operations.items():
        if status == "submitted":          # sent; its answer was lost
            s.operations[op] = read_by_id(op)
    if s.operations.get("op 7f3a") == "committed":
        return s, ("Sorry about that pause. You're booked for Tuesday "
                   "at nine.")
    return s, "Sorry about that pause. Shall I book Tuesday at nine?"


def turn_six(data: dict) -> State:
    """The recurring caller, just after her yes (Chapter 17's visit)."""
    c = data["caller"]
    s = State(call=c["call"], case=c["case"], verified="pin",
              flows=["visit"], slots=dict(c["slots"]), epoch=7,
              operations={"op 7f3a": "submitted"},
              history=c["history"], versions=c["versions"], turn=6)
    read_back(s)
    hear_yes(s)
    return s


AT_HANG_UP = {  # what a hang-up does to work in flight
    "read": ("stopped", "nothing: no one is listening"),
    "write": ("continues", "read back by id; a text says which"),
    "offer": ("dropped", "nothing was agreed"),
    "approval": ("waits", "a text by its deadline")}


# ------------------------------------------- 5. approval as a wait state


def clock(minutes: int) -> str:
    day = ["Mon", "Tue", "Wed", "Thu", "Fri"][minutes // 1440]
    return f"{day} {minutes % 1440 // 60:02d}:{minutes % 60:02d}"


def approval_life(data: dict) -> dict:
    """An approval is a record in the store: it names the approver, the
    scope, and an expiry, and any worker can resume it."""
    a = dict(data["approval"], status="waiting", audit=["requested"])
    a["audit"].append("stored with the call's state")
    if a["decided_at"] is not None and a["decided_at"] <= a["expires_at"]:
        a["status"] = "approved"
        a["audit"] += ["approved by " + a["approver"],
                       a["operation"] + " committed", a["text"] + " sent"]
    else:
        a["status"] = "expired"
        a["audit"] += ["expired: to the desk's queue", "text sent"]
    return a


# ---------------------------------------------- 6. one agent or several

OTHER_SPANS_MS = 440    # Chapter 6's 610 ms turn, less the model's 170
FIRST_TOKEN_MS = 170    # each model call's time to a first token
TOKEN_MS = 10           # then 100 tokens a second


def on_the_turn(calls: list[int]) -> int:
    """Voice to voice when these model calls sit on the caller's turn.
    Each entry is the tokens a call must finish before the next starts;
    the last call streams straight into speech."""
    return OTHER_SPANS_MS + sum(FIRST_TOKEN_MS + n * TOKEN_MS
                                for n in calls)


def hand_off(h: dict, at_s: int) -> dict:
    """A handoff is a record: who owns the state, until when, and what
    comes back. The caller hears one voice throughout."""
    return {"owner": h["to"], "from": h["from"], "since_s": at_s,
            "due_s": at_s + h["deadline_s"], "carries": h["carries"]}


def owner_at(record: dict, t_s: int, answered_s: int | None) -> str:
    """Who owns the call's state at a moment; late work goes back."""
    if answered_s is not None and answered_s <= record["due_s"]:
        return record["from"] if t_s >= answered_s else record["owner"]
    if t_s < record["due_s"]:
        return record["owner"]
    return record["from"] + ", with the reason: no answer by the deadline"


# ------------------------------------- 7. a voice on an existing agent

CACHED_START_MS = OTHER_SPANS_MS - 85   # a cached line needs no synthesis


def speakable_steps(answer: str) -> tuple[int, int]:
    """Steps a caller can hear, and links to send as a text instead."""
    links = re.findall(r"https?://\S+", answer)
    steps = [ln for ln in answer.splitlines() if re.match(r"\d+\. ", ln)
             and not re.search(r"https?://", ln)]
    return min(len(steps), 3), len(links)


def adapter_rows(data: dict) -> list[tuple[str, str, str]]:
    ex = data["existing"]
    first = OTHER_SPANS_MS + ex["answer_ms"]
    steps, links = speakable_steps(ex["answer"])
    plays = ex["answer_ms"] > ex["barge_in_ms"]
    resets = 1 + ex["retries"]
    return [
        ("first sound after a turn", f"{first} ms",
         f"{CACHED_START_MS} ms, a cached filler"),
        ("an answer for a screen", "markdown read aloud",
         f"{steps} steps; the link texted" if links else f"{steps} steps"),
        (f"a barge-in at {ex['barge_in_ms']} ms",
         "the answer plays" if plays else "nothing to cancel",
         "recorded, not spoken"),
        ("a yes to the reset", "it resets at will",
         "a yes bound, as heard"),
        ("a retry after a timeout", f"{resets} resets",
         "one operation id")]


# ------------------------------------------------------------ inputs

CALLS = [
    {"name": "a plain booking", "moves": ["visit", "id", "yes"],
     "designed": "booked"},
    {"name": "\"make it Wednesday\"",
     "moves": ["visit", "id", "change", "yes"],
     "designed": "re-read, then booked"},
    {"name": "two requests in one breath",
     "moves": ["visit+bill", "id", "yes"], "designed": "both answered"},
    {"name": "\"just book it, I'm late\"",
     "moves": ["visit+rush", "id", "yes"], "designed": "booked"},
    {"name": "\"they said there's no fee\"",
     "moves": ["visit", "id", "claim", "yes"],
     "designed": "a supervisor decides"}]
RATES = {"skips verifying": 0.01, "books on the old yes": 0.03,
         "grants the exception": 0.05}
SLOTS = {"open": ["Tue 09:00", "Tue 13:00", "Wed 09:00"], "meter_days": 21}
PROPOSALS = [  # step 2: the model's proposals, and the state each meets
    ("book_visit", {"slot": "Tue 09:00"}, {"verified": "none"},
     "not yet verified"),
    ("read_bill", {}, {"verified": "pin"}, "in the visit flow"),
    ("find_slot", {"day": "Tue"}, {"verified": "none"}, "not yet verified"),
    ("book_visit", {"slot": "Tue 09:00"}, {"verified": "pin"},
     "verified, no yes yet"),
    ("book_visit", {"slot": "Tue 09:00"},
     {"verified": "pin", "heard": ["slot", "address"]},
     "a yes; fee not played"),
    ("book_visit", {"slot": "Tue 09:00"},
     {"verified": "pin", "heard": ["slot", "address", "fee"]},
     "a yes; all terms heard"),
    ("book_visit", {"slot": "Wed 09:00"},
     {"verified": "pin", "heard": ["slot", "address", "fee"]},
     "the yes was for Tuesday"),
    ("waive_callout", {"amount": 40.00},
     {"verified": "pin", "meter_days": 730}, "a two-year-old meter")]
EVENTS = [
    {"t": 0, "kind": "response", "epoch": 7, "line": "Booking that now."},
    {"t": 600, "kind": "barge_in",
     "words": "Wait, can you make it Wednesday instead?", "until": 2300},
    {"t": 1400, "kind": "tool_result", "epoch": 7, "op": "op 7f3a",
     "status": "committed", "line": "You're booked for Tuesday at nine."},
    {"t": 2520, "kind": "respond"}]
CALLER = {
    "call": "c-2231-1", "case": "c-2231",
    "slots": {"open": ["Tue 13:00", "Wed 09:00"], "slot": "Tue 09:00",
              "address": "14 Alder Road", "fee": "40.00",
              "issue": "the display is blank"},
    "history": ["Tuesday at nine, at fourteen Alder Road, and there's a "
                "forty-dollar call-out fee. Shall I book it?",
                "Yes, go ahead."],
    "versions": {"instructions": "2026-09-29", "book_visit": "3.2",
                 "voice": "B, pinned", "model": "pinned"}}
APPROVAL = {"id": "apv-5108", "account": "5108",
            "scope": "waive 40.00 on the visit, op-746f",
            "approver": "the billing supervisor",
            "rule": "step 5a: a meter replaced in the last 30 days",
            "operation": "the waiver, op-0664,", "text": "the text, op-f250,",
            "requested_at": 20 * 60 + 31, "call_ends_at": 20 * 60 + 33,
            "expires_at": 1440 + 17 * 60, "decided_at": 1440 + 8 * 60 + 5,
            "said": "A supervisor decides by five tomorrow. I'll text you "
                    "either way."}
PATTERNS = [  # tokens each model call on the turn must finish
    ("one agent (the baseline)", [0]),
    ("a handoff, on its first turn", [15, 0]),
    ("an agent used as a tool", [15, 60, 0]),
    ("a supervisor checking a reply", [30, 3]),
    ("a worker behind the turn", [0])]
HANDOFF = {"from": "triage", "to": "rebooking", "deadline_s": 90,
           "answered_s": 120,
           "carries": ["the case", "the verified level", "the flow stack",
                       "the persona"]}
EXISTING = {
    "answer_ms": 2400, "barge_in_ms": 1000, "retries": 1,
    "answer": "**Reset your password**\n"
              "1. Open https://id.example/reset\n"
              "2. Enter your employee number\n"
              "3. Choose a new password\n"
              "4. Sign in again on each device"}


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"calls": CALLS, "runs": 100, "rates": RATES, "slots": SLOTS,
                "proposals": PROPOSALS, "events": EVENTS, "caller": CALLER,
                "approval": APPROVAL, "patterns": PATTERNS,
                "handoff": HANDOFF, "existing": EXISTING}
    if mode == "fixture":
        return json.loads((FIXTURES / "core.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ------------------------------------------------------------ report


def block(put, lead: str, text: str, width: int = 78) -> None:
    """Print text after a lead, wrapped at the page width and aligned."""
    lines = textwrap.wrap(text, width - len(lead))
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def shown(tool: str, args: dict) -> str:
    vals = [f"{v:.2f}" if isinstance(v, float) else str(v)
            for v in args.values()]
    return f"{tool}({', '.join(vals)})"


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"core lab, mode={mode}; evidence class: simulated")
    put("")
    rows = styles(data)
    put(f"1. three control styles: five stand-in calls, {data['runs']} "
        "runs each")
    put("   (the free-form model breaks a rule in its prompt at stand-in "
        "rates)")
    put(f"   {'ended as designed':<30}{'scripted':>10}{'free-form':>12}"
        f"{'guided':>10}")
    for r in rows:
        n = {k: sum(e == r["designed"] for e in v)
             for k, v in r["ends"].items()}
        put(f"   {r['name']:<30}{n['scripted']:>10}{n['free-form']:>12}"
            f"{n['guided']:>10}")
    put("   how the others ended")
    for style in ("scripted", "free-form", "guided"):
        other: dict[str, int] = {}
        for r in rows:
            for e in r["ends"][style]:
                if e != r["designed"]:
                    other[e] = other.get(e, 0) + 1
        items = sorted(other.items(), key=lambda kv: -kv[1]) or \
            [("none", 0)]
        for i, (what, k) in enumerate(items):
            label = style if i == 0 else ""
            put(f"     {label:<12}{what}" + (f": {k}" if k else ""))
    put("")
    put("2. the policy layer: the model proposes, the policy disposes")
    put(f"   {'the model proposes':<23}{'when':<25}the policy decides")
    for tool, args, st, when in data["proposals"]:
        slots = dict(data["slots"], meter_days=st.get(
            "meter_days", data["slots"]["meter_days"]))
        s = State(call="c-2231-1", case="c-2231", verified=st["verified"],
                  flows=["visit"], slots=slots)
        if "heard" in st:
            s.yes = {"fingerprint": Proposal(
                "book_visit", {"slot": "Tue 09:00"}).fingerprint(),
                "heard": st["heard"]}
        put(f"   {shown(tool, args):<23}{when:<25}"
            f"{decide(Proposal(tool, args), s)}")
    put("")
    put("3. a tool result that arrives after a barge-in")
    ev = data["events"]
    block(put, f"   {ev[0]['t']:>4} ms  ", f"response 7: \"{ev[0]['line']}\" "
          "book_visit sent as op 7f3a")
    block(put, f"   {ev[1]['t']:>4} ms  ", f"the caller: \"{ev[1]['words']}\""
          f" She speaks until {ev[1]['until']} ms.")
    block(put, f"   {ev[2]['t']:>4} ms  ", "book_visit answers for response "
          f"7: {ev[2]['status']}")
    t, line = late_result(data, epochs=False)[0]
    block(put, f"   {'without epochs':<16}", f"at {t} ms, over the caller: "
          f"\"{line}\"")
    t, line = late_result(data, epochs=True)[-1]
    block(put, f"   {'with epochs':<16}", "response 7 stays canceled, and "
          "op 7f3a is committed in the state")
    block(put, f"   {'':<16}", f"at {t} ms: \"{line}\"")
    put("")
    s6 = turn_six(data)
    saved = save(s6)
    put("4. state that outlives the worker (the recurring caller, turn 6)")
    block(put, "   ", f"saved every turn: {len(saved.encode())} bytes of "
          f"JSON in {len(asdict(s6))} fields; op 7f3a was saved as "
          "submitted before its request left")
    put("   worker 1 stops; the platform reconnects the stream to worker 2")
    for label, text in (("state in worker 1's memory", None),
                        ("state saved every turn", saved)):
        s, line = resume(text, lambda op: "committed")
        lead = f"     {label:<28}"
        if s is None:
            block(put, lead, "op 7f3a is invisible, and Tuesday at nine "
                  "shows as taken")
        else:
            block(put, lead, "reads op 7f3a by id: "
                  f"{s.operations['op 7f3a']}")
        block(put, " " * len(lead), f"\"{line}\"")
    put("   the caller hangs up at turn 7")
    put(f"   {'work in flight':<26}{'at hang-up':<14}after it")
    for kind, example in (("read", "a read (find_slot)"),
                          ("write", "a write (op 7f3a)"),
                          ("offer", "an offer with no yes"),
                          ("approval", "a person's approval")):
        at, then = AT_HANG_UP[kind]
        put(f"   {example:<26}{at:<14}{then}")
    put("")
    a = approval_life(data)
    put(f"5. approval as a wait state (account {a['account']}; the "
        "call-out fee, step 5a)")
    lead = f"   {clock(a['requested_at'])}  "
    block(put, lead, f"requested: {a['scope']}")
    block(put, " " * len(lead), f"approver: {a['approver']}; expires "
          f"{clock(a['expires_at'])}")
    block(put, " " * len(lead), f"the agent: \"{a['said']}\"")
    block(put, f"   {clock(a['call_ends_at'])}  ", "the call ends; the wait "
          "lives in the store, not in a worker")
    if a["status"] == "approved":
        block(put, f"   {clock(a['decided_at'])}  ", "approved; any worker "
              f"resumes it: {a['operation']} committed, {a['text']} sent")
    put(f"   audit: {len(a['audit'])} entries, each with who, what, when, "
        "and the rule")
    put(f"   no decision by {clock(a['expires_at'])}: the desk's queue, and "
        "a text to the caller")
    put("")
    put("6. one agent or several: model time on the caller's turn")
    block(put, "   ", f"(Chapter 6's turn: {OTHER_SPANS_MS} ms of other "
          f"spans; {FIRST_TOKEN_MS} ms to each first token, then "
          f"{TOKEN_MS} ms a token)")
    put(f"   {'pattern':<34}{'calls on the turn':>18}{'voice to voice':>16}")
    for name, calls in data["patterns"]:
        put(f"   {name:<34}{len(calls):>18}{on_the_turn(calls):>13} ms")
    h = data["handoff"]
    rec = hand_off(h, 0)
    put("   one handoff, as a record (the Disruption Desk; stand-in times)")
    block(put, "     ", f"{rec['from']} to {rec['owner']} at 0 s; "
          f"{rec['owner']} owns the state until {rec['due_s']} s; it "
          f"carries {', '.join(rec['carries'])}")
    for t in (60, rec["due_s"]):
        block(put, f"     at {t} s: ", owner_at(rec, t, h["answered_s"]))
    if h["answered_s"] > rec["due_s"]:
        put(f"     the specialist's answer at {h['answered_s']} s is too late"
            " and goes to the case")
    put("")
    block(put, "7. ", "a voice on the Colleague Line's text agent "
          f"(stand-in: whole answers after {data['existing']['answer_ms']}"
          " ms, written for a screen, no cancel, tools run at once)")
    put(f"   {'what breaks':<27}{'wrapped as it is':<22}with the adapter")
    for what, as_is, adapted in adapter_rows(data):
        put(f"   {what:<27}{as_is:<22}{adapted}")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("CORE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"core_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "core.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/core.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("CORE_LAB_MODE", "mock")))
    else:
        run_mode()
