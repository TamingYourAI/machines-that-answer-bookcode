"""The agent core: one call's turn loop.

Each caller turn is read (rules first, then the brain for leftovers), routed, and answered
with lines that pass the policy gate. The order of routing is the book's order of precedence:

  1. an emergency, whatever else was said;
  2. a request for a person: granted without a fight (one offer when a task is half done,
     then the transfer, or a truthful callback when no one is free);
  3. repeat, help, silence;
  4. the question the agent is waiting on (a read-back, the terms of an action, an offer);
  5. the active skill: fill slots, confirm by risk, act;
  6. a question for the documents, answered and then back to where the call was;
  7. the repair catalog, and a way out when it runs out.

The agent does no I/O of its own. It returns events (lines to say, cards to show, a transfer,
the end) for a transport to deliver, and the transport reports back what was played and heard.
"""
from __future__ import annotations

import asyncio
import dataclasses
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from .dialogue import FormSkill, Skill, read_back_line, render
from .nlu import Frame, SlotSpec, Understanding, understand
from .operations import Confirmation, OpResult, Proposal
from .policy import redact
from .speech import Line, words

if TYPE_CHECKING:
    from .runtime import Pack, Runtime

FINISH = re.compile(r"\b(finish|carry on|continue|keep going|go on|you do it|let's do it|"
                    r"stay|no need|i'll stay)\b")


@dataclass
class CallState:
    call_id: str
    tenant: str
    channel: str
    caller: str = ""
    identity: dict = field(default_factory=lambda: {"level": "none"})
    skill: str | None = None
    slots: dict = field(default_factory=dict)
    tentative: dict = field(default_factory=dict)
    expecting: str | None = None
    pending: dict | None = None
    stack: list = field(default_factory=list)
    asked: dict = field(default_factory=dict)
    fails: dict = field(default_factory=dict)
    changing: bool = False
    person_offered: bool = False
    turn: int = 0
    epoch: int = 0
    done: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    last_line: str | None = None
    ended: bool = False
    outcome: str = ""


@dataclass
class LineRecord:
    line: Line
    status: str = "queued"          # queued | played | heard | interrupted
    heard_chars: int | None = None  # None: all of it (once heard)


class Ctx:
    """What a skill sees and can do during a turn."""

    def __init__(self, agent: "Agent"):
        self.agent = agent

    @property
    def state(self) -> CallState:
        return self.agent.state

    @property
    def pack(self) -> "Pack":
        return self.agent.pack

    @property
    def rt(self) -> "Runtime":
        return self.agent.rt

    @property
    def store(self):
        return self.agent.rt.store

    @property
    def today(self):
        return self.agent.rt.clock.today()

    @property
    def now(self):
        return self.agent.rt.clock.now()

    def say(self, line: Line | str, register: str | None = None) -> str:
        if isinstance(line, str):
            line = Line.plain(line)
        if register:
            line.register = register
        return self.agent.say(line)

    def card(self, kind: str, **data: Any) -> None:
        self.agent.events.append({"type": "card", "kind": kind, **data})

    def emit(self, event: dict) -> None:
        self.agent.events.append(event)

    def offer(self, line: Line | str, name: str, on_yes: Callable, on_no: Callable) -> None:
        """Ask a yes-or-no question whose answer calls back into the skill."""
        self.agent.offers[name] = (on_yes, on_no)
        self.say(line)
        self.state.pending = {"kind": "offer", "name": name}
        self.state.epoch += 1

    async def execute(self, proposal: Proposal, run, reconcile=None,
                      confirmation: Confirmation | None = None) -> OpResult:
        return await self.agent.execute(proposal, run, reconcile, confirmation)


class Agent:
    def __init__(self, rt: "Runtime", pack: "Pack", call_id: str, channel: str,
                 caller: str = "", identity: dict | None = None):
        self.rt, self.pack = rt, pack
        self.state = CallState(call_id, pack.id, channel, caller)
        if identity:
            self.state.identity = dict(identity)
        self.ctx = Ctx(self)
        self.events: list[dict] = []
        self.lines: dict[str, LineRecord] = {}
        self.offers: dict[str, tuple[Callable, Callable]] = {}
        self.lock = asyncio.Lock()
        self.t0 = time.perf_counter()
        # Set by a transport that plays audio: how much of a line was heard. The default
        # (text on a screen) is that a line is heard when it is shown.
        self.heard_of: Callable[[str], int | None] | None = None

    # ------------------------------------------------------------ public surface
    @property
    def call_id(self) -> str:
        return self.state.call_id

    async def begin(self) -> list[dict]:
        async with self.lock:
            if self.rt.killed(self.pack.id):
                await self._killed(start=True)
                return self._flush()
            self.say(Line.plain(self.pack.brief.greeting))
            self._state_event()
            return self._flush()

    async def hear(self, text: str, meta: dict | None = None) -> list[dict]:
        async with self.lock:
            s = self.state
            if s.ended:
                return []
            s.turn += 1
            self.rt.store.add_turn(s.call_id, s.turn, "caller", redact(text), "", meta or {})
            if self.rt.killed(self.pack.id):
                await self._killed()
                return self._flush()
            t = time.perf_counter()
            u = await self.understand(text)
            self._span("understand", "nlu", t, {"act": u.act, "intent": u.intent,
                                                "source": u.source,
                                                "slots": sorted(u.slots)})
            await self.route(u)
            self._state_event()
            self.rt.store.save_state(s.call_id, dataclasses.asdict(s))
            return self._flush()

    async def silence(self, ms: int = 5000) -> list[dict]:
        async with self.lock:
            if self.state.ended:
                return []
            await self._silence()
            return self._flush()

    async def dtmf(self, digits: str) -> list[dict]:
        if digits == "0":
            return await self.hear("operator", {"dtmf": digits})
        return await self.hear(" ".join(digits), {"dtmf": digits})

    async def external(self, event: dict) -> list[dict]:
        """Something happened on another channel during the call (a photo arrived)."""
        async with self.lock:
            if self.state.ended:
                return []
            await self.pack.on_external(self.ctx, event)
            return self._flush()

    def mark(self, line_id: str, status: str = "heard", heard_chars: int | None = None
             ) -> None:
        """The transport reports a line's fate: played in full (heard) or cut (interrupted,
        with the characters of its spoken form that were played)."""
        rec = self.lines.get(line_id)
        if rec is None:
            return
        rec.status = status
        rec.heard_chars = heard_chars if status == "interrupted" else None

    async def end(self, outcome: str = "caller hung up") -> None:
        if not self.state.ended:
            self.state.ended = True
            self.state.outcome = self.state.outcome or outcome
        self.rt.store.end_call(self.call_id, self.state.outcome,
                               self.pack.summary(self.ctx).get("whisper", ""))
        self.rt.end_call(self.call_id)

    # ------------------------------------------------------------ saying things
    def say(self, line: Line) -> str:
        v = self.rt.policies[self.pack.id].check(line, self._committed())
        if v.action != "allow":
            self._span("policy", "policy", time.perf_counter(), {"verdict": v.action,
                                                                 "reason": v.reason})
        line = v.line
        line = self._lexicon(line)
        lid = "ln-" + uuid.uuid4().hex[:8]
        self.lines[lid] = LineRecord(line)
        self.state.last_line = lid
        self.events.append({"type": "say", "id": lid, "text": line.text,
                            "speech": line.speech, "register": line.register,
                            "terms": sorted(line.terms)})
        self.rt.store.add_turn(self.call_id, self.state.turn, "agent", line.text,
                               line.speech, {"id": lid, "register": line.register})
        return lid

    def _lexicon(self, line: Line) -> Line:
        lex = self.pack.brief.lexicon
        if not lex:
            return line
        speech = line.speech
        for shown, spoken in lex.items():
            speech = re.sub(r"\b" + re.escape(shown) + r"\b", spoken, speech)
        if speech == line.speech:
            return line
        # respelling shifts term spans; recompute them from the terms' spoken forms
        spans = {}
        for name, term in line.terms.items():
            i = speech.find(term.spoken)
            if i >= 0:
                spans[name] = (i, i + len(term.spoken))
        return dataclasses.replace(line, speech=speech, spans=spans)

    def _committed(self) -> set[str]:
        return {o["id"] for o in self.rt.store.ops(self.call_id) if o["state"] == "committed"}

    def _flush(self) -> list[dict]:
        out, self.events = self.events, []
        return out

    def _state_event(self) -> None:
        s = self.state
        self.events.append({"type": "state", "skill": s.skill, "expecting": s.expecting,
                            "identity": s.identity.get("level"),
                            "pending": (s.pending or {}).get("kind")})

    def _span(self, name: str, layer: str, t_start: float, meta: dict | None = None) -> None:
        now = time.perf_counter()
        self.rt.store.add_span(self.call_id, self.state.turn, layer, name,
                               (t_start - self.t0) * 1000, (now - self.t0) * 1000, meta)

    def heard_terms(self, line_id: str) -> set[str]:
        rec = self.lines.get(line_id)
        if rec is None:
            return set()
        if self.heard_of is not None:
            chars = self.heard_of(line_id)
            if rec.status == "interrupted":
                chars = rec.heard_chars
            return rec.line.heard_terms(chars)
        if rec.status == "interrupted":
            return rec.line.heard_terms(rec.heard_chars)
        return set(rec.line.terms)

    # ------------------------------------------------------------ understanding
    def frame(self) -> Frame:
        s = self.state
        sk = self.skill()
        expecting: SlotSpec | None = None
        others: list[SlotSpec] = []
        if isinstance(sk, FormSkill):
            if s.expecting:
                expecting = sk.slot(s.expecting).spec()
            if s.pending and s.pending.get("kind") == "slot":
                expecting = sk.slot(s.pending["slot"]).spec()
            specs = sk.slot_specs(self.ctx)
            if s.changing or (s.pending and s.pending.get("kind") == "action"):
                specs = [x.spec() for x in sk.slots]
            others = [x for x in specs if expecting is None or x.name != expecting.name]
        return Frame(expecting, bool(s.pending), others, self.pack.intents,
                     self.rt.clock.today())

    async def understand(self, text: str) -> Understanding:
        f = self.frame()
        u = understand(text, f)
        if u.act in ("unclear", "question") or (u.act == "value" and not u.slots
                                                and not u.intent):
            t = time.perf_counter()
            u2 = await self.rt.brain.understand(text, f, u)
            if u2.source != "rules":
                self._span("brain.understand", "llm", t, {"act": u2.act})
            u = u2
        return u

    # ------------------------------------------------------------ skills
    def skill(self, name: str | None = None) -> Skill | None:
        n = name or self.state.skill
        return self.pack.skills.get(n) if n else None

    async def start_skill(self, name: str, u: Understanding | None = None) -> None:
        s = self.state
        sk = self.skill(name)
        if sk is None:
            await self.repair("out_of_scope")
            return
        text = u.text if u else None
        if text:
            s.facts[f"request:{name}"] = text
        if sk.needs_identity and s.identity.get("level") == "none" and self.pack.verify_skill:
            if s.skill:
                s.stack.append({"skill": s.skill, "slots": s.slots, "expecting": s.expecting})
            s.stack.append({"skill": name, "slots": {}, "fresh": True, "text": text})
            self._switch(self.pack.verify_skill)
            await self._begin(self.skill(), text)
            return
        if s.skill and s.skill != name:
            s.stack.append({"skill": s.skill, "slots": s.slots, "expecting": s.expecting})
        self._switch(name)
        await self._begin(sk, text)

    def _switch(self, name: str, slots: dict | None = None) -> None:
        s = self.state
        s.skill, s.slots, s.expecting, s.tentative = name, dict(slots or {}), None, {}
        s.person_offered, s.changing, s.asked = False, False, {}

    async def _begin(self, sk: Skill, text: str | None) -> None:
        """Start a skill, using what the caller already said to fill its slots."""
        if isinstance(sk, FormSkill) and text:
            if sk.prefill:
                await sk.prefill(self.ctx)
            if sk.intro:
                self.ctx.say(render(self.ctx, sk.intro))
            u = understand(text, self.frame())
            if sk.opening_slot and sk.opening_slot not in self.state.slots:
                u.slots.setdefault(sk.opening_slot, text.strip())
            if not u.slots or not await self.fill(sk, u):
                await self.next_step()
            return
        await sk.start(self.ctx)

    async def complete_skill(self, closing: bool = True) -> None:
        s = self.state
        if s.skill:
            s.done.append(s.skill)
        self._switch(None)
        s.skill = None
        if s.stack:
            frame = s.stack.pop()
            self._switch(frame["skill"], frame["slots"])
            sk = self.skill()
            if frame.get("fresh"):
                await self._begin(sk, frame.get("text"))
            else:
                label = self.pack.labels.get(s.skill, "where we were")
                self.ctx.say(f"Now, back to {label}.")
                await self.next_step()
            return
        if closing:
            self.ctx.offer("Is there anything else I can help with?", "anything_else",
                           self._anything_yes, self._anything_no)

    async def _anything_yes(self, ctx: Ctx) -> None:
        ctx.say("What else can I help with?")

    async def _anything_no(self, ctx: Ctx) -> None:
        await self.goodbye()

    async def next_step(self) -> None:
        s = self.state
        sk = self.skill()
        if not isinstance(sk, FormSkill):
            return
        open_slots = sk.open_slots(s.slots)
        if open_slots:
            slot = open_slots[0]
            s.expecting = slot.name
            n = s.asked.get(slot.name, 0)
            s.asked[slot.name] = n + 1
            text = slot.reask if (n and slot.reask) else slot.ask
            self.ctx.say(render(self.ctx, text))
            return
        s.expecting = None
        if sk.terms is None:
            if sk.done:
                await sk.done(self.ctx, OpResult("", "committed"))
            return
        proposal, line = sk.terms(self.ctx)
        lid = self.ctx.say(line)
        s.epoch += 1
        s.pending = {"kind": "action", "skill": sk.name, "line": lid, "epoch": s.epoch,
                     "proposal": {"tool": proposal.tool, "subject": proposal.subject,
                                  "terms": [list(t) for t in proposal.terms]}}

    async def fill(self, sk: FormSkill, u: Understanding) -> bool:
        """Put the values the caller gave into the skill's slots, confirming by risk."""
        s = self.state
        names = [x.name for x in sk.slots]
        vals = {k: v for k, v in u.slots.items() if k in names}
        if not vals:
            return False
        accepted, risky, said_problem = False, [], False
        for slot in sk.slots:
            if slot.name not in vals:
                continue
            if slot.name in s.slots and not s.changing and slot.name != s.expecting:
                continue
            v = vals[slot.name]
            problem = slot.check(self.ctx, v) if slot.check else None
            if problem:
                self.ctx.say(problem)
                s.slots.pop(slot.name, None)
                s.expecting = slot.name
                said_problem = True
                continue
            if slot.risk == "low" or s.changing:
                s.slots[slot.name] = v
                accepted = True
                if slot.on_fill:
                    await slot.on_fill(self.ctx, v)
            else:
                risky.append((slot, v))
        s.changing = False
        if accepted or risky:
            s.fails.pop("unclear", None)
        if risky:
            s.tentative = {sl.name: v for sl, v in risky[1:]}
            self.offer_value(risky[0][0], risky[0][1])
            return True
        if accepted:
            if not s.pending:
                await self.next_step()
            return True
        return said_problem

    def offer_value(self, slot, value) -> None:
        s = self.state
        lid = self.ctx.say(read_back_line(self.ctx, slot, value))
        s.epoch += 1
        s.pending = {"kind": "slot", "slot": slot.name, "value": value, "line": lid,
                     "epoch": s.epoch}
        s.expecting = slot.name

    async def accept_slot(self, name: str, value: Any) -> None:
        s = self.state
        sk = self.skill()
        s.slots[name] = value
        slot = sk.slot(name)
        if slot.on_fill:
            await slot.on_fill(self.ctx, value)
        if s.ended or s.skill != sk.name:
            return
        if s.tentative:
            nxt, v = next(iter(s.tentative.items()))
            del s.tentative[nxt]
            self.offer_value(sk.slot(nxt), v)
            return
        if not s.pending:
            await self.next_step()

    # ------------------------------------------------------------ routing
    async def route(self, u: Understanding) -> None:
        s = self.state
        if await self.pack.emergency(self.ctx, u.text):
            return
        if u.act == "silence":
            await self._silence()
            return
        s.fails.pop("silence", None)
        if u.act == "person":
            await self.person(u)
            return
        if s.pending and s.pending.get("kind") == "offer" and \
                s.pending.get("name") == "person_or_finish" and u.act != "repeat":
            s.pending = None
            if FINISH.search(u.text.lower()) and u.act != "yes":
                self.ctx.say("Sure, let's finish it.")
                await self.reprompt()
                return
            await self.transfer()
            return
        if u.act == "repeat":
            await self.repeat()
            return
        if u.act == "help":
            self.ctx.say(self.pack.brief.capabilities)
            await self.reprompt(quiet=True)
            return
        if u.intent == "are_you_a_person":
            self.ctx.say(self.pack.brief.are_you_a_person)
            await self.reprompt(quiet=True)
            return
        if s.pending and await self.on_pending(u):
            return
        if u.act == "goodbye":
            await self.goodbye()
            return
        sk = self.skill()
        if sk is not None:
            if isinstance(sk, FormSkill) and await self.fill(sk, u):
                return
            if await sk.handle(self.ctx, u):
                return
            if u.act == "skip" and isinstance(sk, FormSkill) and s.expecting:
                slot = sk.slot(s.expecting)
                if slot.optional:
                    await self.accept_slot(slot.name, None)
                    return
            if u.intent and u.intent != sk.name and u.intent in self.pack.skills and \
                    u.intent not in [f["skill"] for f in s.stack] and \
                    u.intent != self.pack.verify_skill:
                target = self.pack.skills[u.intent]
                if getattr(target, "inline", False):
                    await target.start(self.ctx)
                    await self.reprompt()
                else:
                    self.ctx.say(f"Sure. We'll come back to {self.pack.labels.get(sk.name, 'this')} "
                                 "after.")
                    await self.start_skill(u.intent, u)
                return
            if u.act in ("question", "value", "unclear") and await self.answer(u, True):
                return
            await self.repair("out_of_scope" if u.act == "question" else "unclear")
            return
        if u.intent and u.intent in self.pack.skills:
            await self.start_skill(u.intent, u)
            return
        if await self.answer(u, False):
            return
        await self.repair("out_of_scope" if u.act in ("question", "value") else "unclear")

    async def on_pending(self, u: Understanding) -> bool:
        s = self.state
        p = s.pending
        kind = p["kind"]
        sk = self.skill()
        if kind == "offer":
            yes_fn, no_fn = self.offers.get(p["name"], (None, None))
            if u.act in ("yes", "no"):
                s.pending = None
                fn = yes_fn if u.act == "yes" else no_fn
                if fn:
                    await fn(self.ctx)
                return True
            s.pending = None                     # the caller moved on: route normally
            return False
        if u.act == "yes":
            s.pending = None
            s.fails.pop("unclear", None)
            if kind == "slot":
                await self.accept_slot(p["slot"], p["value"])
            elif kind == "action":
                await self.run_action(p)
            return True
        if u.act == "no":
            s.pending = None
            if kind == "slot":
                new = u.slots.get(p["slot"])
                if new is not None and new != p["value"]:
                    self.offer_value(sk.slot(p["slot"]), new)
                else:
                    slot = sk.slot(p["slot"])
                    s.asked[slot.name] = max(1, s.asked.get(slot.name, 0))
                    self.ctx.say("Sorry about that.")
                    s.expecting = slot.name
                    self.ctx.say(render(self.ctx, slot.reask or slot.ask))
                return True
            if kind == "action":
                if u.slots:
                    s.changing = True
                    if not await self.fill(sk, u):
                        await self.next_step()
                    return True
                s.changing = True
                self.ctx.say("What would you like to change?")
                return True
        if kind == "slot" and u.slots.get(p["slot"]) is not None:
            s.pending = None
            self.offer_value(sk.slot(p["slot"]), u.slots[p["slot"]])
            return True
        if kind == "action" and u.slots and isinstance(sk, FormSkill):
            s.pending = None
            s.changing = True
            if not await self.fill(sk, u):
                await self.next_step()
            return True
        if u.act in ("question",) and await self.answer(u, False):
            self.ctx.say("Now, where were we.")
            self._resay(p["line"])
            return True
        if u.act == "goodbye":
            return False
        n = s.fails["yesno"] = s.fails.get("yesno", 0) + 1
        if n > 2:
            s.pending = None
            await self.repair("unclear")
            return True
        self.ctx.say("Sorry, was that a yes or a no?")
        return True

    def _resay(self, line_id: str) -> None:
        rec = self.lines.get(line_id)
        if rec is None:
            return
        lid = self.say(dataclasses.replace(rec.line))
        if self.state.pending is not None:
            self.state.pending["line"] = lid

    async def run_action(self, p: dict) -> None:
        s = self.state
        sk = self.skill(p["skill"])
        if not isinstance(sk, FormSkill) or sk.terms is None or sk.act is None:
            return
        if self.rt.killed(self.pack.id):
            # The switch was pressed while this turn was in flight: no write starts after it
            # (Chapter 27's emergency stop). The caller goes where the switch sends calls.
            self._span(f"tool:{p['proposal']['tool']}", "tool", time.perf_counter(),
                       {"state": "refused", "failure": "kill switch"})
            await self._killed()
            return
        current, _ = sk.terms(self.ctx)
        asked = Proposal(p["proposal"]["tool"], p["proposal"]["subject"],
                         tuple(tuple(t) for t in p["proposal"]["terms"]))
        heard = frozenset(self.heard_terms(p["line"]))
        conf = Confirmation(asked.fingerprint(), heard, time.time(), p["epoch"])
        p.setdefault("operation_id", self.rt.ledgers[self.pack.id].op_id())
        s.facts["last_authorized_operation"] = dict(p)
        self.rt.store.save_state(self.call_id, dataclasses.asdict(s))
        t = time.perf_counter()
        result = await self.execute(current, lambda oid: sk.act(self.ctx, oid),
                                    (lambda oid: sk.reconcile(self.ctx, oid))
                                    if sk.reconcile else None, conf, epoch=p["epoch"],
                                    operation_id=p["operation_id"])
        self._span(f"tool:{current.tool}", "tool", t, {"state": result.state,
                                                        "failure": result.failure})
        if result.state == "refused" and result.failure and (
                "not heard" in result.failure or "expired" in result.failure
                or "changed" in result.failure):
            self.ctx.say("Before I go ahead, let me read that back in full.")
            await self.next_step()
            return
        if sk.done:
            await sk.done(self.ctx, result)
        elif result.state == "committed":
            await self.complete_skill()
        else:
            self.ctx.say(result.line or "I couldn't do that.")

    async def execute(self, proposal: Proposal, run, reconcile=None,
                      confirmation: Confirmation | None = None,
                      epoch: int | None = None, operation_id: str | None = None) -> OpResult:
        ledger = self.rt.ledgers[self.pack.id]
        return await ledger.execute(self.call_id, proposal, run, reconcile, confirmation,
                                    epoch if epoch is not None else self.state.epoch,
                                    self.state.identity.get("level", "none"),
                                    operation_id=operation_id)

    # ------------------------------------------------------------ answers from knowledge
    async def answer(self, u: Understanding, reprompt: bool) -> bool:
        from .knowledge import terms
        if u.act != "question" and len(terms(u.text)) < 2:
            return False                     # "yes", "Jordan": not a question for the docs
        if await self.pack.personal_answer(self.ctx, u):
            if reprompt:
                await self.reprompt()
            return True
        t = time.perf_counter()
        passages = self.pack.knowledge.search(u.text, today=self.rt.clock.today())
        self._span("retrieve", "rag", t, {"hits": [p.source_id for p in passages],
                                           "confidence": [p.confidence for p in passages]})
        if not passages:
            return False
        t = time.perf_counter()
        a = await self.rt.brain.answer(u.text, passages)
        self._span("answer", "llm" if a and a.how != "extractive" else "rag", t,
                   {"how": a.how if a else None, "sources": a.sources if a else []})
        if a is None:
            return False
        line = Line.plain(a.text)
        self.ctx.say(line)
        self.events.append({"type": "sources", "sources": a.sources, "how": a.how})
        if reprompt:
            await self.reprompt()
        elif not self.state.pending and not self.state.skill:
            self.ctx.offer("Is there anything else I can help with?", "anything_else",
                           self._anything_yes, self._anything_no)
        return True

    async def reprompt(self, quiet: bool = False) -> None:
        """Return to the question the call was waiting on."""
        s = self.state
        if s.pending and s.pending.get("line"):
            self._resay(s.pending["line"])
            return
        sk = self.skill()
        if isinstance(sk, FormSkill) and s.expecting:
            slot = sk.slot(s.expecting)
            self.ctx.say(render(self.ctx, slot.reask or slot.ask))
            return
        if not quiet and not s.pending:
            self.ctx.say("What can I help with?")

    async def repeat(self) -> None:
        rec = self.lines.get(self.state.last_line or "")
        if rec is None:
            await self.reprompt()
            return
        p = self.state.pending
        lid = self.say(dataclasses.replace(rec.line))
        if p and self.lines.get(p.get("line", "")) is rec:
            p["line"] = lid              # the question was said again: bind to the new line

    # ------------------------------------------------------------ repair, silence, person
    async def repair(self, kind: str) -> None:
        s = self.state
        n = s.fails[kind] = s.fails.get(kind, 0) + 1
        line = self.pack.repairs.line(kind, n)
        if line is None:
            self.ctx.say("Let me get you to someone who can help.")
            await self.person(Understanding("person"), failover=True)
            return
        self.ctx.say(line)
        if kind == "out_of_scope" and not s.skill and not s.pending:
            self.ctx.say(self.pack.brief.capabilities)
            return
        await self.reprompt(quiet=True)

    async def _silence(self) -> None:
        s = self.state
        n = s.fails["silence"] = s.fails.get("silence", 0) + 1
        line = self.pack.repairs.line("silence", n)
        if line is None:
            self.ctx.say("I'll end the call now. Call back any time.")
            s.outcome = "ended after silence"
            await self._end_event("silence")
            return
        self.ctx.say(line)

    async def person(self, u: Understanding, failover: bool = False) -> None:
        s = self.state
        route = self.pack.person_route(self.ctx)
        sk = self.skill()
        if route.available:
            half_done = isinstance(sk, FormSkill) and bool(s.slots) and sk.quick and \
                sk.name != self.pack.verify_skill
            if half_done and not s.person_offered and not failover:
                s.person_offered = True
                label = self.pack.labels.get(sk.name, "this")
                minutes = "a minute" if route.wait_min <= 1 else \
                    f"{words(route.wait_min)} minutes"
                self.ctx.offer(
                    f"I can put you through to {route.label} now; the wait is about "
                    f"{minutes}. Or I can finish {label} with you in about two minutes. "
                    "Which would you like?", "person_or_finish", self._to_person,
                    self._finish_instead)
                return
            await self.transfer(route)
            return
        s.pending = None
        self.ctx.say(f"No one is free {route.next_open or 'right now'}, and I won't keep "
                     "you waiting on hold.")
        cb = self.pack.skills.get("callback")
        if cb is not None:
            if s.skill and s.skill != "callback":
                s.stack.append({"skill": s.skill, "slots": s.slots,
                                "expecting": s.expecting})
            s.skill, s.slots, s.expecting = "callback", {}, None
            await cb.start(self.ctx)
        else:
            self.ctx.say("Please call back during opening hours.")

    async def _to_person(self, ctx: Ctx) -> None:
        await self.transfer()

    async def _finish_instead(self, ctx: Ctx) -> None:
        ctx.say("Sure, let's finish it.")
        await self.reprompt()

    async def transfer(self, route=None) -> None:
        s = self.state
        route = route or self.pack.person_route(self.ctx)
        summary = self.pack.summary(self.ctx)
        self.ctx.say(f"Putting you through to {route.label} now, with what you've told me.")
        s.outcome = "transferred"
        self.events.append({"type": "transfer", "to": route.label, "number": route.number,
                            "summary": summary})
        await self._end_event("transfer")

    async def goodbye(self) -> None:
        self.ctx.say(self.pack.brief.closing)
        self.state.outcome = self.state.outcome or (
            "completed" if self.state.done else "ended by caller")
        await self._end_event("goodbye")

    async def _end_event(self, reason: str) -> None:
        self.state.ended = True
        self.state.pending = None
        self.events.append({"type": "end", "reason": reason, "outcome": self.state.outcome})

    async def _killed(self, start: bool = False) -> None:
        route = self.pack.switch_route(self.ctx)
        if start:
            self.say(Line.plain(self.pack.brief.greeting.split(".")[0] + "."))
        self.ctx.say("Our automated line is paused right now.")
        self.state.outcome = "kill switch"
        if route.available:
            await self.transfer(route)
        else:
            self.ctx.say(f"No one is free {route.next_open}. Please call back then. Goodbye."
                         if route.next_open else "Please call back later. Goodbye.")
            await self._end_event("kill switch")
