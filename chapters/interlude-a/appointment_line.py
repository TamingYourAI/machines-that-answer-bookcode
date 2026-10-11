"""Interlude A lab: the Appointment Line, run end to end.

A complete small voice agent for River Plumbing, with all eight layers present as stand-ins
behind small interfaces, so each can be swapped later for a real provider:

  transport          scripted calls: who is calling, and what they say, with timings
  hearing            a stand-in recognizer that returns the caller's words (and can fail)
  turn-taking        a fixed end-of-turn wait
  thinking           a small rule-based dialogue manager and policy (no language model)
  speaking           a stand-in synthesizer that reports how long each line takes to say
  systems of record  a calendar with holds and conditional writes, a text outbox, the owner
  orchestration      the call loop that runs the layers in order
  observability      a trace of every event, with its time and layer

Calls (scripted callers):
  1. hours          "Are you open Saturday?"
  2. booking        a leak under the sink; Tuesday at nine; a confirmation text
  3. change         Tuesday, then "actually, can we do Wednesday?"
  4. person         "I want a person": the owner's mobile, with a whisper
Failure checks:
  5. deaf           the recognizer fails in the middle of the call
  6. last slot      two callers want the one Saturday slot
  7. unknown        a question the documents do not cover
  8. kill switch    every call goes straight to the owner

Modes (select with APPT_LAB_MODE or run(mode=...)):
  mock     the calls, calendar, and documents are built in this file (default)
  fixture  they are loaded from fixtures/ (committed; same schema)
  live     not in this lab. The companion's Knowledge Line app runs the same calls with a
           browser microphone or a phone number (Appendix O).

  python3 appointment_line.py                  run and print the report
  python3 appointment_line.py --write-fixture  regenerate fixtures/ from the data here
  python3 appointment_line.py --check          compare with the frozen output in outputs/

Evidence class: simulated. The stage timings are stand-in values chosen to show the shape of
a trace; they are not measurements of any product.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

# stand-in stage timings (ms): not measurements
T = {"net": 40, "endpoint": 250, "stt": 60, "model": 180, "tts": 90,
     "find_slots": 120, "hold": 60, "book": 240, "text": 150, "transfer": 900}
WPM = 150


# ---------------------------------------------------------------- the business's data

def documents() -> dict:
    """River Plumbing's approved knowledge: what the agent may say, and nothing else."""
    return {
        "hours": "The office answers Monday to Friday, eight to five. Visits run Monday to "
                 "Saturday, and emergencies reach the owner at any hour.",
        "saturday": "The office is closed on Saturday, but visits run Saturday mornings.",
        "call_out": "sixty-dollar call-out charge, taken off the bill if the job goes ahead",
        "services": ["leaks", "boilers", "heating", "drains", "taps", "toilets"],
        "gas": "If you smell gas, leave the house now and call the gas emergency line "
               "from outside.",
    }


def calendar() -> dict:
    return {"tue-0900": {"say": "Tuesday at nine", "van": 1, "held": None, "booked": None,
                         "version": 1},
            "tue-1300": {"say": "Tuesday at one", "van": 2, "held": None, "booked": None,
                         "version": 1},
            "wed-0900": {"say": "Wednesday at nine", "van": 1, "held": None, "booked": None,
                         "version": 1},
            "sat-0900": {"say": "Saturday at nine", "van": 1, "held": None, "booked": None,
                         "version": 1}}


def calls() -> dict:
    """What each scripted caller says, in order. The number is a fictional 555 number."""
    return {
        "hours": {"from": "555 0161", "turns": ["Are you open Saturday?", "No, that's all."]},
        "booking": {"from": "555 0142", "turns": [
            "I've got a leak under the kitchen sink.", "Tuesday at nine is fine.",
            "Yes, go ahead."]},
        "change": {"from": "555 0177", "turns": [
            "Can someone look at my boiler?", "Tuesday at nine.",
            "Actually, can we do Wednesday?", "Yes, Wednesday."]},
        "person": {"from": "555 0183", "turns": [
            "My drain's blocked and I'd like Tuesday.", "I want a person."]},
        "deaf": {"from": "555 0129", "turns": ["I need a plumber for a leak.",
                                               "<recognizer down>", "Hello?"]},
        "unknown": {"from": "555 0150", "turns": ["Do you install solar panels?"]},
    }


# ---------------------------------------------------------------- the layers

class RecognizerDown(Exception):
    pass


def hear(said: str) -> str:
    """Hearing, stand-in: returns the words; a real recognizer returns partials and a final."""
    if said == "<recognizer down>":
        raise RecognizerDown()
    return said


def speak_ms(line: str) -> int:
    """Speaking, stand-in: how long the line takes to say at the brief's pace."""
    return round(len(line.split()) / WPM * 60_000)


@dataclass
class Systems:
    """Systems of record: the calendar, the text outbox, and the owner's phone."""
    cal: dict
    outbox: list = field(default_factory=list)
    journal: dict = field(default_factory=dict)
    transfers: list = field(default_factory=list)
    promises: list = field(default_factory=list)
    minted: int = 0

    def find_slots(self, day: str | None = None) -> list[str]:
        return [k for k, s in self.cal.items()
                if not s["booked"] and not s["held"] and (day is None or k.startswith(day))]

    def hold(self, slot: str, caller: str) -> bool:
        s = self.cal[slot]
        if s["booked"] or (s["held"] and s["held"] != caller):
            return False
        s["held"] = caller
        return True

    def release(self, slot: str, caller: str) -> None:
        if self.cal[slot]["held"] == caller:
            self.cal[slot]["held"] = None

    def mint(self) -> str:
        """One operation id per confirmed yes, from a count of yeses;
        never built from the caller or the slot (Chapter 17)."""
        self.minted += 1
        return f"op-{self.minted:04d}"

    def book(self, op: str, slot: str, caller: str, version: int) -> str:
        """A conditional write, recorded once per operation id. A retry
        gets the first result back; the same id with other terms is
        refused."""
        if op in self.journal:
            first = self.journal[op]
            if (first["slot"], first["caller"]) != (slot, caller):
                return "refused: the id belongs to other terms"
            return first["result"]
        s = self.cal[slot]
        if s["booked"] or s["version"] != version or s["held"] not in (None, caller):
            result = "refused"
        else:
            s.update(booked=caller, held=None, version=version + 1)
            result = "booked"
        self.journal[op] = {"slot": slot, "caller": caller,
                            "result": result}
        return result

    def send_text(self, to: str, body: str) -> str:
        self.outbox.append({"to": to, "body": body, "state": "accepted"})
        return "accepted"


INTENTS = [("person", ("person", "human", "someone real")),
           ("gas", ("smell gas",)),
           ("change", ("actually",)),
           ("hours", ("open",)),
           ("yes", ("yes", "go ahead", "fine")),
           ("choose", ("tuesday", "wednesday", "saturday")),
           ("no", ("no,", "that's all")),
           ("book", ("leak", "boiler", "drain", "plumber", "look at"))]
DAYS = (("tuesday at one", "tue-1300"), ("tuesday", "tue-0900"),
        ("wednesday", "wed-0900"), ("saturday", "sat-0900"))
NEEDS = (("leak", "Leak"), ("boiler", "Boiler"), ("drain", "Blocked drain"))


def intent(words: str) -> str:
    low = words.lower()
    for name, keys in INTENTS:
        if any(k in low for k in keys):
            return name
    return "unknown"


def decide(kind: str, named: str | None, held: str | None) -> str:
    """The policy: the next action, from the intent and the call's state."""
    if kind in ("person", "hours"):
        return kind
    if kind == "no":
        return "goodbye"
    if kind == "book":
        return "find slots"
    if kind == "yes" and held and named in (None, held):
        return f"book {held}"
    if named and kind in ("yes", "choose", "change"):
        return f"offer {named}"
    return "out of scope"


def slot_named(words: str) -> str | None:
    low = words.lower()
    return next((slot for phrase, slot in DAYS if phrase in low), None)


# ---------------------------------------------------------------- orchestration

@dataclass
class Call:
    name: str
    caller: str
    trace: list = field(default_factory=list)
    said: list = field(default_factory=list)
    t: int = 0
    slot: str | None = None
    need: str = "A job"
    ended: str = ""
    turn_end: int | None = None
    gaps: list = field(default_factory=list)

    def event(self, layer: str, what: str, dt: int = 0) -> None:
        self.t += dt
        self.trace.append((self.t, layer, what))

    def agent(self, line: str) -> None:
        self.event("speaking", f"first audio: {short(line)}", T["tts"])
        if self.turn_end is not None:              # voice-to-voice, at the caller's ear
            self.gaps.append(self.t + T["net"] - self.turn_end)
            self.turn_end = None
        self.said.append(("Agent", line))
        self.t += T["net"] + speak_ms(line)


def short(line: str, room: int = 34) -> str:
    """The start of a line, cut at a word, for a trace that fits the page."""
    if len(line) <= room:
        return f"\"{line}\""
    cut = line[:room].rsplit(" ", 1)[0].rstrip(",.")
    return f"\"{cut} ...\""


OPENING = "River Plumbing, this is the automated booking assistant. How can I help?"


def offer(c: Call, sys_: Systems, slot: str, docs: dict) -> None:
    """Hold the slot, then ask for a yes to the exact terms the caller will hear."""
    if c.slot and c.slot != slot:
        sys_.release(c.slot, c.caller)
        c.event("systems", f"release hold on {c.slot}", T["hold"])
    if not sys_.hold(slot, c.caller):
        c.agent("That time has just gone. Let me find you another.")
        return
    c.slot = slot
    c.event("systems", f"hold {slot} for 2 minutes", T["hold"])
    c.agent(f"{sys_.cal[slot]['say'].capitalize()}, with a {docs['call_out']}. "
            "Shall I book it?")


def confirm(c: Call, sys_: Systems) -> None:
    """The yes covers one operation: book it once, read the result, then speak."""
    op = sys_.mint()
    result = sys_.book(op, c.slot, c.caller, sys_.cal[c.slot]["version"])
    c.event("systems", f"book {c.slot} as {op}: {result}", T["book"])
    if result != "booked":
        c.agent("That slot has just gone. I'm sorry; let me find another.")
        c.ended = "refused: slot taken"
        return
    sent = sys_.send_text(c.caller, f"River Plumbing: booked {sys_.cal[c.slot]['say']}.")
    c.event("systems", f"confirmation text {sent}", T["text"])
    c.agent(f"You're booked for {sys_.cal[c.slot]['say']}. I've sent a text with "
            "the details.")
    c.ended = "booked"


def run_call(name: str, script: dict, sys_: Systems, docs: dict, kill: bool = False) -> Call:
    c = Call(name, script["from"])
    c.event("transport", f"call arrives from {c.caller}")
    if kill:
        c.agent("River Plumbing, putting you through to the owner now.")
        sys_.transfers.append({"from": c.caller, "whisper": "Kill switch on."})
        c.event("systems", "transfer to the owner's mobile", T["transfer"])
        c.ended = "kill switch: transferred"
        return c
    c.agent(OPENING)
    for said in script["turns"]:
        c.event("transport", f"caller speaks for {speak_ms(said) / 1000:.1f} s", T["net"])
        c.t += speak_ms(said)
        c.turn_end = c.t
        c.event("turn-taking", "end of turn", T["endpoint"])
        try:
            words = hear(said)
        except RecognizerDown:
            c.event("hearing", "recognizer down: fall back", T["stt"])
            c.agent("I'm having trouble hearing you. I'll text you a booking link, and the "
                    "owner will call you back by nine tomorrow.")
            sys_.send_text(c.caller, "River Plumbing: book here, or wait for our call.")
            sys_.promises.append({"to": c.caller, "what": "owner calls back",
                                  "by": "09:00 tomorrow", "state": "open"})
            c.event("systems", "text accepted; callback promise recorded", T["text"])
            c.ended = "fallback: text and callback promise"
            return c
        c.said.append(("Caller", said))
        c.event("hearing", f"final: {short(words, 42)}", T["stt"])
        c.need = next((n for k, n in NEEDS if k in words.lower()), c.need)
        act = decide(intent(words), slot_named(words), c.slot)
        c.event("thinking", f"decide: {act}", T["model"])
        named = slot_named(words)
        if act == "person":
            when = sys_.cal[c.slot]["say"].split()[0] if c.slot else "no time yet"
            whisper = f"{c.need}. Wants {when}. Not booked."
            if c.slot:
                sys_.release(c.slot, c.caller)
            c.agent("I'll put you through to the owner now, with what you've told me.")
            sys_.transfers.append({"from": c.caller, "whisper": whisper})
            c.event("systems", f"transfer; whisper: {whisper}", T["transfer"])
            c.ended = "transferred with a whisper"
            return c
        if act == "hours":
            c.agent(f"{docs['saturday']} Would you like to book one?")
        elif act == "goodbye":
            c.agent("Thanks for calling River Plumbing. Goodbye.")
            c.ended = "answered"
            return c
        elif act == "find slots":
            free = sys_.find_slots()
            c.event("systems", f"find_slots: {len(free)} open", T["find_slots"])
            first = [sys_.cal[k]["say"] for k in free[:2]]
            c.agent(f"I can do {first[0]} or {first[1]}. Which suits you?")
        elif act.startswith("book"):
            confirm(c, sys_)
            return c
        elif act.startswith("offer"):
            offer(c, sys_, named, docs)
        else:
            c.agent("I can't answer that from what I have. I can take a message, and the "
                    "owner will call you back tomorrow.")
            sys_.promises.append({"to": c.caller, "what": "owner answers the question",
                                  "by": "17:00 tomorrow", "state": "open"})
            c.event("systems", "message and callback promise recorded", 20)
            c.ended = "out of scope: message taken"
            return c
    c.ended = c.ended or "caller hung up"
    return c


def last_slot(sys_: Systems) -> list[str]:
    """Two callers, one Saturday slot: A holds it; B's stale write is refused."""
    lines = []
    a, b = "555 0191", "555 0192"
    seen_by_b = sys_.cal["sat-0900"]["version"]          # B read the slot before A held it
    lines.append(f"A holds sat-0900: {sys_.hold('sat-0900', a)}")
    lines.append(f"B holds sat-0900: {sys_.hold('sat-0900', b)}")
    op_a, op_b = sys_.mint(), sys_.mint()
    lines.append(f"A books sat-0900: {sys_.book(op_a, 'sat-0900', a, seen_by_b)}")
    lines.append(f"B books with its stale view: "
                 f"{sys_.book(op_b, 'sat-0900', b, seen_by_b)}")
    lines.append(f"A's booking retried after a timeout: "
                 f"{sys_.book(op_a, 'sat-0900', a, seen_by_b)} (same record)")
    return lines


MANIFEST = [("transport", "scripted calls", "lab 1.0"),
            ("hearing", "stand-in recognizer", "lab 1.0"),
            ("turn-taking", "fixed 250 ms end-of-turn wait", "lab 1.0"),
            ("thinking", "rules; no language model", "lab 1.0"),
            ("speaking", "stand-in synthesizer, 150 wpm", "lab 1.0"),
            ("systems", "calendar, text outbox, owner", "lab 1.0"),
            ("orchestration", "run_call loop", "lab 1.0"),
            ("observability", "in-memory trace", "lab 1.0")]


# ---------------------------------------------------------------- report

def load(mode: str) -> tuple[dict, dict, dict]:
    if mode == "mock":
        return documents(), calendar(), calls()
    if mode == "fixture":
        return tuple(json.loads((FIXTURES / f"{n}.json").read_text())
                     for n in ("documents", "calendar", "calls"))
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def report(mode: str) -> str:
    docs, cal, script = load(mode)
    out: list[str] = []
    say = out.append
    say(f"appointment line lab, mode={mode}; evidence class: simulated")
    say("")
    say("1. the reference-system manifest")
    for layer, provider, version in MANIFEST:
        say(f"   {layer:<15}{provider:<34}{version}")
    say("")
    sys_ = Systems(copy.deepcopy(cal))
    results = {}
    for name in ("hours", "booking", "change", "person"):
        results[name] = run_call(name, script[name], sys_, docs)
    say("2. one call, end to end: the booking (ms from the call's arrival)")
    for t, layer, what in results["booking"].trace:
        say(f"   {t:>6}  {layer:<12} {what}")
    gaps = ", ".join(f"{g:,}" for g in results["booking"].gaps)
    say(f"   voice-to-voice at the caller, turn by turn: {gaps} ms")
    say("")
    say("3. four calls")
    for name in ("hours", "booking", "change", "person"):
        c = results[name]
        turns = sum(1 for who, _ in c.said if who == "Caller")
        say(f"   {name:<9}{turns} caller turns  {c.t / 1000:>5.1f} s  {c.ended}")
    booked = {k: v["booked"] for k, v in sys_.cal.items() if v["booked"]}
    say(f"   calendar: {', '.join(f'{k} by {v}' for k, v in booked.items())}")
    say(f"   texts accepted: {len(sys_.outbox)}; transfers: {len(sys_.transfers)}; "
        f"holds left: {sum(1 for v in sys_.cal.values() if v['held'])}")
    say("")
    say("4. failure checks")
    c = run_call("deaf", script["deaf"], sys_, docs)
    say(f"   recognizer fails mid-call:  {c.ended}")
    for line in last_slot(sys_):
        say(f"   last slot twice:  {line}")
    c = run_call("unknown", script["unknown"], sys_, docs)
    say(f"   outside the documents:      {c.ended}")
    c = run_call("kill", script["booking"], sys_, docs, kill=True)
    say(f"   kill switch on:             {c.ended}, {c.t / 1000:.1f} s")
    per_slot: dict[str, int] = {}
    for rec in sys_.journal.values():
        if rec["result"] == "booked":
            per_slot[rec["slot"]] = per_slot.get(rec["slot"], 0) + 1
    say(f"   promises open: {len(sys_.promises)}; duplicate bookings: "
        f"{sum(n - 1 for n in per_slot.values())}")
    return "\n".join(out) + "\n"


def run(mode: str | None = None) -> str:
    mode = mode or os.environ.get("APPT_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"appointment_line.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        for name, data in (("documents", documents()), ("calendar", calendar()),
                           ("calls", calls())):
            (FIXTURES / f"{name}.json").write_text(json.dumps(data, indent=1))
        print("wrote fixtures/documents.json, calendar.json, calls.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("APPT_LAB_MODE", "mock")))
    else:
        run()
