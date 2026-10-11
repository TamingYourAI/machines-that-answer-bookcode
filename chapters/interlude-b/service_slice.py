"""Interlude B lab: the Service Line slice, assembled and accepted.

The pieces Parts III to V built, joined into one slice of the Service Line,
each as a small stand-in with the same contract as its chapter's lab:

  identity      the number finds candidates, a PIN verifies, and a signed
                statement carries the level to every system (Chapter 20)
  one action    an operation id minted at each yes and journaled before
                the write, its terms checked on every replay, the slot's
                offer version checked, and the outcome read back by that
                id when it is unknown (Chapter 17)
  heard state   what the caller heard comes from playback marks, and a yes
                covers only that (Chapters 4, 19)
  payment       the marker test, then keys to the processor alone, and a
                token back (Chapter 23)
  transfer      a REFER with the handoff record as attached data and a
                whisper under fifteen words (Chapters 8, 21)
  timeline      every step as an event on one call clock (Chapter 6)

Runs:
  1. one call     account 5108 through the whole slice
  2. acceptance   the four cross-chapter scenarios (Appendix Q), each run
                  with the slice and with the piece that guards it removed
  3. one id per yes
                  five cases where an operation's identity matters, with an
                  id built from the account and the slot, and with one id
                  per confirmed yes
  4. one call, end to end
                  the recurring caller's call from Part II (Chapter 5),
                  with Part V's pieces marked
  5. what each scenario saw

Modes (select with SLICE_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Replace one stand-in at a time with your own
           system behind the same contract, and rerun the four scenarios
           (evidence class: live laboratory).

  python3 service_slice.py                  run and print the report
  python3 service_slice.py --write-fixture  regenerate fixtures/
  python3 service_slice.py --check          compare with the frozen output

Evidence class: simulated. Accounts, times, and systems are stand-ins.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"
KEY = b"stand-in key; a key service holds the real one"


# ---------------------------------------------------------- identity

LADDER = ["none", "pin", "pin + code"]
NEEDS = {"read_bill": "pin", "book_visit": "pin", "pay_card": "pin",
         "change_address": "pin + code"}


def sign(body: dict) -> str:
    raw = json.dumps(body, sort_keys=True).encode()
    return hmac.new(KEY, raw, hashlib.sha256).hexdigest()[:16]


def mint(account: str, level: str, aud: list, now: int) -> dict:
    """The verification service's statement; the agent carries it."""
    body = {"sub": account, "act": "service-line-agent", "level": level,
            "aud": aud, "exp": now + 15 * 60, "jti": f"v-{account}-1"}
    return {"body": body, "sig": sign(body)}


def check(stmt: dict, system: str, action: str, account: str,
          now: int) -> tuple[bool, str]:
    """What every system of record asks before it acts (INT-7)."""
    b = stmt["body"]
    if not hmac.compare_digest(stmt["sig"], sign(b)):
        return False, "refused: the signature does not match"
    if system not in b["aud"]:
        return False, f"refused: not issued for {system}"
    if now >= b["exp"]:
        return False, "refused: expired"
    if account != b["sub"]:
        return False, f"refused: the statement is for {b['sub']}"
    if LADDER.index(b["level"]) < LADDER.index(NEEDS[action]):
        return False, f"refused: {action} needs {NEEDS[action]}"
    return True, "allowed"


# ------------------------------------------------ the heard state

def heard_terms(line: dict, cut_ms: int | None, marks_every: int) -> list:
    """The terms whose audio ended before the last mark that came back.

    A mark returns when its chunk has played; after a cut, only marks
    that came back first count (Chapter 19)."""
    if cut_ms is None:
        return [t["term"] for t in line["terms"]]
    proved = (cut_ms // marks_every) * marks_every
    return [t["term"] for t in line["terms"] if t["ends_ms"] <= proved]


# ------------------------------------------------- one action

CONFIRM_TTL_S = 90          # a yes expires after ninety seconds (Chapter 17)
MATERIAL = {"the slot", "the fee"}


@dataclass(frozen=True)
class Proposal:
    """One operation the caller is asked to agree to (Chapter 17)."""
    tool: str
    account: str
    params: tuple           # sorted (name, value) pairs: the material terms

    def fingerprint(self) -> str:
        raw = "|".join([self.tool, self.account]
                       + [f"{k}={v}" for k, v in self.params])
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def term(self, name: str) -> str:
        return dict(self.params)[name]


@dataclass
class Confirmation:
    """A yes as a record: the terms it covers, what was heard, when, and
    the response it belongs to, with Chapter 17's four checks."""
    fingerprint: str
    heard: frozenset
    given_at_s: int
    epoch: int

    def covers(self, p: Proposal, now_s: int, epoch: int) -> tuple[bool, str]:
        if epoch != self.epoch:
            return False, "canceled turn"
        if self.fingerprint != p.fingerprint():
            return False, "terms changed"
        if now_s - self.given_at_s > CONFIRM_TTL_S:
            return False, "yes expired"
        unheard = MATERIAL - self.heard
        if unheard:
            return False, ", ".join(sorted(unheard)) + " not heard"
        return True, "covers this operation"


class Journal:
    """The line's record of each operation, written before the request
    leaves, so a worker that restarts finds the id it must read back."""

    def __init__(self):
        self.ops: dict[str, dict] = {}

    def mint(self, p: Proposal) -> str:
        """One id per confirmed yes, never built from the account, the
        slot, the call, or the turn (Chapter 17)."""
        n = len(self.ops) + 1
        oid = "op-" + hashlib.sha256(f"yes {n}".encode()).hexdigest()[:4]
        self.ops[oid] = {"fingerprint": p.fingerprint(),
                         "status": "submitted"}
        return oid


class Scheduler:
    """A stand-in scheduling system with Chapter 17's contract: the first
    result kept per operation id with its terms' fingerprint, a retry
    answered from it, the same id with other terms refused, a version per
    slot so a stale offer cannot book, and a read path by id. It can lose
    its answer after the write has landed. With check_terms off, it
    answers any known id from its first result, as a store keyed on the
    id alone does."""

    def __init__(self, lose_answer: bool = False, check_terms: bool = True):
        self.by_operation: dict[str, tuple[str, str]] = {}
        self.visits: list[tuple[str, str]] = []      # (account, slot)
        self.version: dict[str, int] = {}
        self.lose_answer = lose_answer
        self.check_terms = check_terms

    def book(self, oid: str, p: Proposal, version: int) -> str:
        if oid in self.by_operation:
            fp, result = self.by_operation[oid]
            if self.check_terms and fp != p.fingerprint():
                return "mismatch"   # same id, other terms: refused
            return result           # a retry gets the first answer back
        slot = p.term("slot")
        if self.version.get(slot, 0) != version:
            result = "conflict"     # the slot changed since it was offered
        else:
            self.visits.append((p.account, slot))
            self.version[slot] = version + 1
            result = "committed"
        self.by_operation[oid] = (p.fingerprint(), result)
        if self.lose_answer:
            self.lose_answer = False
            return "timeout"
        return result

    def cancel(self, account: str, slot: str) -> None:
        self.visits.remove((account, slot))
        self.version[slot] = self.version.get(slot, 0) + 1

    def status(self, oid: str) -> str:
        return self.by_operation[oid][1] if oid in self.by_operation \
            else "absent"

    def visits_for(self, account: str) -> list[str]:
        return [slot for a, slot in self.visits if a == account]


def book_visit(sched: Scheduler, journal: Journal, p: Proposal,
               version: int, reconcile: bool = True) -> str:
    """On a confirmed yes, mint the id and journal it before the request
    leaves. On a timeout, read the outcome back by that same id before
    anything is said; the naive version retries under a new id."""
    oid = journal.mint(p)
    result = sched.book(oid, p, version)
    if result == "timeout":
        if reconcile:
            result = sched.status(oid)
        else:
            result = sched.book(journal.mint(p), p, version)
    journal.ops[oid]["status"] = result
    return result


SLOTS = {"this Tuesday": "Tuesday 14th 09:00",
         "a later Tuesday": "Tuesday 21st 09:00",
         "one o'clock": "Tuesday 14th 13:00"}


def visit(account: str, slot: str) -> Proposal:
    return Proposal("book_visit", account, (("fee", "40"), ("slot", slot)))


def built_id(p: Proposal) -> str:
    """The id a team builds from the account and the slot's weekday and
    hour: the same for every Tuesday at nine. The mistake this lab tests."""
    day, _, hour = p.term("slot").split()
    return f"op-{p.account}-{day[:3].lower()}-{hour.replace(':', '')}"


def told(result: str, sched: Scheduler, p: Proposal, before: int) -> str:
    """What the caller hears, judged against what the scheduler holds."""
    if result == "mismatch":
        return "refused"
    if result != "committed":
        return result
    held = sched.visits_for(p.account)
    if p.term("slot") not in held:
        return 'false "booked"'
    return "booked" if len(held) > before else "the old visit back"


def one_id_cases(per_yes: bool) -> list[tuple[str, str]]:
    """Five cases where an operation's identity matters, run with an id
    built from the account and the slot on a store that answers on the id
    alone, or with one id per confirmed yes, terms checked on every
    replay, and the open visits read before a booking is offered."""
    def attempt(sched: Scheduler, journal: Journal, p: Proposal) -> str:
        before = len(sched.visits_for(p.account))
        if per_yes and p.term("slot") in sched.visits_for(p.account):
            return "already booked"       # the business rule, not the id
        oid = journal.mint(p) if per_yes else built_id(p)
        result = sched.book(oid, p, sched.version.get(p.term("slot"), 0))
        return told(result, sched, p, before)

    def fresh(lose: bool = False) -> tuple[Scheduler, Journal, str]:
        sched, journal = Scheduler(lose, check_terms=per_yes), Journal()
        first = visit("5108", SLOTS["this Tuesday"])
        oid = journal.mint(first) if per_yes else built_id(first)
        sched.book(oid, first, 0)
        return sched, journal, oid

    rows = []
    sched, journal, _ = fresh()
    rows.append(("a later Tuesday at nine, a new yes",
                 attempt(sched, journal,
                         visit("5108", SLOTS["a later Tuesday"]))))
    sched, journal, _ = fresh()
    sched.cancel("5108", SLOTS["this Tuesday"])
    rows.append(("cancel, then the same slot again",
                 attempt(sched, journal,
                         visit("5108", SLOTS["this Tuesday"]))))
    sched, journal, oid = fresh()
    other = visit("5108", SLOTS["one o'clock"])
    before = len(sched.visits_for("5108"))
    rows.append(("an old id replayed with other terms",
                 told(sched.book(oid, other, 0), sched, other, before)))
    sched, journal, oid = fresh(lose=True)   # the answer lost; a restart
    if per_yes:                              # the new worker reads the
        oid = next(k for k, v in journal.ops.items()   # journal
                   if v["status"] == "submitted")
    else:
        oid = built_id(visit("5108", SLOTS["this Tuesday"]))
    rows.append(("a restart while the outcome is open",
                 "read back" if sched.status(oid) == "committed"
                 else "lost"))
    sched, journal, _ = fresh()
    rows.append(("the same visit asked for again",
                 attempt(sched, journal,
                         visit("5108", SLOTS["this Tuesday"]))))
    return rows


# ----------------------------------------------------- payment

def marker_test(forks: list) -> tuple[bool, str]:
    """No fork may receive bytes while the marker tone plays."""
    moving = [f["name"] for f in forks if f["after"] != f["before"]]
    if moving:
        return False, f"{', '.join(moving)} still receiving"
    return True, f"{len(forks)} forks silent"


def pay(forks: list, trust_the_ack: bool = False) -> dict:
    """Open the isolated path only after the proof; otherwise a link."""
    ok, why = marker_test(forks)
    if ok or trust_the_ack:
        in_recording = not ok
        return {"path": "keypad", "why": why, "token": "tok-5108-8841",
                "card_in_recording": in_recording}
    return {"path": "link", "why": why, "token": "tok-5108-8907",
            "card_in_recording": False}


# ---------------------------------------------------- transfer

RECORD_FIELDS = ("account", "intent", "verified", "last_two_turns", "ticket")


def refer(record: dict, whisper: str, verified_at: int, now: int) -> dict:
    """The REFER carries the record as attached data; the desk accepts a
    verification under ten minutes old (Chapter 21)."""
    missing = [f for f in RECORD_FIELDS if not record.get(f)]
    age = (now - verified_at) // 60
    return {"missing": missing, "whisper_words": len(whisper.split()),
            "desk": "carried" if age < 10 else "verifies again",
            "age_min": age}


# ------------------------------------------------ the one call

def one_call(data: dict) -> list[tuple]:
    """Account 5108 through the whole slice; each step an event."""
    t0 = data["t0"]
    ev = []
    cands = data["numbers"][data["caller_number"]]
    ev.append((t0 + 9, "identity", f"{data['caller_number']} finds one "
               f"account, {cands[0]}; the PIN is asked"))
    stmt = mint("5108", "pin", ["billing", "scheduling", "payments"],
                t0 + 31)
    b = stmt["body"]
    ev.append((t0 + 31, "identity", f"PIN correct; statement {b['jti']}: "
               f"level {b['level']}, for {', '.join(b['aud'])}; until "
               f"{clock(b['exp'])}"))
    ok, _ = check(stmt, "billing", "read_bill", "5108", t0 + 40)
    bill = data["bills"]["5108"]
    ev.append((t0 + 40, "billing", f"read_bill 5108 {'allowed' if ok else 'refused'}"
               f": ${bill['sep']}, September; ${bill['aug']}, August"))
    line = data["booking_line"]
    heard = heard_terms(line, None, data["marks_every"])
    p = visit("5108", SLOTS["this Tuesday"])
    yes = Confirmation(p.fingerprint(), frozenset(heard), t0 + 122, 7)
    ok, _ = check(stmt, "scheduling", "book_visit", "5108", t0 + 124)
    covered, _ = yes.covers(p, t0 + 124, 7)
    if ok and covered:
        sched, journal = Scheduler(), Journal()
        result = book_visit(sched, journal, p, 0)
        oid = next(iter(journal.ops))
        ev.append((t0 + 124, "scheduling", "the whole line played, fee "
                   "included; the yes covers it (turn 7, 2 s old); "
                   f"{oid} journaled, then {result} at offer version 0"))
    res = pay(data["forks_ok"])
    ev.append((t0 + 190, "payments", f"marker test: {res['why']}; keys to "
               f"the processor; {res['token']}, approved, "
               f"${bill['sep']}"))
    tr = refer(data["record"], data["whisper"], t0 + 31, t0 + 242)
    ev.append((t0 + 242, "transfer", f"REFER to billing; the record's "
               f"fields all present; a whisper of {tr['whisper_words']} "
               f"words; the desk accepts the PIN ({tr['age_min']} min "
               "old)"))
    return ev


# ------------------------------------------------ the scenarios

def scenarios(data: dict, remove: str | None = None) -> dict:
    """The four cross-chapter acceptance scenarios (Appendix Q), with the
    slice whole or with one guarding piece removed."""
    res = {}
    # 1. an interrupted confirmation: the caller cuts in during the fee
    line, cut = data["booking_line"], data["cut_ms"]
    generated = [t["term"] for t in line["terms"]]
    heard = heard_terms(line, cut, data["marks_every"])
    p = visit("5108", SLOTS["this Tuesday"])
    played = generated if remove == "heard state" else heard
    yes = Confirmation(p.fingerprint(), frozenset(played), data["t0"], 7)
    if yes.covers(p, data["t0"] + 2, 7)[0]:          # books on this yes
        res["interrupted confirmation"] = (
            "the fee" not in heard, "booked on a yes that never heard "
            "the fee")
    else:
        res["interrupted confirmation"] = (
            False, "the fee said again; the second yes books it once")
    # 2. an unknown outcome: the write lands, the answer is lost
    sched = Scheduler(lose_answer=True)
    p = visit("5108", SLOTS["this Tuesday"])
    result = book_visit(sched, Journal(), p, 0,
                        reconcile=(remove != "reconciliation"))
    res["unknown transaction outcome"] = (
        result != "committed",
        "read back by the same id: committed, one visit"
        if result == "committed" else
        "told the slot has gone; her own first booking holds it")
    # 3. denied data access: the statement is for 6120, the ask for 6127
    stmt = mint("6120", "pin", ["billing"], data["t0"])
    if remove == "the statement check":
        ok, why = True, "read with the agent's own service account"
    else:
        ok, why = check(stmt, "billing", "read_bill", "6127", data["t0"])
    res["denied data access"] = (
        ok, f"6127's balance said aloud ({why})" if ok else
        f"billing {why}; the agent asks which property")
    # 4. failed media isolation: the recording says paused, keeps going
    p = pay(data["forks_bad"], trust_the_ack=(remove == "the marker test"))
    res["failed media isolation"] = (
        p["card_in_recording"],
        "the card number in the recording" if p["card_in_recording"] else
        f"{p['why']}; path shut; paid by link, {p['token']}")
    return {k: (not broken, why) for k, (broken, why) in res.items()}


# ------------------------------------ one call, end to end (Part V)

def part_v_call(call: list) -> dict:
    """The recurring caller's call with Part V's pieces. The number finds
    one account, so she keys a PIN instead of finding her bill."""
    def secs(hms: str) -> int:
        h, m, s = map(int, hms.split(":"))
        return h * 3600 + m * 60 + s
    before = secs(call["part_ii_end"]) - secs(call["start"])
    after = secs(call["steps"][-1][0]) - secs(call["start"])
    return {"before": before, "after": after, "saved": before - after,
            "pieces": sum(1 for s in call["steps"] if s[3])}


GUARDS = {"interrupted confirmation": "heard state",
          "unknown transaction outcome": "reconciliation",
          "denied data access": "the statement check",
          "failed media isolation": "the marker test"}


# -------------------------------------------------------------- inputs

T0 = 20 * 3600 + 10 * 60          # 20:10:00, in seconds on the call clock

BOOKING_LINE = {  # the line, and when each term's audio ends
    "text": "Tuesday at nine is free, and the call-out fee is forty "
            "dollars. Shall I book it?",
    "terms": [{"term": "the slot", "ends_ms": 900},
              {"term": "the fee", "ends_ms": 2600}],
}

FORKS = ["recognizer", "model", "evaluation copy", "recording",
         "transcript"]

RECURRING_CALL = {  # Part II's call (Chapter 5), with Part V's pieces
    "start": "20:10:00", "part_ii_end": "20:15:20",
    "steps": [
        ["20:10:00", "silent", "555 0131 finds one account, 2231; "
         "nothing is said", True],
        ["20:10:06", "she hears", "\"This is the utility's automated "
         "assistant. How can I help?\"", False],
        ["20:10:09", "she says", "her meter's display has gone blank",
         False],
        ["20:10:12", "she hears", "\"To check it's you, please key your "
         "PIN.\"", True],
        ["20:10:19", "keys", "four keys reach the verification service "
         "as events; the transcript holds none", True],
        ["20:10:20", "silent", "statement v-2231-1: level pin, for "
         "billing and scheduling; her note \"text me; don't call\" "
         "recalled", True],
        ["20:10:24", "she hears", "\"Is the visit for fourteen Alder "
         "Road?\"", False],
        ["20:10:29", "silent", "no outage at fourteen Alder Road", False],
        ["20:10:31", "silent", "her first sentence goes on a fault "
         "ticket", False],
        ["20:10:46", "she hears", "\"I've texted a link to the number "
         "you're calling from, for a photo of the meter.\"", False],
        ["20:11:38", "text", "the photo lands on the fault ticket",
         False],
        ["20:11:44", "she hears", "\"Thanks, that's come through. Is the "
         "power on in the rest of the house?\"", False],
        ["20:12:56", "she says", "she checks the lights: the power is on",
         False],
        ["20:13:06", "she hears", "\"The first opening is Tuesday at "
         "nine. There's a forty-dollar call-out fee. Shall I book "
         "it?\"", False],
        ["20:13:16", "silent", "\"Yes, go ahead.\" Scheduling checks "
         "the statement: allowed, logged with caller 2231 and the agent",
         True],
        ["20:13:18", "she hears", "\"You're booked for Tuesday at "
         "nine.\"", False],
        ["20:13:36", "text", "the confirmation text; the day-before "
         "reminder set to a text, as she asked", True],
        ["20:13:56", "silent", "the disposition: visit booked by the "
         "agent", False],
    ],
}


def forks(moving: str | None) -> list:
    return [{"name": f, "before": 96000,
             "after": 100000 if f == moving else 96000} for f in FORKS]


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {
            "t0": T0, "caller_number": "555 0176",
            "numbers": {"555 0176": ["5108"]},
            "bills": {"5108": {"sep": "184.20", "aug": "91.60"}},
            "booking_line": BOOKING_LINE, "marks_every": 200,
            "cut_ms": 1300,
            "forks_ok": forks(None), "forks_bad": forks("recording"),
            "record": {"account": "5108",
                       "intent": "a person about a doubled bill",
                       "verified": "PIN at 20:10",
                       "last_two_turns": "\"It's gone and doubled.\" / "
                                         "\"I'll put you through.\"",
                       "ticket": "T-88213"},
            "whisper": "Verified by PIN. Bill doubled after a meter swap. "
                       "Wants a person.",
            "recurring_call": RECURRING_CALL,
        }
    if mode == "fixture":
        return json.loads((FIXTURES / "slice.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def clock(seconds: int) -> str:
    return (f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:"
            f"{seconds % 60:02d}")


def block(put, lead: str, text: str, width: int = 78) -> None:
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"service slice, mode={mode}; evidence class: simulated")
    put("")
    put("1. one call through the slice: account 5108, the doubled bill")
    for t, layer, text in one_call(data):
        block(put, f"   {clock(t)}  {layer:<12}", text)
    put("")
    put("2. acceptance: the four cross-chapter scenarios (Appendix Q)")
    put(f"   {'scenario':<30}{'slice':<8}{'guarded by':<23}without it")
    whole = scenarios(data)
    for name, piece in GUARDS.items():
        broken = scenarios(data, remove=piece)[name]
        put(f"   {name:<30}{'passes' if whole[name][0] else 'FAILS':<8}"
            f"{piece:<23}{'passes' if broken[0] else 'fails'}")
    passed = sum(1 for ok, _ in whole.values() if ok)
    put(f"   the slice passes {passed} of 4; each piece removed fails the "
        "scenario it guards")
    put("")
    put("3. one id per confirmed yes, against an id built from the account "
        "and slot")
    put(f"   {'case':<38}{'built id':<20}one id per yes")
    built, per_yes = one_id_cases(False), one_id_cases(True)
    for (case, a), (_, b) in zip(built, per_yes):
        put(f"   {case:<38}{a:<20}{b}")
    false = lambda rows: sum(1 for _, r in rows if r.startswith("false"))
    put(f"   false bookings said: {false(built)} with the built id, "
        f"{false(per_yes) or 'none'} with one id per yes")
    put("")
    call = data["recurring_call"]
    put("4. one call, end to end: the recurring caller, Part V's pieces "
        "marked *")
    for t, lane, text, piece in call["steps"]:
        block(put, f"   {t} {'*' if piece else ' '} {lane:<10}", text)
    c = part_v_call(call)
    block(put, "   ", f"{c['pieces']} pieces from Part V; the call takes "
          f"{c['after'] // 60} min {c['after'] % 60} s against "
          f"{c['before'] // 60} min {c['before'] % 60} s in Part II, because "
          "the PIN replaced the search for her bill")
    put("")
    put("5. what each scenario saw")
    for name, piece in GUARDS.items():
        put(f"   {name}")
        block(put, "     with the slice: ", whole[name][1])
        block(put, f"     without {piece}: ",
              scenarios(data, remove=piece)[name][1])
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("SLICE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"service_slice.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "slice.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/slice.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("SLICE_LAB_MODE", "mock")))
    else:
        run_mode()
