"""River Plumbing's Appointment Line: the book's simple example, complete at small scale."""
from __future__ import annotations

import re

from conftest import Caller, make_runtime, MONDAY_NIGHT


async def test_booking_states_the_fee_before_the_yes_and_texts_after(rt):
    c = Caller(rt, pack="river")
    first = await c.start()
    assert first[0] == "River Plumbing, this is the automated booking assistant. How can I help?"
    await c.say("my kitchen drain is blocked", "12 Maple Street", "Jordan", "Wednesday")
    terms = c.said[-1]
    assert re.search(r"The first opening is Wed 30 Sep at 9 am\. There's a \$60 call-out "
                     r"charge, taken off the bill if the job goes ahead\. Shall I book it "
                     r"for 12 Maple Street\?", terms)
    await c.say("yes")
    assert "You're booked for Wed 30 Sep at 9 am." in c.said
    assert rt.store.messages()[0]["body"].startswith("River Plumbing: visit booked Wed 30 Sep")
    slot = rt.store.get("rp_slot", "2026-09-30T09:00-van1")
    assert slot["state"] == "booked" and slot["booking"]["name"] == "Jordan"


async def test_two_callers_cannot_book_the_same_slot(rt):
    a, b = Caller(rt, pack="river", caller="+13125550101"), \
        Caller(rt, pack="river", caller="+13125550102")
    for c in (a, b):
        await c.start()
        await c.say("a leaking tap", "5 Oak Lane", "Sam", "Wednesday")
    # both were offered Wednesday at nine; the first hold wins it, the second gets van 2
    assert "Wed 30 Sep at 9 am" in a.said[-1]
    await a.say("yes")
    await b.say("yes")
    booked = [s for s in rt.store.all("rp_slot") if s["state"] == "booked"
              and s["booking"].get("op") != "seed"]
    assert len({s["id"] for s in booked}) == 2


async def test_questions_come_from_the_desk_facts(rt):
    c = Caller(rt, pack="river")
    await c.start()
    lines = await c.say("how much is a call out")
    assert lines[0] == "The call-out charge is sixty dollars. It is taken off the bill if " \
                       "the job goes ahead."


async def test_a_gas_smell_gets_the_safety_script_and_nothing_else(rt):
    c = Caller(rt, pack="river")
    await c.start()
    await c.say("I think I can smell gas in the basement")
    assert c.said[1].startswith("If you smell gas, leave the house now and call the gas "
                                "emergency line from outside.")
    assert c.of("end") and not c.of("transfer")


async def test_a_burst_pipe_reaches_the_owner_at_any_hour():
    rt = make_runtime(MONDAY_NIGHT)
    c = Caller(rt, pack="river")
    await c.start()
    await c.say("a pipe burst and there's water everywhere")
    t = c.of("transfer")[0]
    assert t["to"] == "the owner" and t["summary"]["whisper"].startswith("Emergency")


async def test_cancel_a_visit_booked_from_this_number(rt):
    c = Caller(rt, pack="river", caller="+13125550199")
    await c.start()
    await c.say("dripping tap", "8 Birch Road", "Robin", "Thursday", "yes")
    d = Caller(rt, pack="river", caller="+13125550199")
    await d.start()
    await d.say("I need to cancel my visit")
    assert "Shall I cancel it?" in d.said[-1]
    await d.say("yes")
    assert any("Your visit is cancelled." in l for l in d.said)


async def test_the_kill_switch_sends_every_call_to_the_owner():
    # Interlude A: with the switch on, every call goes straight to the owner, at any hour.
    rt = make_runtime(MONDAY_NIGHT)
    await rt.set_kill("river", True)
    c = Caller(rt, pack="river")
    lines = await c.start()
    assert "paused" in " ".join(lines)
    assert c.of("transfer")[0]["to"] == "the owner"
    await rt.set_kill("river", False)


async def test_the_switch_stops_a_booking_whose_yes_is_still_being_understood(rt):
    # Chapter 27's stronger contract: the switch pressed mid-turn stops the write that turn
    # was about to make, and the caller goes where the switch sends calls.
    c = Caller(rt, pack="river")
    await c.start()
    await c.say("my kitchen drain is blocked", "12 Maple Street", "Jordan", "Wednesday")
    understand = c.agent.understand

    async def pressed_while_understanding(text):
        await rt.set_kill("river", True)
        return await understand(text)
    c.agent.understand = pressed_while_understanding
    await c.say("yes")
    assert not any(line.startswith("You're booked") for line in c.said)
    assert c.of("transfer")[-1]["to"] == "the owner"
    assert rt.store.get("rp_slot", "2026-09-30T09:00-van1")["state"] != "booked"
    assert rt.store.messages() == []
    await rt.set_kill("river", False)
