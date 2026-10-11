"""The Claims Line, call by call. Every scenario is a whole conversation in text; the same
agent runs behind the browser, WebRTC, and phone transports (tests/test_server.py)."""
from __future__ import annotations

import re

from conftest import VERIFY_ALEX, Caller, make_runtime, MONDAY_NIGHT


def _has(lines, pattern):
    return any(re.search(pattern, l) for l in lines)


async def test_first_sentence_discloses(caller):
    c = caller()
    first = (await c.start())[0]
    assert first.startswith("This is Quillmere Mutual's automated claims assistant.")


async def test_report_a_claim_by_voice_start_to_finish(rt, caller):
    c = caller()
    await c.start()
    await c.say("I need to report a claim, someone backed into my car yesterday")
    assert _has(c.said, r"policy number")
    await c.say(*VERIFY_ALEX)
    assert _has(c.said, r"Thanks, Alex")
    # the opening sentence already gave the type and the day: neither is asked again
    await c.say("no")                                   # is anyone hurt
    assert not _has(c.said, r"What happened\?|When did it happen")
    await c.say("around 5 pm", "on Clark Street near Diversey",
                "I was parked and someone reversed into my rear bumper",
                "yes", "no", "no", "yes")
    terms = c.said[-1]
    assert terms.startswith("Here's what I have: a collision yesterday, at about 5 pm, at "
                            "Clark Street near Diversey.") and terms.endswith(
        "Shall I file the claim?")
    await c.say("yes")
    filed = [l for l in c.said if l.startswith("Your claim is filed.")]
    assert filed and re.search(r"CL-\d{6}", filed[0])
    number = re.search(r"CL-\d{6}", filed[0]).group(0)
    claim = rt.store.get("claim", number)
    assert claim["loss_type"] == "collision" and claim["location"] == \
        "Clark Street near Diversey" and claim["other_party"] is True
    # say it, then send it: the link went to the phone on the policy, as its own operation
    msgs = rt.store.messages()
    assert msgs[0]["to_addr"] == "+13125550142" and number in msgs[0]["body"]
    assert _has(c.said, r"I've texted the link to the mobile ending 0142")
    assert {o["tool"]: o["state"] for o in rt.store.ops()} == {
        "file_claim": "committed", "send_upload_link": "committed"}
    assert _has(c.said, r"rental car, up to \$40 a day")        # not drivable, has rental
    assert c.of("card")[0]["kind"] == "claim"


async def test_a_correction_to_the_terms_is_read_back_again(caller):
    c = caller()
    await c.start()
    await c.say("my car was broken into", *VERIFY_ALEX, "no", "yesterday", "no idea",
                "outside 1500 West Belmont Avenue", "they smashed the window", "yes", "no")
    assert "Shall I file the claim?" in c.said[-1]
    await c.say("no, it was on Saturday")
    assert "on Sat 26 Sep" in c.said[-1] and "Shall I file the claim?" in c.said[-1]


async def test_one_yes_files_one_claim(rt, caller):
    c = caller()
    await c.start()
    await c.say("report a claim, my windshield cracked", *VERIFY_ALEX, "no", "today",
                "this morning", "on the Kennedy Expressway", "a stone hit it", "no")
    await c.say("yes")
    before = rt.store.count("claim")
    # a replayed yes (a retried request, a duplicated event) reaches the ledger again
    agent = c.agent
    p = rt.store.ops(agent.call_id)[0]
    assert p["state"] == "committed"
    import time
    from ova.operations import Confirmation, Proposal
    prop = Proposal("file_claim", "QM-481273", tuple(sorted(
        (k, v) for k, v in p["terms"].items())))
    r = await agent.execute(prop, lambda oid: agent.pack.skills["report_claim"].act(
        agent.ctx, oid), confirmation=Confirmation(prop.fingerprint(), frozenset(prop.material),
                                     time.time(), agent.state.epoch),
                            operation_id=p["id"])
    assert r.replayed and rt.store.count("claim") == before


async def test_an_unheard_fee_is_not_agreed(rt, caller):
    """The caller interrupts the terms before the location is played; their yes does not
    cover it, and the agent reads the terms again instead of filing."""
    c = caller(channel="webrtc")
    await c.start()
    await c.say("I want to report a theft", *VERIFY_ALEX, "no", "yesterday", "no idea",
                "outside 1500 West Belmont Avenue", "my bike rack was stolen", "no", "no")
    terms_id = [e for e in c.events if e["type"] == "say"][-1]["id"]
    rec = c.agent.lines[terms_id]
    cut = rec.line.spans["location"][0] - 1          # cut just before the location
    c.agent.mark(terms_id, "interrupted", cut)
    await c.say("yes")
    assert rt.store.count("claim") == 3               # the three seeded claims only
    assert _has(c.said[-3:], r"let me read that back in full")


async def test_status_by_claim_number(caller):
    c = caller()
    await c.start()
    await c.say("what's the status of my claim", "two zero four eight one seven", "yes",
                "3/4/1985")
    assert _has(c.said, r"inspection is booked for .* between ten in the morning and noon")
    assert _has(c.said, r"Dana Reyes")
    await c.say("yes")
    assert _has(c.said, r"I've texted a link to follow the claim")


async def test_status_waiting_for_photos_offers_the_link(rt):
    c = Caller(rt, caller="+13125550163")
    await c.start()
    await c.say("check on my claim", "five five two eight zero six", "yes",
                "july twenty second nineteen seventy eight")
    assert _has(c.said, r"waiting for photos")
    await c.say("yes")
    assert "CL-207455" in rt.store.messages()[0]["body"]


async def test_questions_from_the_documents_and_never_a_coverage_promise(caller):
    c = caller()
    await c.start()
    lines = await c.say("what is a deductible")
    assert lines[0].startswith("A deductible is the part of a claim you pay yourself.")
    assert c.of("sources")[0]["sources"] == ["qm-glossary"]
    lines = await c.say("is hail damage covered?")
    assert not _has(lines, r"(?i)you're covered|it's covered|we will pay")


async def test_my_policy_needs_verification_then_answers(caller):
    c = caller()
    await c.start()
    await c.say("what's my deductible")
    assert _has(c.said, r"policy number")
    await c.say(*VERIFY_ALEX)
    assert _has(c.said, r"collision deductible is \$500")


async def test_a_person_without_a_fight(caller):
    c = caller()
    await c.start()
    await c.say("agent")
    assert c.of("transfer"), "no task in progress: straight through"
    c = caller()
    await c.start()
    await c.say("my car was stolen", *VERIFY_ALEX, "no")
    await c.say("I want to talk to a person")
    assert _has(c.said, r"wait is about four minutes. Or I can finish your claim")
    await c.say("put me through")
    t = c.of("transfer")[0]
    assert t["summary"]["whisper"].startswith("Verified Alex; reporting; a theft")


async def test_after_hours_a_truthful_callback():
    rt = make_runtime(MONDAY_NIGHT)
    c = Caller(rt)
    await c.start()
    await c.say("operator")
    assert _has(c.said, r"No one is free until eight in the morning tomorrow")
    assert "Shall I set that up?" in c.said[-1]
    await c.say("yes")
    assert rt.store.promises()[0]["kind"] == "callback"


async def test_an_emergency_comes_first(caller):
    c = caller()
    await c.start()
    await c.say("I was in a crash and my son is hurt")
    assert _has(c.said, r"call emergency services now")
    await c.say("we're ok now, I want to report it")
    assert _has(c.said[-1:], r"policy number")


async def test_verification_never_says_which_detail_failed(caller):
    c = caller()
    await c.start()
    await c.say("status of my claim", "481273", "yes", "january 1 1990")
    assert _has(c.said, r"I couldn't match those details")
    await c.say("481273", "yes", "january 2 1990")
    assert c.of("transfer")
    assert not _has(c.said, r"(?i)date of birth (is|was) wrong|wrong date")


async def test_documents_by_email_after_verification(rt, caller):
    c = caller()
    await c.start()
    await c.say("can you send me my proof of insurance", *VERIFY_ALEX, "email please")
    assert _has(c.said, r"I've emailed your proof of insurance to the address on the policy")
    m = rt.store.messages()[0]
    assert m["channel"] == "email" and m["to_addr"] == "alex.rivera@example.com"


async def test_failed_email_never_becomes_a_spoken_delivery_claim(rt, caller):
    class FailedSender:
        name = "failed-test-sender"

        async def send(self, message):
            raise ConnectionError("mail provider unavailable")

    rt.channels.email = FailedSender()
    c = caller()
    await c.start()
    await c.say("can you send me my proof of insurance", *VERIFY_ALEX, "email please")
    assert rt.store.messages()[0]["status"] == "failed"
    assert not _has(c.said, r"I've emailed")
    assert rt.store.ops()[0]["state"] == "failed"


async def test_a_photo_that_arrives_during_the_call_is_acknowledged(rt, caller):
    c = caller(channel="web")
    await c.start()
    await c.say("check on my claim", "204817", "yes", "march 4 1985")
    ev = await c.agent.external({"type": "photos", "claim": "CL-204817", "count": 3,
                                 "total": 5})
    assert ev[0]["text"].startswith("I can see three new photos on claim CL-204817.")


async def test_silence_three_times_ends_politely(caller):
    c = caller()
    await c.start()
    for _ in range(3):
        ev = await c.agent.silence()
    assert ev[-1]["type"] == "end"


async def test_kill_switch_stops_new_calls(rt, caller):
    await rt.set_kill("claims", True)
    c = caller()
    lines = await c.start()
    assert "paused" in " ".join(lines) and c.of("transfer")
    await rt.set_kill("claims", False)


async def test_signed_in_session_skips_verification(caller):
    c = caller(channel="web", identity={"level": "signed-in", "policy": "QM-481273",
                                        "first": "Alex", "kind": "auto"})
    await c.start()
    await c.say("what's the status of my claim")
    assert not _has(c.said, r"policy number")
    assert _has(c.said, r"CL-204817")
