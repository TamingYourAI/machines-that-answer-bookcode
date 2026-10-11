"""Skills as data: slots, confirmation by risk, the terms question, and the repair catalog.

A skill is one task a caller can finish: report a claim, book a visit, check a status. A form
skill is a list of slots, each with its question and its risk, followed by one action whose
terms the agent reads back before it acts (builders' Chapters 4 and 5).

Confirmation by risk (the book's four levels):
  low          none: move to the next question
  identifier   read back in groups, then a yes
  high         the question is the read-back; a yes
  commitment   the terms in the question; the yes binds one operation (the action)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from .nlu import SlotSpec
from .operations import OpResult, Proposal
from .speech import Line, Term

if TYPE_CHECKING:
    from .agent import Ctx

Text = str | Line | Callable[["Ctx"], "str | Line"]


def render(ctx: "Ctx", t: Text) -> Line:
    v = t(ctx) if callable(t) else t
    return v if isinstance(v, Line) else Line.plain(v)


@dataclass
class Slot:
    name: str
    ask: Text
    kind: str                                   # an extractor in ova.nlu.EXTRACTORS
    risk: str = "low"                           # low | identifier | high
    choices: dict[str, list[str]] | None = None
    id_prefix: str = ""
    id_digits: int = 0
    when: Callable[[dict], bool] | None = None  # ask only when this holds
    optional: bool = False                      # "I don't know" is an answer
    reask: Text | None = None                   # a different wording for a repair
    read_back: Callable[["Ctx", Any], Line] | None = None
    check: Callable[["Ctx", Any], "str | None"] | None = None   # a problem line, or None
    on_fill: Callable[["Ctx", Any], Awaitable[None]] | None = None
    keypad: bool = False                        # touch-tones can answer it

    def spec(self) -> SlotSpec:
        return SlotSpec(self.name, self.kind, self.choices, self.id_prefix, self.id_digits)


@dataclass
class Skill:
    """The base: a skill the agent can start from an intent."""
    name: str
    intents: tuple[str, ...] = ()
    needs_identity: bool = False
    description: str = ""                       # for the model's router
    quick: bool = True                          # finishing beats a queue: offer it once

    def slot_specs(self, ctx: "Ctx") -> list[SlotSpec]:
        return []

    async def start(self, ctx: "Ctx") -> None:
        raise NotImplementedError

    async def handle(self, ctx: "Ctx", u) -> bool:
        """Take a turn while active. False: the skill did not use it."""
        return False


@dataclass
class FormSkill(Skill):
    slots: list[Slot] = field(default_factory=list)
    intro: Text | None = None
    terms: Callable[["Ctx"], tuple[Proposal, Line]] | None = None
    act: Callable[["Ctx", str], Awaitable[Any]] | None = None
    reconcile: Callable[["Ctx", str], Awaitable[Any]] | None = None
    done: Callable[["Ctx", OpResult], Awaitable[None]] | None = None
    prefill: Callable[["Ctx"], Awaitable[None]] | None = None
    opening_slot: str | None = None         # the slot the caller's opening words fill

    def slot(self, name: str) -> Slot:
        return next(s for s in self.slots if s.name == name)

    def open_slots(self, values: dict) -> list[Slot]:
        return [s for s in self.slots if s.name not in values
                and (s.when is None or s.when(values))]

    def slot_specs(self, ctx: "Ctx") -> list[SlotSpec]:
        return [s.spec() for s in self.open_slots(ctx.state.slots)]

    async def start(self, ctx: "Ctx") -> None:
        if self.prefill:
            await self.prefill(ctx)
        if self.intro:
            ctx.say(render(ctx, self.intro))
        await ctx.agent.next_step()


# ---------------------------------------------------------------- read-backs

def read_back_line(ctx: "Ctx", slot: Slot, value: Any) -> Line:
    if slot.read_back:
        return slot.read_back(ctx, value)
    from .speech import say_birthdate, say_code, say_date, show_date, say_time
    import datetime as dt
    if slot.kind in ("id", "digits"):
        term = Term(slot.name, str(value), say_code(str(value)), str(value))
        return Line.of("That's ", term, ". Is that right?")
    if slot.kind == "birthdate":
        d = dt.date.fromisoformat(value)
        return Line.of("That's ", Term(slot.name, f"{d:%B} {d.day}, {d.year}",
                                        say_birthdate(d), value), ". Is that right?")
    if slot.kind.startswith("date"):
        d = dt.date.fromisoformat(value)
        return Line.of("So that was ", Term(slot.name, show_date(d, ctx.today),
                                            say_date(d, ctx.today), value), ". Is that right?")
    if slot.kind == "time" and ":" in str(value):
        return Line.of("At ", Term(slot.name, str(value), say_time(str(value)), str(value)),
                       ". Is that right?")
    return Line.of("I have ", Term(slot.name, str(value), str(value), str(value)),
                   ". Is that right?")


# ---------------------------------------------------------------- the repair catalog

@dataclass
class RepairCatalog:
    """A different line for each failure of each kind, and a way out when they run out.
    The same words are never said twice for the same failure (builders' Chapter 4)."""
    lines: dict[str, list[str]] = field(default_factory=lambda: {
        "unclear": ["Sorry, I missed that.",
                    "I'm still not getting it, sorry. You can also type it, or use your "
                    "keypad."],
        "silence": ["Are you still there?",
                    "I'm still here. If now isn't a good time, you can call back any time."],
        "out_of_scope": ["I can't help with that one here.",
                         "That's outside what I can do on this line."],
        "no_match": ["I couldn't match those details.",
                     "Those details still don't match what I have."],
    })

    def line(self, kind: str, n: int) -> str | None:
        """The nth line (1-based) for this kind, or None when the catalog is exhausted."""
        options = self.lines.get(kind, [])
        return options[n - 1] if 0 < n <= len(options) else None
