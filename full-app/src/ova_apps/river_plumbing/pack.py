"""River Plumbing's Appointment Line: the book's simple example, complete at small scale.

A two-van plumbing and heating company. The agent books visits against a local calendar with
holds and a conditional write, states the sixty-dollar call-out charge before the yes, texts a
confirmation, cancels a visit, answers the desk's questions from its facts, puts emergencies
through to the owner at any hour, and gives a gas smell the safety script and nothing else
(canon: the Appointment Line; Interlude A).
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ova.dialogue import FormSkill, Slot
from ova.knowledge import KnowledgeBase
from ova.operations import OpResult, Proposal, ToolContract, ToolError
from ova.runtime import Pack, PersonRoute, VoiceBrief
from ova.speech import (Line, Term, say_address, say_date, say_money, say_phone_tail,
                        say_time, show_date, show_time)

HERE = Path(__file__).resolve().parent
FEE = 60
HOLD_S = 120                            # a held slot is released after two minutes
TIMES = ("09:00", "13:00")
VANS = ("van 1", "van 2")

CONTRACTS = {c.name: c for c in [
    ToolContract("find_slot", "short", "none", "read", "n/a",
                 "The first opening is Tuesday at nine."),
    ToolContract("book_visit", "short", "explicit", "write", "cancel_visit",
                 "You're booked for Tuesday at nine."),
    ToolContract("cancel_visit", "short", "explicit", "write", "book_visit",
                 "Your Tuesday visit is cancelled."),
    ToolContract("send_confirmation", "long", "implicit", "write", "none",
                 "I've texted you the details."),
]}

URGENT = r"\b(?:burst|flooding|flooded|water everywhere|pouring|sewage|no water at all|" \
         r"overflowing)\b"
GAS = r"\b(?:smell gas|smells? of gas|smells like gas|gas smell|gas leak)\b"


def slot_id(d: dt.date, hhmm: str, van: str) -> str:
    return f"{d.isoformat()}T{hhmm}-{van.replace(' ', '')}"


class RiverPlumbingPack(Pack):
    id = "river"
    name = "River Plumbing"
    timezone = "America/Chicago"
    contracts = CONTRACTS
    labels = {"book_visit": "your booking", "cancel_visit": "your cancellation"}
    intents = [
        ("cancel_visit", [r"\bcancel\b", r"\bcan't make (?:it|the)\b"]),
        ("book_visit", [r"\b(?:book|schedule|arrange|get|need|send)\b.{0,25}\b(?:visit|"
                        r"plumber|appointment|someone|engineer|technician)\b",
                        r"\b(?:leak|leaking|drip|dripping|blocked|clogged|blockage|drain|"
                        r"toilet|tap|faucet|water heater|boiler|no hot water)\b"]),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.brief = VoiceBrief(
            speaker="River Plumbing's automated booking assistant",
            greeting="River Plumbing, this is the automated booking assistant. How can I help?",
            are_you_a_person="No, I'm the automated booking assistant. I can put you "
                             "through to the owner if you'd like.",
            capabilities="I can book or cancel a visit, and answer questions about our hours "
                         "and charges. For an emergency, I'll put you through to the owner.",
            closing="Thanks for calling River Plumbing. Goodbye.",
            never_say=[(r"\b(?:it's|it is|that's|that is) (?:probably|definitely|likely) "
                        r"(?:safe|fine|nothing)\b",
                        "I can't judge that over the phone. Let's get a plumber to look at "
                        "it.")],
        )
        self.knowledge = KnowledgeBase(synonyms={"open": ["hours"], "charge": ["price",
                                                                            "cost", "fee"],
                                                 "saturday": ["weekend"]})
        self.knowledge.add_dir(HERE / "knowledge")
        self.skills = {s.name: s for s in [self._book(), self._cancel()]}

    # ------------------------------------------------------------ the calendar
    def seed(self, store, clock) -> None:
        self.store = store
        self.clock = clock
        today = clock.today()
        if store.count("rp_slot"):
            return
        for i in range(1, 8):
            d = today + dt.timedelta(days=i)
            if d.weekday() == 6:                     # no visits on Sunday
                continue
            for t in TIMES:
                for van in VANS:
                    store.put("rp_slot", slot_id(d, t, van),
                              {"id": slot_id(d, t, van), "date": d.isoformat(), "time": t,
                               "van": van, "state": "open"})
        # a lived-in week: the first morning is already taken on both vans
        first = today + dt.timedelta(days=1 if today.weekday() != 5 else 2)
        for van in VANS:
            sid = slot_id(first, "09:00", van)
            s = store.get("rp_slot", sid)
            if s:
                s["state"] = "booked"
                s["booking"] = {"name": "(earlier caller)", "op": "seed"}
                store.put("rp_slot", sid, s)

    def find_slot(self, after: dt.date, day: str | None, part: str | None,
                  call_id: str, now_s: float) -> dict | None:
        for s in sorted(self.store.all("rp_slot"), key=lambda x: (x["date"], x["time"])):
            if s["date"] < after.isoformat():
                continue
            if day and s["date"] != day:
                continue
            if part == "morning" and s["time"] >= "12:00":
                continue
            if part in ("afternoon", "evening") and s["time"] < "12:00":
                continue
            held_by_other = s["state"] == "held" and s.get("hold_call") != call_id and \
                s.get("hold_until", 0) > now_s
            if s["state"] == "open" or (s["state"] == "held" and not held_by_other):
                return s
        return None

    def hold(self, s: dict, call_id: str, now_s: float) -> None:
        s.update(state="held", hold_call=call_id, hold_until=now_s + HOLD_S)
        self.store.put("rp_slot", s["id"], s)

    # ------------------------------------------------------------ people and safety
    def person_route(self, ctx) -> PersonRoute:
        now = ctx.now
        number = ctx.store.setting("river:owner_number", "") or ""
        if now.weekday() < 5 and 8 <= now.hour < 17:
            return PersonRoute("the owner", True, 1, number)
        return PersonRoute("the owner", False, 0, number, next_open="until tomorrow morning",
                           callback_by="by nine tomorrow morning")

    def switch_route(self, ctx) -> PersonRoute:
        # The owner presses the switch to take the calls himself, at any hour (Interlude A).
        return PersonRoute("the owner", True, 0, ctx.store.setting("river:owner_number", "") or "")

    async def emergency(self, ctx, text: str) -> bool:
        t = text.lower()
        if re.search(GAS, t):
            ctx.say("If you smell gas, leave the house now and call the gas emergency line "
                    "from outside. Don't use light switches or flames.", register="emergency")
            ctx.say("Once you're safe, call us back and we'll book a visit.")
            ctx.state.outcome = "gas safety script"
            await ctx.agent._end_event("safety")
            return True
        if re.search(URGENT, t):
            ctx.say("That's an emergency. Turn off the water at the main stopcock if you "
                    "can.", register="emergency")
            ctx.state.slots["issue"] = "Emergency: " + text.strip()[:60]
            route = PersonRoute("the owner", True, 0,
                                ctx.store.setting("river:owner_number", "") or "")
            await ctx.agent.transfer(route)
            return True
        return False

    def summary(self, ctx) -> dict:
        s = ctx.state
        issue = s.slots.get("issue") or "Caller"
        wants = s.slots.get("day")
        booked = s.facts.get("booked")
        bits = [issue.rstrip(".").capitalize() + "."]
        if wants:
            bits.append(f"Wants {dt.date.fromisoformat(wants):%A}.")
        bits.append("Booked." if booked else "Not booked.")
        return {"whisper": " ".join(bits), "slots": dict(s.slots), "booked": booked}

    # ------------------------------------------------------------ skills
    def _book(self) -> FormSkill:
        pack = self

        async def prefill(ctx) -> None:
            if ctx.state.caller:
                ctx.state.slots.setdefault("phone", ctx.state.caller)

        def terms(ctx):
            s = ctx.state.slots
            import time as _t
            after = ctx.today + dt.timedelta(days=1)
            slot = pack.find_slot(after, s.get("day"), s.get("part"), ctx.state.call_id,
                                  _t.time())
            if slot is None and s.get("day"):
                ctx.say("That day is full.")
                slot = pack.find_slot(after, None, s.get("part"), ctx.state.call_id,
                                      _t.time())
            if slot is None:
                slot = pack.find_slot(after, None, None, ctx.state.call_id, _t.time())
            pack.hold(slot, ctx.state.call_id, _t.time())
            ctx.state.facts["held"] = slot["id"]
            d = dt.date.fromisoformat(slot["date"])
            when = Term("slot", f"{show_date(d)} at {show_time(slot['time'])}",
                        f"{say_date(d, ctx.today)} at {say_time(slot['time'])}", slot["id"])
            p = Proposal.make("book_visit", s.get("phone", ""), slot=slot["id"],
                              address=s["address"], fee=FEE)
            return p, Line.of("The first opening is ", when, ". There's a ",
                              Term("fee", f"${FEE} call-out charge",
                                   f"{say_money(FEE).replace(' dollars', '-dollar')} "
                                   "call-out charge", str(FEE)),
                              ", taken off the bill if the job goes ahead. Shall I book it "
                              "for ", Term("address", s["address"], say_address(s["address"]),
                                           s["address"]), "?")

        async def act(ctx, op_id: str):
            sid = ctx.state.facts.get("held")
            slot = pack.store.get("rp_slot", sid)
            if slot is None or slot["state"] == "booked" and \
                    slot.get("booking", {}).get("op") != op_id:
                raise ToolError("conflict", "slot taken")
            if slot["state"] == "held" and slot.get("hold_call") != ctx.state.call_id:
                raise ToolError("conflict", "held by another call")
            slot.update(state="booked", booking={
                "op": op_id, "name": ctx.state.slots.get("name"),
                "phone": ctx.state.slots.get("phone"), "address": ctx.state.slots["address"],
                "issue": ctx.state.slots.get("issue"), "fee": FEE})
            pack.store.put("rp_slot", sid, slot)
            return {"slot": sid}

        async def reconcile(ctx, op_id: str):
            for s in pack.store.all("rp_slot"):
                if s.get("booking", {}).get("op") == op_id:
                    return {"slot": s["id"]}
            return None

        async def done(ctx, r: OpResult) -> None:
            s = ctx.state
            if r.state == "failed" and r.failure == "conflict":
                ctx.say("That time was just taken. Let me find you another.")
                s.facts.pop("held", None)
                await ctx.agent.next_step()
                return
            if r.state != "committed":
                ctx.say(r.line or "I couldn't book that.")
                await ctx.agent.person(None, failover=True)
                return
            slot = pack.store.get("rp_slot", r.data["slot"])
            d = dt.date.fromisoformat(slot["date"])
            s.facts["booked"] = slot["id"]
            ctx.say(Line.of("You're booked for ",
                            Term("slot", f"{show_date(d)} at {show_time(slot['time'])}",
                                 f"{say_date(d, ctx.today)} at {say_time(slot['time'])}",
                                 slot["id"]), ".", backed_by=r.op_id))
            ctx.card("booking", booking={"when": f"{show_date(d)} {show_time(slot['time'])}",
                                         "address": s.slots["address"], "fee": FEE})
            phone = s.slots.get("phone")
            if phone:
                body = (f"River Plumbing: visit booked {show_date(d)}, "
                        f"{show_time(slot['time'])}, {s.slots['address']}. ${FEE} call-out, "
                        "off the bill if the job goes ahead. Reply C to cancel.")
                prop = Proposal.make("send_confirmation", phone, slot=slot["id"])

                async def run(op_id):
                    m = await ctx.rt.channels.send_text(s.call_id, phone, body)
                    if m.status == "failed":
                        raise ToolError("unavailable", "text failed")
                    return {"message": m.id}
                tr = await ctx.execute(prop, run)
                if tr.state == "committed":
                    ctx.say(Line.of("I've texted the details to the number ending ",
                                    Term("phone", phone[-4:], say_phone_tail(phone), phone),
                                    ".", backed_by=tr.op_id))
                else:
                    ctx.rt.promises.make(s.call_id, "text", 30 * 60, {"to": phone,
                                                                     "body": body})
                    ctx.say("The text didn't go through yet. I'll keep trying for the next "
                            "half hour.")
            await ctx.agent.complete_skill()

        return FormSkill(
            name="book_visit", intents=("book_visit",), description="Book a plumber's visit.",
            prefill=prefill,
            slots=[
                Slot("issue", "What's the problem?", "text",
                     reask="In a few words, what needs fixing?"),
                Slot("address", "What's the address for the visit?", "place",
                     reask="Could you give me the house number and street?"),
                Slot("name", "And your name?", "text"),
                Slot("phone", "What's the best number to text the details to?", "phone",
                     "identifier", read_back=lambda ctx, v: Line.of(
                         "That's the number ending ", Term("phone", v[-4:],
                                                           say_phone_tail(v), v),
                         ". Is that right?")),
                Slot("day", "Which day suits you? We visit Monday to Saturday.", "date_future",
                     optional=True, reask="Any day this week, or the first opening?"),
            ],
            terms=terms, act=act, reconcile=reconcile, done=done, opening_slot="issue")

    def _cancel(self) -> FormSkill:
        pack = self

        def booking_for(phone: str) -> dict | None:
            for s in sorted(pack.store.all("rp_slot"), key=lambda x: (x["date"], x["time"])):
                if s["state"] == "booked" and s.get("booking", {}).get("phone") == phone:
                    return s
            return None

        async def prefill(ctx) -> None:
            if ctx.state.caller and booking_for(ctx.state.caller):
                ctx.state.slots.setdefault("phone", ctx.state.caller)

        def terms(ctx):
            b = booking_for(ctx.state.slots["phone"])
            if b is None:
                return Proposal.make("cancel_visit", ctx.state.slots["phone"], slot="none"), \
                    Line.plain("I can't find a visit booked for that number. Shall I put you "
                               "through to the owner?")
            d = dt.date.fromisoformat(b["date"])
            p = Proposal.make("cancel_visit", ctx.state.slots["phone"], slot=b["id"])
            return p, Line.of("You have a visit ", Term(
                "slot", f"{show_date(d)} at {show_time(b['time'])}",
                f"{say_date(d, ctx.today)} at {say_time(b['time'])}", b["id"]),
                ". Shall I cancel it?")

        async def act(ctx, op_id):
            b = booking_for(ctx.state.slots["phone"])
            if b is None:
                raise ToolError("not_found")
            b["state"] = "open"
            b["cancelled"] = {"op": op_id, "was": b.pop("booking")}
            pack.store.put("rp_slot", b["id"], b)
            return {"slot": b["id"]}

        async def done(ctx, r: OpResult) -> None:
            if r.state == "committed":
                ctx.say(Line.of("Your visit is cancelled. I've cancelled it on our calendar.",
                                backed_by=r.op_id))
                await ctx.agent.complete_skill()
            elif r.failure == "not_found":
                await ctx.agent.person(None, failover=True)
            else:
                ctx.say(r.line)
                await ctx.agent.complete_skill()

        return FormSkill(
            name="cancel_visit", intents=("cancel_visit",), description="Cancel a visit.",
            prefill=prefill,
            slots=[Slot("phone", "What's the phone number the visit was booked with?",
                        "phone", "identifier", read_back=lambda ctx, v: Line.of(
                            "That's the number ending ", Term("phone", v[-4:],
                                                              say_phone_tail(v), v),
                            ". Is that right?"))],
            terms=terms, act=act, done=done)
