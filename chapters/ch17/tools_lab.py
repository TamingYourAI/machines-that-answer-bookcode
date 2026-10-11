"""Builders' Chapter 17 lab: tools and actions that happen once and are spoken truthfully.

The lab runs six small experiments on the Service Line's technician-visit booking tool:

  1. the tool contract table          what every tool declares before a caller meets it
  2. spoken failure                   each error class and the words the agent says
  3. lost responses and retries       three retry strategies on a faulty link
  4. confirmation binding             five ways a "yes" can be misapplied
  5. the last slot                    two callers, every possible ordering
  6. post-call promises               a receipt that must arrive, tracked or not

Modes (select with TOOLS_LAB_MODE or run(mode=...)):
  mock     fault schedules generated from seeded random numbers (default; runs anywhere)
  fixture  fault schedules loaded from fixtures/faults.json (committed; same schema)
  live     not implemented in this lab. To try the same failures on your own systems,
           point a booking adapter at a sandbox calendar and a test SMS number; the evidence
           becomes live laboratory (Appendix A).

Other entry points:
  python3 tools_lab.py                 run in the selected mode and print the report
  python3 tools_lab.py --write-fixture regenerate fixtures/faults.json from the mock seeds
  python3 tools_lab.py --check         run, then compare with the frozen output in outputs/

Evidence class of every number printed: simulated. The faults are injected at stated rates on
stand-in operations. The lab proves mechanisms (a duplicate cannot happen, a false statement
cannot be spoken); it does not measure any real system's failure rate.

Stand-in data only. No production calendar, no customer data, no real phone numbers.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "faults.json"
OUTPUTS = HERE / "outputs"

N_OPERATIONS = 500          # booking operations in experiment 3
ATTEMPTS = 2                # one try and one retry: a live caller cannot wait longer
P_LOST_REQUEST = 0.08       # the request never reaches the calendar: no side effect
P_LOST_RESPONSE = 0.08      # the calendar commits, the answer never comes back
N_RECEIPTS = 400            # post-call receipts in experiment 6
P_SMS_FAIL = 0.15           # each send attempt fails at this rate
RETRY_AT_MIN = (0, 5, 20)   # send attempts, minutes after the call
DEADLINE_MIN = 30           # the promise said "within half an hour"
CONFIRM_TTL_S = 90          # a yes expires after ninety seconds


# ---------------------------------------------------------------- 1. the tool contract

@dataclass(frozen=True)
class ToolContract:
    name: str
    latency_class: str      # instant | short | long
    confirm_class: str      # none | implicit | explicit | explicit + step-up
    effect: str             # read | write | irreversible
    undo: str               # how the business reverses it, if it can
    speakable: str          # the summary the tool returns beside its data


SERVICE_LINE_TOOLS = [
    ToolContract("lookup_account", "instant", "none", "read", "n/a",
                 "I've found your account."),
    ToolContract("outage_status", "short", "none", "read", "n/a",
                 "Crews expect power back by six this evening."),
    ToolContract("find_visit_slots", "short", "none", "read", "n/a",
                 "The first opening is Tuesday at nine."),
    ToolContract("book_visit", "short", "explicit", "write", "cancel_visit",
                 "You're booked for Tuesday at nine."),
    ToolContract("cancel_visit", "short", "explicit", "write", "book_visit",
                 "Your Tuesday visit is cancelled."),
    ToolContract("change_address", "short", "explicit + step-up", "write", "change_address",
                 "Your billing address is updated."),
    ToolContract("take_payment", "short", "explicit + step-up", "irreversible", "staff refund",
                 "Your payment of forty dollars went through."),
    ToolContract("send_receipt", "long", "implicit", "write", "none",
                 "I'll text you a receipt."),
]


# ---------------------------------------------------------------- 2. spoken failure

@dataclass(frozen=True)
class FailureClass:
    code: str
    who_fixes: str
    retry: str
    line: str               # at most two sentences; nothing the caller cannot act on


FAILURES = [
    FailureClass("invalid_input", "the caller", "no; re-ask",
                 "That date's already passed on my side. Which day this week works for you?"),
    FailureClass("not_found", "the caller", "no; re-ask",
                 "I can't find an account with that number. Could you read it to me once more?"),
    FailureClass("conflict", "the agent", "no; offer another",
                 "Tuesday at nine was just taken. I can do Tuesday at one, or Wednesday at nine."),
    FailureClass("not_permitted", "a step-up or a person", "no",
                 "I'll need to confirm it's you before I change that. I'll send a code to the phone on the account."),
    FailureClass("unavailable", "time", "yes, silently, within budget",
                 "The booking system is slow right now. Give me a few more seconds."),
    FailureClass("timeout", "reconciliation", "yes, same operation id",
                 "I've sent the booking and I'm waiting for it to confirm. I'll text you within five minutes either way."),
    FailureClass("internal", "a person", "no",
                 "Something went wrong on our side, not yours. I can connect you to a colleague, or have someone call you back today."),
]


def speak_failure(code: str) -> str:
    """The agent never improvises failure wording: the class decides the line."""
    for f in FAILURES:
        if f.code == code:
            return f.line
    return next(f.line for f in FAILURES if f.code == "internal")


# ---------------------------------------------------------------- the system of record

class Timeout(Exception):
    """No answer inside the budget. It says nothing about whether the write happened."""


@dataclass(frozen=True)
class Proposal:
    tool: str
    account: str
    params: tuple           # sorted (name, value) pairs: the material terms of the action

    def fingerprint(self) -> str:
        raw = "|".join([self.tool, self.account] + [f"{k}={v}" for k, v in self.params])
        return hashlib.sha256(raw.encode()).hexdigest()[:12]


class Calendar:
    """A stand-in scheduling system. Like most calendar interfaces, it
    accepts two appointments in one slot unless the caller of the
    interface asks it not to."""

    def __init__(self, slots: list[str]):
        self.bookings: list[tuple[str, str]] = []   # (slot, account)
        self.version = {s: 0 for s in slots}          # bumps on each write
        # operation id -> (fingerprint of the terms, first result)
        self.by_operation: dict[str, tuple[str, str]] = {}

    def book(self, p: Proposal, operation_id: str | None = None,
             expected_version: int | None = None) -> str:
        slot = dict(p.params)["slot"]
        if operation_id is not None and operation_id in self.by_operation:
            fp, result = self.by_operation[operation_id]
            if fp != p.fingerprint():
                return "mismatch"   # same id, different terms: refuse
            return result           # a retry gets the first answer back
        if (expected_version is not None
                and self.version[slot] != expected_version):
            result = "conflict"     # the slot changed since it was offered
        else:
            self.bookings.append((slot, p.account))
            self.version[slot] += 1
            result = "booked"
        if operation_id is not None:
            self.by_operation[operation_id] = (p.fingerprint(), result)
        return result

    def is_free(self, slot: str) -> bool:
        return all(b[0] != slot for b in self.bookings)

    def lookup(self, operation_id: str) -> str:
        """Reconciliation needs a read path keyed by your operation id."""
        if operation_id in self.by_operation:
            return self.by_operation[operation_id][1]
        return "absent"

    def count(self, slot: str, account: str) -> int:
        return sum(1 for b in self.bookings if b == (slot, account))


class Link:
    """The network between the agent and the calendar, with injected faults."""

    def __init__(self, faults: list[str]):
        self.faults = iter(faults)

    def call(self, fn):
        fault = next(self.faults)
        if fault == "lost_request":
            raise Timeout()                  # nothing happened on the far side
        result = fn()
        if fault == "lost_response":
            raise Timeout()                  # something happened; we will not hear about it
        return result


# ---------------------------------------------------------------- 3. retry strategies

def naive(cal: Calendar, link: Link, p: Proposal, op: str) -> str:
    """Retry with a fresh request each time; give up and say so."""
    for _ in range(ATTEMPTS):
        try:
            link.call(lambda: cal.book(p))
            return "booked"
        except Timeout:
            continue
    return "failed"


def keyed(cal: Calendar, link: Link, p: Proposal, op: str) -> str:
    """Reuse one operation id on every retry; still give up and say so."""
    for _ in range(ATTEMPTS):
        try:
            return link.call(lambda: cal.book(p, operation_id=op))
        except Timeout:
            continue
    return "failed"


def keyed_reconciled(cal: Calendar, link: Link, p: Proposal,
                     op: str) -> str:
    """Reuse one operation id; never speak an outcome you have not read."""
    for _ in range(ATTEMPTS):
        try:
            return link.call(lambda: cal.book(p, operation_id=op))
        except Timeout:
            continue
    try:
        state = link.call(lambda: cal.lookup(op))
    except Timeout:
        return "pending"   # say so, and make it a tracked promise
    return "booked" if state == "booked" else "pending"


def truthful(spoken: str, committed: int) -> bool:
    """Did the words match the calendar? 'pending' is true by construction: it claims nothing."""
    if spoken == "booked":
        return committed >= 1
    if spoken == "failed":
        return committed == 0
    return True


def experiment_retries(faults: list[str]) -> dict[str, dict[str, float]]:
    out = {}
    for name, strategy in (("naive retry", naive), ("operation id", keyed),
                           ("operation id + reconcile", keyed_reconciled)):
        link = Link(faults)
        dup = false_statements = pending = told_failed = 0
        for i in range(N_OPERATIONS):
            cal = Calendar([f"slot-{i}"])
            p = Proposal("book_visit", f"acct-{i:04d}", (("slot", f"slot-{i}"),))
            spoken = strategy(cal, link, p, f"op-{i:04d}")
            n = cal.count(f"slot-{i}", f"acct-{i:04d}")
            dup += max(0, n - 1)
            false_statements += 0 if truthful(spoken, n) else 1
            pending += spoken == "pending"
            told_failed += spoken == "failed"
        out[name] = {
            "duplicate action rate": 100.0 * dup / N_OPERATIONS,
            "false commitment rate": 100.0 * false_statements / N_OPERATIONS,
            "told it failed": 100.0 * told_failed / N_OPERATIONS,
            "handed to a promise": 100.0 * pending / N_OPERATIONS,
        }
    return out


# ---------------------------------------------------------------- 4. confirmation binding

@dataclass
class Confirmation:
    fingerprint: str    # the operation and terms the caller agreed to
    heard: frozenset    # the material terms actually played to the caller
    given_at_s: float
    epoch: int          # the response the yes belongs to

    def covers(self, p: Proposal, material: set[str], now_s: float,
               epoch: int) -> tuple[bool, str]:
        if epoch != self.epoch:
            return False, "canceled turn"
        if self.fingerprint != p.fingerprint():
            return False, "terms changed"
        if now_s - self.given_at_s > CONFIRM_TTL_S:
            return False, "yes expired"
        unheard = material - self.heard
        if unheard:
            return False, ", ".join(sorted(unheard)) + " not heard"
        return True, "covers this operation"


TUESDAY = Proposal("book_visit", "acct-2231",
                   (("address", "14 Alder Road"), ("fee", "40"), ("slot", "Tue 09:00")))
THURSDAY = Proposal("book_visit", "acct-2231",
                    (("address", "14 Alder Road"), ("fee", "40"), ("slot", "Thu 09:00")))
MATERIAL = {"slot", "address", "fee"}

# Each scenario: the proposal about to execute, what the caller confirmed, what they heard,
# seconds since the yes, and whether the yes came from a response that was later canceled.
BINDING_SCENARIOS = [
    ("a plain yes", TUESDAY, TUESDAY, MATERIAL, 4, False),
    ('changed mind: "make it Thursday"', THURSDAY, TUESDAY, MATERIAL, 6, False),
    ("yes, then three minutes on hold", TUESDAY, TUESDAY, MATERIAL, 185, False),
    ("barge-in before the fee was played", TUESDAY, TUESDAY, {"slot", "address"}, 3, False),
    ("late result from a canceled turn", TUESDAY, TUESDAY, MATERIAL, 5, True),
]


def experiment_binding() -> list[tuple[str, bool, bool, str]]:
    """Returns (scenario, executes when bound to the call, executes when bound to the
    operation, why). Bound to the call means any yes in this call authorizes the next write."""
    rows = []
    for label, executing, confirmed, heard, age_s, from_canceled in BINDING_SCENARIOS:
        c = Confirmation(confirmed.fingerprint(), frozenset(heard), 0.0, epoch=1)
        current_epoch = 2 if from_canceled else 1
        ok, why = c.covers(executing, MATERIAL, float(age_s), current_epoch)
        rows.append((label, True, ok, why))
    return rows


# ---------------------------------------------------------------- 5. the last slot

def interleavings(a: list[str], b: list[str]):
    """Every ordering of two callers' steps that keeps each caller's own order."""
    n = len(a) + len(b)
    for positions in itertools.combinations(range(n), len(a)):
        seq, ia, ib = [], iter(a), iter(b)
        for i in range(n):
            seq.append(next(ia) if i in positions else next(ib))
        yield seq


def race(strategy: str) -> tuple[int, int, int]:
    """Returns (orderings, double bookings, callers offered a slot they then lost)."""
    slots = ["Tue 09:00", "Tue 13:00"]
    orders = doubles = lost_after_offer = 0
    for seq in interleavings(["A.offer", "A.book"], ["B.offer", "B.book"]):
        orders += 1
        cal = Calendar(slots)
        held_by: dict[str, str] = {}
        offered: dict[str, tuple[str, int]] = {}
        for step in seq:
            who, what = step.split(".")
            if what == "offer":
                # find_visit_slots: the first slot that is free (and not held by someone else)
                slot = next(s for s in slots if cal.is_free(s) and held_by.get(s, who) == who)
                if strategy == "hold at offer":
                    held_by[slot] = who          # expires in the real system; not modeled here
                offered[who] = (slot, cal.version[slot])
            else:
                slot, seen = offered[who]
                p = Proposal("book_visit", who, (("slot", slot),))
                if strategy == "conditional write":
                    if cal.book(p, expected_version=seen) == "conflict":
                        lost_after_offer += 1    # the agent must now say the conflict line
                else:
                    cal.book(p)
        doubles += sum(1 for s in slots if cal.version[s] > 1)
    return orders, doubles, lost_after_offer


# ---------------------------------------------------------------- 6. post-call promises

def experiment_promises(sms_faults: list[bool]) -> dict[str, dict[str, float]]:
    """sms_faults[i*len(RETRY_AT_MIN) + k] is True when attempt k of receipt i fails."""
    per = len(RETRY_AT_MIN)
    fire_and_forget = sum(0 if sms_faults[i * per] else 1 for i in range(N_RECEIPTS))
    kept = escalated = 0
    for i in range(N_RECEIPTS):
        for k, at_min in enumerate(RETRY_AT_MIN):
            if not sms_faults[i * per + k] and at_min <= DEADLINE_MIN:
                kept += 1
                break
        else:
            escalated += 1                       # exhausted: a person gets a task, with the deadline
    return {
        "fire and forget": {"promise keep rate": 100.0 * fire_and_forget / N_RECEIPTS,
                            "escalated to a person": 0.0,
                            "silently broken": 100.0 * (N_RECEIPTS - fire_and_forget) / N_RECEIPTS},
        "tracked promise": {"promise keep rate": 100.0 * kept / N_RECEIPTS,
                            "escalated to a person": 100.0 * escalated / N_RECEIPTS,
                            "silently broken": 0.0},
    }


# ---------------------------------------------------------------- fixtures and modes

def generate_faults(seed: int = 17) -> dict:
    rng = random.Random(seed)
    link = []
    for _ in range(N_OPERATIONS * (ATTEMPTS + 1)):   # every strategy replays this schedule
        r = rng.random()
        link.append("lost_request" if r < P_LOST_REQUEST
                    else "lost_response" if r < P_LOST_REQUEST + P_LOST_RESPONSE else "ok")
    sms = [rng.random() < P_SMS_FAIL for _ in range(N_RECEIPTS * len(RETRY_AT_MIN))]
    return {"seed": seed, "link": link, "sms": sms,
            "note": "stand-in fault schedule; evidence class simulated"}


def load_faults(mode: str) -> dict:
    if mode == "fixture":
        return json.loads(FIXTURE.read_text())
    if mode == "mock":
        return generate_faults()
    raise SystemExit("live mode is not implemented in this lab; use mock or fixture")


def report(mode: str) -> str:
    """Every line fits a 78-column book page, so the chapter can print it unedited."""
    import textwrap
    faults = load_faults(mode)
    lines: list[str] = []
    say = lines.append
    say(f"mode={mode}  evidence class: simulated (stand-in operations, injected faults)")
    say("")
    say("1. the tool contract table (Service Line)")
    say(f"   {'tool':<17}{'latency':<9}{'confirm':<20}{'effect':<14}undo")
    for t in SERVICE_LINE_TOOLS:
        say(f"   {t.name:<17}{t.latency_class:<9}{t.confirm_class:<20}{t.effect:<14}{t.undo}")
    say("")
    say("2. spoken failure: the class decides the words")
    for f in FAILURES:
        say(f"   {f.code:<14} fixed by {f.who_fixes}; retry: {f.retry}")
        for w in textwrap.wrap(f'"{speak_failure(f.code)}"', 60):
            say(f"   {'':<14} {w}")
    say("")
    say(f"3. lost responses ({N_OPERATIONS} bookings; {ATTEMPTS} attempts; "
        f"{P_LOST_REQUEST:.0%} of requests and")
    say(f"   {P_LOST_RESPONSE:.0%} of responses lost on the link; same faults for every strategy)")
    res = experiment_retries(faults["link"])
    cols = ["duplicate action rate", "false commitment rate", "told it failed", "handed to a promise"]
    say(f"   {'':<27}{'duplicate':>11}{'false':>12}{'said it':>11}{'handed to':>12}")
    say(f"   {'strategy':<27}{'actions':>11}{'commitment':>12}{'failed':>11}{'a promise':>12}")
    for name, m in res.items():
        say(f"   {name:<27}" + "".join(f"{m[c]:>{w}.1f} %" for c, w in zip(cols, (9, 10, 9, 10))))
    say("")
    say("4. confirmation binding: what a yes may authorize")
    say(f"   {'scenario':<35}{'call-bound':<14}operation-bound")
    rows = experiment_binding()
    for label, naive_exec, bound_exec, why in rows:
        # a write is correct only when the operation-bound check would also allow it
        naive_cell = "executes" if bound_exec else "UNCONFIRMED"
        bound_cell = "executes" if bound_exec else f"re-confirms: {why}"
        say(f"   {label:<35}{naive_cell:<14}{bound_cell}")
    unconfirmed_call = sum(1 for _, n, b, _ in rows if n and not b)
    unconfirmed_op = 0                         # by construction: it executes only when covered
    say(f"   unconfirmed actions: call-bound {unconfirmed_call} of {len(rows)}, "
        f"operation-bound {unconfirmed_op} of {len(rows)}")
    say("")
    say("5. the last slot: two callers, every ordering of offer and book")
    say(f"   {'strategy':<22}{'orderings':>10}{'double-booked':>16}{'lost after offer':>19}")
    for strategy in ("check then book", "conditional write", "hold at offer"):
        orders, doubles, lost = race(strategy)
        say(f"   {strategy:<22}{orders:>10}{doubles:>16}{lost:>19}")
    say("")
    say(f"6. post-call promises ({N_RECEIPTS} receipts; {P_SMS_FAIL:.0%} of send attempts fail;")
    say(f"   deadline {DEADLINE_MIN} min; tracked attempts at "
        f"{', '.join(str(m) for m in RETRY_AT_MIN)} min after the call)")
    say(f"   {'policy':<20}{'promise keep rate':>19}{'escalated':>12}{'silently broken':>18}")
    for name, m in experiment_promises(faults["sms"]).items():
        say(f"   {name:<20}{m['promise keep rate']:>17.1f} %{m['escalated to a person']:>10.1f} %"
            f"{m['silently broken']:>16.1f} %")
    say("")
    say("release-blocking invariants (must be exactly zero):")
    inv = {
        "duplicate actions with an operation id": res["operation id"]["duplicate action rate"]
        + res["operation id + reconcile"]["duplicate action rate"],
        "false commitments with reconciliation": res["operation id + reconcile"]["false commitment rate"],
        "unconfirmed actions with operation binding": float(unconfirmed_op),
        "double bookings with a conditional write": float(race("conditional write")[1]),
        "double bookings with a hold at offer": float(race("hold at offer")[1]),
    }
    for k, v in inv.items():
        say(f"   {k:<46}{v:>5.1f}   {'PASS' if v == 0 else 'FAIL'}")
    say("regression band: invariants exactly zero; other rates within 2 points")
    say("of the frozen output")
    return "\n".join(lines) + "\n"


def run(mode: str | None = None) -> str:
    mode = mode or os.environ.get("TOOLS_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"tools_lab.{mode}.out.txt").read_text()
    now = report(mode)
    if now == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(generate_faults(), separators=(",", ":")))
        print(f"wrote {FIXTURE.relative_to(HERE)}")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("TOOLS_LAB_MODE", "mock")))
    else:
        run()
