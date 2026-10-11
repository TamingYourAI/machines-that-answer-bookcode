"""The framework's parts, one mechanism at a time."""
from __future__ import annotations

import asyncio
import datetime as dt
import time

import pytest

from ova.knowledge import KnowledgeBase
from ova.links import Links
from ova.nlu import (Frame, SlotSpec, digit_string, parse_birthdate, parse_date, parse_time,
                     understand)
from ova.operations import (Confirmation, Ledger, Promises, Proposal, ToolContract, ToolError,
                            failure_line)
from ova.policy import Policy, redact
from ova.speech import Line, Term, say_code, say_date, say_digits, say_money, say_time, speakable
from ova.store import Store

TODAY = dt.date(2026, 9, 28)        # a Monday


# ---------------------------------------------------------------- text for the ear

def test_digits_are_grouped_and_never_strand_one():
    assert say_digits("4417") == "four four, one seven"
    assert say_digits("2125550142") == "two one two, five five five, zero one four two"
    assert say_code("CL-204905") == "C L, two zero four, nine zero five"


def test_money_time_and_dates_for_the_ear():
    assert say_money(60) == "sixty dollars"
    assert say_money("124.50") == "one hundred twenty-four dollars and fifty cents"
    assert say_time("09:00") == "nine in the morning"
    assert say_time("17:05") == "five oh five in the evening"
    assert say_date("2026-09-29") == "Tuesday the twenty-ninth of September"
    assert say_date(TODAY - dt.timedelta(days=1), TODAY) == "yesterday"
    assert speakable("It costs $60 at 5 pm.") == \
        "It costs sixty dollars at five in the evening."


def test_a_line_knows_which_terms_were_heard_when_cut():
    line = Line.of("Book ", Term("slot", "Tue 9 am", "Tuesday at nine"), " for ",
                   Term("fee", "$60", "sixty dollars"), "?")
    assert line.heard_terms(None) == {"slot", "fee"}
    cut = line.speech.index("for")                  # cut after the slot, before the fee
    assert line.heard_terms(cut) == {"slot"}


# ---------------------------------------------------------------- understanding by rules

@pytest.mark.parametrize("said,digits", [
    ("four eight one two seven three", "481273"),
    ("q m four eight one, two seven three", "481273"),
    ("double seven oh one", "7701"),
    ("forty eight twelve seventy three", "481273"),
    ("481 273", "481273"),
])
def test_spoken_digits(said, digits):
    assert digit_string(said) == digits


def test_dates_the_way_callers_say_them():
    assert parse_date("yesterday", TODAY) == dt.date(2026, 9, 27)
    assert parse_date("last night around ten", TODAY) == dt.date(2026, 9, 27)
    assert parse_date("on saturday", TODAY) == dt.date(2026, 9, 26)
    assert parse_date("september twenty second", TODAY) == dt.date(2026, 9, 22)
    assert parse_date("the 20th", TODAY) == dt.date(2026, 9, 20)
    assert parse_date("wednesday", TODAY, "future") == dt.date(2026, 9, 30)
    assert parse_date("three days ago", TODAY) == dt.date(2026, 9, 25)


def test_birthdates_and_times():
    assert parse_birthdate("march fourth nineteen eighty five") == dt.date(1985, 3, 4)
    assert parse_birthdate("the 4th of March 1985") == dt.date(1985, 3, 4)
    assert parse_birthdate("3/4/1985") == dt.date(1985, 3, 4)
    assert parse_birthdate("july twenty second nineteen seventy eight") == \
        dt.date(1978, 7, 22)
    assert parse_time("around 5 pm")[0] == "17:00"
    assert parse_time("at three")[0] == "15:00"
    assert parse_time("this morning") == (None, "morning")


def test_a_person_is_never_a_bare_phrase():
    f = Frame(today=TODAY)
    assert understand("agent", f).act == "person"
    assert understand("can I speak to a person please", f).act == "person"
    assert understand("a person hit my car", f).act != "person"
    u = understand("am I talking to a real person", f)
    assert (u.act, u.intent) == ("question", "are_you_a_person")


def test_yes_no_and_a_correction_in_one_breath():
    spec = SlotSpec("reference", "id", id_digits=6)
    f = Frame(expecting=spec, yes_no=True, today=TODAY)
    assert understand("yes that's right", f).act == "yes"
    u = understand("no it's four eight one two seven four", f)
    assert u.act == "no" and u.slots["reference"] == "481274"


# ---------------------------------------------------------------- knowledge for the ear

DOC = """---
source_id: faq
expires: 2027-01-01
---
## How much is a call-out?

The call-out charge is sixty dollars. It is taken off the bill if the job goes ahead.

## Are you open on Sunday?

We don't make visits on Sunday.
"""


def test_retrieval_returns_one_speakable_sentence_and_a_source():
    kb = KnowledgeBase()
    kb.add_markdown(DOC)
    hits = kb.search("how much is the call out charge", today=TODAY)
    assert hits and hits[0].source_id == "faq"
    assert hits[0].sentence.startswith("The call-out charge is sixty dollars.")


def test_retrieval_says_nothing_rather_than_guess():
    kb = KnowledgeBase()
    kb.add_markdown(DOC)
    assert kb.search("do you repair electric cars", today=TODAY) == []
    assert kb.search("how much is a call-out", today=dt.date(2027, 6, 1)) == []  # expired


# ---------------------------------------------------------------- operations

CONTRACTS = {"book": ToolContract("book", "short", "explicit", "write", "cancel", "Booked."),
             "text": ToolContract("text", "short", "implicit", "write", "none", "Sent.")}


def _yes(p: Proposal, heard=None, at=None, epoch=1) -> Confirmation:
    return Confirmation(p.fingerprint(), frozenset(heard if heard is not None else p.material),
                        at if at is not None else time.time(), epoch)


async def test_a_yes_binds_one_operation_once():
    store = Store()
    ledger = Ledger(store, CONTRACTS)
    p = Proposal.make("book", "acct", slot="Tue 09:00", fee=60)
    calls = []

    async def run(op_id):
        calls.append(op_id)
        return {"ok": True}

    oid = ledger.op_id()
    r1 = await ledger.execute("call-1", p, run, confirmation=_yes(p), epoch=1,
                              operation_id=oid)
    r2 = await ledger.execute("call-1", p, run, confirmation=_yes(p), epoch=1,
                              operation_id=oid)
    assert r1.state == r2.state == "committed"
    assert r2.replayed and len(calls) == 1


async def test_a_yes_does_not_cover_unheard_changed_or_expired_terms():
    ledger = Ledger(Store(), CONTRACTS)
    p = Proposal.make("book", "acct", slot="Tue 09:00", fee=60)

    async def run(op_id):
        return {}

    r = await ledger.execute("c", p, run, confirmation=_yes(p, heard={"slot"}), epoch=1)
    assert r.state == "refused" and "fee not heard" in r.failure
    other = Proposal.make("book", "acct", slot="Thu 09:00", fee=60)
    r = await ledger.execute("c", other, run, confirmation=_yes(p), epoch=1)
    assert r.failure == "terms changed"
    r = await ledger.execute("c", p, run, confirmation=_yes(p, at=time.time() - 600), epoch=1)
    assert r.failure == "yes expired"


async def test_a_timeout_is_reconciled_not_retried_blind():
    store = Store()
    ledger = Ledger(store, CONTRACTS, timeout_s=0.05)
    p = Proposal.make("book", "acct", slot="Tue 09:00", fee=60)
    committed = {}

    async def slow(op_id):
        committed[op_id] = True               # the write happens; the answer is lost
        await asyncio.sleep(1)

    async def reconcile(op_id):
        return {"found": True} if committed.get(op_id) else None

    r = await ledger.execute("c", p, slow, reconcile, _yes(p), epoch=1)
    assert r.state == "committed" and r.data == {"found": True}


async def test_failures_speak_by_class():
    ledger = Ledger(Store(), CONTRACTS)
    p = Proposal.make("text", "acct", to="x")

    async def boom(op_id):
        raise ToolError("conflict")

    r = await ledger.execute("c", p, boom)
    assert r.state == "failed" and r.line == failure_line("conflict")


async def test_promises_are_kept_retried_and_escalated():
    store = Store()
    sent = []

    async def flaky(p):
        sent.append(p.id)
        return len(sent) >= 2                   # the first attempt fails

    pr = Promises(store, {"text": flaky}, retry_at_s=(0, 300, 1200))
    t0 = 1_000_000.0
    pr.make("c", "text", 1800, {"to": "+1", "body": "hi"}, now=t0)
    await pr.tick(now=t0)
    await pr.tick(now=t0 + 301)
    assert store.promises()[0]["state"] == "kept"
    pr.make("c", "callback", 60, {}, now=t0)
    await pr.tick(now=t0 + 120)
    assert any(r["state"] == "escalated" for r in store.promises())
    assert pr.keep_rate() == 0.5


# ---------------------------------------------------------------- policy and links

def test_nothing_is_said_as_done_unless_it_committed():
    policy = Policy()
    line = Line.plain("I've filed your claim.")
    assert policy.check(line, set()).action == "block"
    line.backed_by = "op-1"
    assert policy.check(line, {"op-1"}).action == "allow"


def test_never_say_rewrites():
    policy = Policy(never_say=[(r"\byou're covered\b", "Your adjuster decides that.")])
    v = policy.check(Line.plain("Don't worry, you're covered."), set())
    assert v.action == "rewrite" and v.line.text == "Your adjuster decides that."


def test_redaction_before_logs():
    t = redact("card 4111 1111 1111 1111, ssn 123-45-6789, a.b@example.com, 312-555-0142")
    assert "4111" not in t and "123-45" not in t and "a.b@" not in t and "555-0142" not in t
    assert t.endswith("***-***-0142")


def test_links_open_one_thing_until_they_expire():
    links = Links("s3cret", "https://x.test")
    tok = links.token("upload", "CL-1", ttl_s=60, now=1000)
    assert links.verify(tok, "upload", now=1030)["s"] == "CL-1"
    assert links.verify(tok, "status", now=1030) is None
    assert links.verify(tok, "upload", now=1100) is None
    assert links.verify(tok[:-2] + "xx", "upload", now=1030) is None


def test_free_text_drops_what_the_recognizer_added_at_the_edges():
    # Whisper once heard "Jordan." as "Jordan. //"; the booking kept the slashes.
    from ova.nlu import extract_text
    assert extract_text("Jordan. //") == "Jordan"
    assert extract_text("  -- Mill Lane, ") == "Mill Lane"
    assert extract_text("O'Neill-Smith.") == "O'Neill-Smith"
    assert extract_text("//") is None
