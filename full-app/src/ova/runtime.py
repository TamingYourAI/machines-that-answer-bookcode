"""The runtime: the services every call shares, and the packs it serves.

A pack is one business on the framework: its voice brief, its skills, its tools and their
contracts, its knowledge, and its routes to people. The runtime owns the store, the ledger per
pack, the channels, the signed links, the promises, the brain, the clock, the kill switch, and
a small event bus that carries things that happen on other channels (a photo uploaded, a text
reply) into the live call they belong to.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import secrets
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable
from zoneinfo import ZoneInfo

from .brain import Brain, RulesBrain
from .channels import Channels
from .dialogue import RepairCatalog, Skill
from .knowledge import KnowledgeBase
from .links import Links
from .operations import Ledger, Promises, ToolContract
from .policy import Policy
from .store import Store

if TYPE_CHECKING:
    from .agent import Agent, Ctx


class Clock:
    def __init__(self, tz: str = "America/Chicago", fixed: dt.datetime | None = None):
        self.tz = ZoneInfo(tz)
        self.fixed = fixed.replace(tzinfo=self.tz) if fixed and fixed.tzinfo is None \
            else fixed

    def now(self) -> dt.datetime:
        return self.fixed or dt.datetime.now(self.tz)

    def today(self) -> dt.date:
        return self.now().date()


@dataclass
class VoiceBrief:
    """The voice brief as data (builders' Chapter 3): who is speaking, the disclosure in the
    first sentence, the truthful answer to "are you a person", the never-say list, and the
    pronunciation list."""
    speaker: str
    greeting: str                       # the first line; its first sentence discloses
    are_you_a_person: str
    capabilities: str
    closing: str = "Thanks for calling. Goodbye."
    never_say: list[tuple[str, str | None]] = field(default_factory=list)
    lexicon: dict[str, str] = field(default_factory=dict)     # shown -> spoken
    voice: dict[str, str] = field(default_factory=dict)       # provider -> voice id
    registers: dict[str, str] = field(default_factory=dict)
    version: str = "1.0"


@dataclass
class PersonRoute:
    label: str                          # "a claims specialist"
    available: bool
    wait_min: int = 0
    number: str = ""                    # where a phone transport sends the call
    next_open: str = ""                 # "at eight tomorrow morning"
    callback_by: str = ""               # "by ten tomorrow morning"


class Pack:
    """Subclass per business. The defaults are safe: no emergency handling beyond a person,
    no personal answers, and a whisper that names the skill."""
    id = "pack"
    name = "Pack"
    timezone = "America/Chicago"
    brief: VoiceBrief
    intents: list[tuple[str, list[str]]] = []
    skills: dict[str, Skill] = {}
    contracts: dict[str, ToolContract] = {}
    labels: dict[str, str] = {}         # skill -> "your claim", for "back to your claim"
    verify_skill: str | None = None
    knowledge: KnowledgeBase
    repairs: RepairCatalog

    def __init__(self) -> None:
        self.repairs = RepairCatalog()

    def seed(self, store: Store, clock: "Clock") -> None:
        pass

    def person_route(self, ctx: "Ctx") -> PersonRoute:
        return PersonRoute("a colleague", True, 2)

    def switch_route(self, ctx: "Ctx") -> PersonRoute:
        """Where calls go while the kill switch is on. By default, the person route."""
        return self.person_route(ctx)

    async def emergency(self, ctx: "Ctx", text: str) -> bool:
        return False

    async def personal_answer(self, ctx: "Ctx", u) -> bool:
        return False

    def summary(self, ctx: "Ctx") -> dict:
        s = ctx.state
        return {"whisper": f"{self.labels.get(s.skill or '', 'Caller')}; "
                           f"identity {s.identity.get('level', 'none')}.",
                "slots": dict(s.slots), "identity": dict(s.identity)}

    async def on_external(self, ctx: "Ctx", event: dict) -> None:
        pass

    def public_info(self) -> dict:
        return {"id": self.id, "name": self.name, "speaker": self.brief.speaker,
                "capabilities": self.brief.capabilities}


Listener = Callable[[dict], Awaitable[None]]


class Bus:
    """Keyed pub/sub in one process: key is what the event concerns (a claim, a call)."""

    def __init__(self) -> None:
        self.subs: dict[str, list[Listener]] = {}

    def subscribe(self, key: str, fn: Listener) -> Callable[[], None]:
        self.subs.setdefault(key, []).append(fn)

        def off() -> None:
            if fn in self.subs.get(key, []):
                self.subs[key].remove(fn)
        return off

    async def publish(self, key: str, event: dict) -> int:
        n = 0
        for fn in list(self.subs.get(key, [])):
            await fn(event)
            n += 1
        return n


class Runtime:
    def __init__(self, store: Store | None = None, packs: list[Pack] | None = None,
                 brain: Brain | None = None, channels: Channels | None = None,
                 links: Links | None = None, clock: Clock | None = None,
                 public_url: str = "http://localhost:8080", secret: str | None = None):
        self.store = store or Store()
        self.brain = brain or RulesBrain()
        self.channels = channels or Channels(self.store)
        self.links = links or Links(secret or secrets.token_hex(16), public_url)
        self.clock = clock or Clock()
        self.bus = Bus()
        self.packs: dict[str, Pack] = {}
        self.ledgers: dict[str, Ledger] = {}
        self.policies: dict[str, Policy] = {}
        self.promises = Promises(self.store, {"text": self._send_promised_text,
                                              "email": self._send_promised_email})
        self.calls: dict[str, "Agent"] = {}
        for p in packs or []:
            self.add_pack(p)

    def add_pack(self, pack: Pack) -> None:
        self.packs[pack.id] = pack
        self.ledgers[pack.id] = Ledger(self.store, pack.contracts, scope=pack.id)
        self.policies[pack.id] = Policy(never_say=list(pack.brief.never_say))
        pack.seed(self.store, self.clock)

    def reset_records(self) -> int:
        """Back to each pack's seeded records, for a test run that must start from the same state
        (the ``before`` of builders' Appendix M). Calls and operations are kept."""
        n = self.store.clear_records()
        for pack in self.packs.values():
            pack.seed(self.store, self.clock)
        return n

    def new_call(self, pack_id: str, channel: str, caller: str = "",
                 identity: dict | None = None, call_id: str | None = None) -> "Agent":
        from .agent import Agent
        pack = self.packs[pack_id]
        cid = call_id or f"call-{uuid.uuid4().hex[:12]}"
        agent = Agent(self, pack, cid, channel, caller, identity)
        self.calls[cid] = agent
        self.store.start_call(cid, pack_id, channel, caller)
        return agent

    def end_call(self, call_id: str) -> None:
        self.calls.pop(call_id, None)

    # ------------------------------------------------------------ the kill switch
    def killed(self, pack_id: str) -> bool:
        return self.store.setting("kill:*") == "on" or \
            self.store.setting(f"kill:{pack_id}") == "on"

    async def set_kill(self, pack_id: str, on: bool) -> None:
        self.store.set_setting(f"kill:{pack_id}", "on" if on else "off")
        self.store.event("kill", pack_id, {"on": on})
        await self.bus.publish("kill", {"type": "kill", "pack": pack_id, "on": on})

    # ------------------------------------------------------------ promises
    async def _send_promised_text(self, p) -> bool:
        m = await self.channels.send_text(p.call_id, p.payload["to"], p.payload["body"])
        return m.status in ("sent", "simulated")

    async def _send_promised_email(self, p) -> bool:
        m = await self.channels.send_email(p.call_id, p.payload["to"],
                                           p.payload.get("subject", ""), p.payload["body"])
        return m.status in ("sent", "simulated")

    async def run_promises(self, every_s: float = 15.0) -> None:
        while True:
            try:
                await self.promises.tick()
            except Exception:                    # noqa: BLE001 - keep the loop alive
                pass
            await asyncio.sleep(every_s)
