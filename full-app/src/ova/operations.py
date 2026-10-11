"""Operations: how an agent changes the world safely (builders' Chapter 17).

  - A ToolContract declares each tool's latency class, confirm class, effect, and undo.
  - A Proposal names one operation and its material terms. Its fingerprint is the identity of
    what the caller agrees to.
  - A Confirmation binds a yes to one fingerprint, to the terms the caller actually heard, to a
    time (a yes expires), and to the response it answered.
  - The Ledger executes an operation once under an operation id, moves it along the event
    timeline (proposed, authorized, committed), reconciles an unknown outcome instead of
    retrying blind, and returns a speakable summary or a failure line chosen by class.
  - Promises are operations after the call: a deadline, retries, and an escalation path.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
import weakref
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .store import Store

CONFIRM_TTL_S = 90          # a yes expires after ninety seconds (the book's working value)
TOOL_TIMEOUT_S = 4.0        # a live caller cannot wait longer for a short tool


@dataclass(frozen=True)
class ToolContract:
    name: str
    latency_class: str      # instant | short | long
    confirm_class: str      # none | implicit | explicit | explicit+step-up
    effect: str             # read | write | irreversible
    undo: str               # how the business reverses it, if it can
    speakable: str          # an example of the summary the tool returns beside its data


@dataclass(frozen=True)
class FailureClass:
    code: str
    who_fixes: str
    retry: str
    line: str               # at most two sentences; nothing the caller cannot act on


FAILURES = {f.code: f for f in [
    FailureClass("invalid_input", "the caller", "no; re-ask",
                 "Something in that didn't check out on my side. Could we go over it once "
                 "more?"),
    FailureClass("not_found", "the caller", "no; re-ask",
                 "I can't find a match for that. Could you read it to me once more?"),
    FailureClass("conflict", "the agent", "no; offer another",
                 "That was just taken. Let me find you another."),
    FailureClass("not_permitted", "a step-up or a person", "no",
                 "I'll need to confirm it's you before I can do that."),
    FailureClass("unavailable", "time", "yes, silently, within budget",
                 "Our system is slow right now. Give me a few more seconds."),
    FailureClass("timeout", "reconciliation", "yes, same operation id",
                 "I haven't confirmed the result yet. I'll help you reach someone who "
                 "can check."),
    FailureClass("internal", "a person", "no",
                 "Something went wrong on our side, not yours. I can connect you to a "
                 "colleague, or have someone call you back today."),
]}


def failure_line(code: str) -> str:
    """The agent never improvises failure wording: the class decides the line."""
    return (FAILURES.get(code) or FAILURES["internal"]).line


class ToolError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Proposal:
    tool: str
    subject: str                            # the account, policy, or claim it acts on
    terms: tuple[tuple[str, str], ...]      # sorted (name, value): the material terms

    @classmethod
    def make(cls, tool: str, subject: str, **terms: Any) -> "Proposal":
        return cls(tool, subject, tuple(sorted((k, str(v)) for k, v in terms.items())))

    def fingerprint(self) -> str:
        raw = json.dumps([self.tool, self.subject, self.terms], separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def material(self) -> set[str]:
        return {k for k, _ in self.terms}

    def as_dict(self) -> dict[str, str]:
        return dict(self.terms)


@dataclass
class Confirmation:
    fingerprint: str        # the operation and terms the caller agreed to
    heard: frozenset        # the material terms actually played to the caller
    given_at_s: float
    epoch: int              # the response the yes belongs to

    def covers(self, p: Proposal, now_s: float, epoch: int) -> tuple[bool, str]:
        if epoch != self.epoch:
            return False, "canceled turn"
        if self.fingerprint != p.fingerprint():
            return False, "terms changed"
        if not 0 <= now_s - self.given_at_s <= CONFIRM_TTL_S:
            return False, "yes expired"
        unheard = p.material - self.heard
        if unheard:
            return False, ", ".join(sorted(unheard)) + " not heard"
        return True, "covers this operation"


@dataclass
class OpResult:
    op_id: str
    state: str              # committed | failed | refused | unknown
    data: Any = None
    speakable: str = ""
    failure: str | None = None
    line: str = ""          # what to say when it failed
    replayed: bool = False  # the same operation id had already committed


Runner = Callable[[str], Awaitable[Any]]           # receives the operation id
Reconciler = Callable[[str], Awaitable[Any | None]]


class Ledger:
    """Executes operations once, and remembers every step."""

    def __init__(self, store: Store, contracts: dict[str, ToolContract],
                 timeout_s: float = TOOL_TIMEOUT_S, scope: str = "default"):
        self.store, self.contracts, self.timeout_s = store, contracts, timeout_s
        self.scope = scope
        self._locks = weakref.WeakValueDictionary()

    @staticmethod
    def op_id() -> str:
        """Mint once for an authorized action; persist and reuse on every retry."""
        return "op-" + uuid.uuid4().hex

    def authorize(self, p: Proposal, confirmation: Confirmation | None, epoch: int,
                  identity: str, now_s: float | None = None) -> tuple[bool, str]:
        c = self.contracts.get(p.tool)
        if c is None:
            return False, "unknown tool"
        if c.confirm_class.endswith("step-up") and identity not in ("verified", "signed-in",
                                                                    "stepped-up"):
            return False, "step-up needed"
        if c.confirm_class.startswith("explicit"):
            if confirmation is None:
                return False, "no confirmation"
            return confirmation.covers(p, now_s if now_s is not None else time.time(), epoch)
        return True, "confirm class " + c.confirm_class

    async def execute(self, call_id: str, p: Proposal, run: Runner,
                      reconcile: Reconciler | None = None,
                      confirmation: Confirmation | None = None, epoch: int = 0,
                      identity: str = "none", *, operation_id: str | None = None) -> OpResult:
        oid = operation_id or self.op_id()
        lock = self._locks.setdefault(oid, asyncio.Lock())
        async with lock:
            return await self._execute(oid, call_id, p, run, reconcile,
                                       confirmation, epoch, identity)

    async def _execute(self, oid, call_id, p, run, reconcile, confirmation,
                       epoch, identity) -> OpResult:
        ok, why = self.authorize(p, confirmation, epoch, identity)
        if not ok:
            return OpResult(oid, "refused", failure=why,
                            line=failure_line("not_permitted") if "step-up" in why else "")
        fingerprint = self.scope + ":" + p.fingerprint()
        prior = self.store.op_get(oid)
        if prior and prior.get("fingerprint") != fingerprint:
            return OpResult(oid, "refused", failure="operation terms or scope changed",
                            line=failure_line("internal"))
        if prior and prior["state"] == "committed":
            return OpResult(oid, "committed", prior["result"], replayed=True)

        def save(state, data=None, failure=None):
            self.store.op_put(oid, call_id, p.tool, p.as_dict(), state, data,
                              failure, fingerprint=fingerprint)

        async def resolve():
            try:
                found = await asyncio.wait_for(reconcile(oid), self.timeout_s) \
                    if reconcile else None
            except Exception:
                found = None
            if found is not None:
                save("committed", found)
                return OpResult(oid, "committed", found)
            save("unknown", failure="timeout")
            return OpResult(oid, "unknown", failure="timeout",
                            line=failure_line("timeout"))

        # A crash or a lost answer can leave a write in flight. A missing read-back
        # is not proof of failure and never authorizes submitting the write again.
        if prior and prior["state"] in {"authorized", "unknown"}:
            return await resolve()
        if prior and prior["state"] == "failed":
            code = prior["failure"] or "internal"
            return OpResult(oid, "failed", failure=code, line=failure_line(code))
        save("authorized")
        try:
            data = await asyncio.wait_for(run(oid), timeout=self.timeout_s)
        except asyncio.TimeoutError:
            return await resolve()
        except asyncio.CancelledError:
            save("unknown", failure="canceled while in flight")
            raise
        except ToolError as e:
            save("failed", failure=e.code)
            return OpResult(oid, "failed", failure=e.code, line=failure_line(e.code))
        except Exception as e:                     # noqa: BLE001 - a tool bug is internal
            save("unknown", failure=f"internal: {type(e).__name__}")
            return OpResult(oid, "unknown", failure="internal", line=failure_line("internal"))
        save("committed", data)
        return OpResult(oid, "committed", data)


# ---------------------------------------------------------------- promises

RETRY_AT_S = (0, 300, 1200)     # send attempts: now, five minutes, twenty minutes


@dataclass
class Promise:
    id: str
    call_id: str
    kind: str                   # text | email | callback
    due_at: float
    payload: dict = field(default_factory=dict)
    attempts: int = 0
    state: str = "open"         # open | kept | missed | escalated


Sender = Callable[[Promise], Awaitable[bool]]


class Promises:
    """Commitments made on the call and kept after it. A promise is kept only when its action
    committed before the deadline the caller heard."""

    def __init__(self, store: Store, senders: dict[str, Sender] | None = None,
                 retry_at_s: tuple[int, ...] = RETRY_AT_S):
        self.store = store
        self.senders = senders or {}
        self.retry_at_s = retry_at_s

    def make(self, call_id: str, kind: str, due_in_s: float, payload: dict,
             now: float | None = None) -> Promise:
        now = now if now is not None else time.time()
        p = Promise("pr-" + uuid.uuid4().hex[:10], call_id, kind, now + due_in_s, payload)
        p.payload.setdefault("made_at", now)
        self._save(p)
        return p

    def _save(self, p: Promise, kept_at: float | None = None) -> None:
        self.store.promise_put(p.id, p.call_id, p.kind, p.due_at, p.state, p.attempts,
                               p.payload, kept_at)

    def load(self, row: dict) -> Promise:
        return Promise(row["id"], row["call_id"], row["kind"], row["due_at"],
                       row["payload"], row["attempts"], row["state"])

    async def tick(self, now: float | None = None) -> list[Promise]:
        """Attempt every open promise whose next attempt is due; return what changed."""
        now = now if now is not None else time.time()
        changed = []
        for row in self.store.promises(state="open"):
            p = self.load(row)
            made = p.payload.get("made_at", now)
            if p.kind not in self.senders:          # kept by a person: watch the deadline
                if now > p.due_at:
                    p.state = "escalated"
                    self._save(p)
                    changed.append(p)
                continue
            if p.attempts >= len(self.retry_at_s):
                p.state = "missed" if now > p.due_at else p.state
                if p.state == "missed":
                    p.state = "escalated"
                    self._save(p)
                    changed.append(p)
                continue
            if now < made + self.retry_at_s[p.attempts]:
                continue
            sender = self.senders.get(p.kind)
            p.attempts += 1
            ok = await sender(p) if sender else False
            if ok and now <= p.due_at:
                p.state = "kept"
                self._save(p, kept_at=now)
            elif ok:
                p.state = "missed"
                self._save(p, kept_at=now)
            else:
                self._save(p)
            changed.append(p)
        return changed

    def keep(self, pid: str, now: float | None = None) -> None:
        """A person marks a promise kept (a callback made)."""
        now = now if now is not None else time.time()
        row = next((r for r in self.store.promises() if r["id"] == pid), None)
        if row is None:
            return
        p = self.load(row)
        p.state = "kept" if now <= p.due_at else "missed"
        self._save(p, kept_at=now)

    def keep_rate(self) -> float | None:
        rows = [r for r in self.store.promises() if r["state"] != "open"]
        if not rows:
            return None
        return sum(r["state"] == "kept" for r in rows) / len(rows)
