"""Failure cases that the book promises across chapter boundaries."""
import asyncio
import time

import pytest

from ova.operations import Confirmation, Ledger, Proposal, ToolContract
from ova.store import Store
from ova.providers.stt import ScriptSTT
from ova.providers.tts import ToneTTS
from ova.transports.twilio import MediaStreamCall
from ova.voice import VoiceSession
from conftest import make_runtime

CONTRACTS = {"book": ToolContract("book", "short", "explicit", "write", "cancel", "Booked")}


def yes(p):
    return Confirmation(p.fingerprint(), frozenset(p.material), time.time(), 1)


async def test_operation_survives_a_new_call_and_a_process_restart(tmp_path):
    path = tmp_path / "operations.sqlite3"
    p = Proposal.make("book", "alice", slot="Tuesday", fee=60)
    writes = []

    async def write(oid):
        writes.append(oid)
        return {"booking": "b1"}

    first = Ledger(Store(path), CONTRACTS)
    oid = first.op_id()
    await first.execute("call-one", p, write, confirmation=yes(p), epoch=1, operation_id=oid)
    resumed = Ledger(Store(path), CONTRACTS)
    result = await resumed.execute("new-call", p, write, confirmation=yes(p), epoch=1,
                                   operation_id=oid)
    assert result.replayed and result.data == {"booking": "b1"} and len(writes) == 1


async def test_same_terms_can_be_a_separate_deliberate_action():
    ledger = Ledger(Store(), CONTRACTS)
    p = Proposal.make("book", "alice", slot="Tuesday")

    async def write(oid):
        return oid

    one = await ledger.execute("call", p, write, confirmation=yes(p), epoch=1)
    two = await ledger.execute("call", p, write, confirmation=yes(p), epoch=1)
    assert one.op_id != two.op_id and not two.replayed


@pytest.mark.parametrize("change", ["terms", "subject", "scope"])
async def test_operation_id_cannot_be_reused_for_another_proposition(change):
    store = Store()
    ledger = Ledger(store, CONTRACTS, scope="claims")
    p = Proposal.make("book", "alice", slot="Tuesday")

    async def write(oid):
        return {"committed": True}

    r = await ledger.execute("call", p, write, confirmation=yes(p), epoch=1)
    q = Proposal.make("book", "bob" if change == "subject" else "alice",
                      slot="Friday" if change == "terms" else "Tuesday")
    if change == "scope":
        ledger = Ledger(store, CONTRACTS, scope="river")
    refused = await ledger.execute("another-call", q, write, confirmation=yes(q), epoch=1,
                                    operation_id=r.op_id)
    assert refused.state == "refused"
    assert store.op_get(r.op_id)["result"] == {"committed": True}


async def test_unknown_outcome_with_failed_readback_never_writes_twice():
    ledger = Ledger(Store(), CONTRACTS, timeout_s=0.01)
    p = Proposal.make("book", "alice", slot="Tuesday")
    writes = []

    async def lost(oid):
        writes.append(oid)
        await asyncio.sleep(10)

    async def unavailable(oid):
        raise ConnectionError("read path down too")

    first = await ledger.execute("a", p, lost, unavailable, yes(p), 1)
    second = await ledger.execute("b", p, lost, unavailable, yes(p), 1,
                                   operation_id=first.op_id)
    assert first.state == second.state == "unknown" and len(writes) == 1


async def test_concurrent_retries_share_one_write():
    ledger = Ledger(Store(), CONTRACTS)
    p = Proposal.make("book", "alice", slot="Tuesday")
    writes = []

    async def slow(oid):
        writes.append(oid)
        await asyncio.sleep(0.02)
        return {"ok": True}

    oid = ledger.op_id()
    results = await asyncio.gather(*[
        ledger.execute("call", p, slow, confirmation=yes(p), epoch=1, operation_id=oid)
        for _ in range(5)])
    assert len(writes) == 1 and sum(r.replayed for r in results) == 4


async def test_replay_still_checks_current_authorization():
    ledger = Ledger(Store(), CONTRACTS)
    p = Proposal.make("book", "alice", slot="Tuesday")

    async def write(oid):
        return {"private": "booking"}

    r = await ledger.execute("call", p, write, confirmation=yes(p), epoch=1)
    refused = await ledger.execute("other-call", p, write, operation_id=r.op_id)
    assert refused.state == "refused" and refused.data is None


@pytest.mark.parametrize("clear_first", [False, True])
async def test_twilio_marks_follow_audio_and_cleared_marks_never_authorize(clear_first):
    rt = make_runtime()
    agent = rt.new_call("river", "phone")
    sent = []

    async def send(message):
        sent.append(message)

    call = MediaStreamCall(lambda start, sink: VoiceSession(
        agent, ScriptSTT(), ToneTTS(ms_per_char=1), 8000, sink), send)
    try:
        await call.handle({"event": "start", "streamSid": "M1", "start": {"callSid": "C1"}})
        for _ in range(100):
            if any(m["event"] == "mark" for m in sent):
                break
            await asyncio.sleep(0.01)
        mark = next(m for m in sent if m["event"] == "mark")
        assert any(m["event"] == "media" for m in sent[:sent.index(mark)])
        lid = call.pending_marks[mark["mark"]["name"]]
        assert call.session.heard_chars(lid) == 0
        if clear_first:
            await call._clear()
        await call.handle(mark)
        if clear_first:
            assert call.session.heard_chars(lid) == 0
            assert agent.lines[lid].status == "interrupted"
        else:
            assert call.session.heard_chars(lid) is None
            assert agent.lines[lid].status == "heard"
    finally:
        await call.close()


async def test_queued_audio_does_not_count_as_heard():
    rt = make_runtime()
    agent = rt.new_call("river", "webrtc")

    async def sink(event):
        pass

    session = VoiceSession(agent, ScriptSTT(), ToneTTS(), 48000, sink)
    events = await agent.begin()
    lid = next(e["id"] for e in events if e["type"] == "say")
    assert session.heard_chars(lid) == 0
