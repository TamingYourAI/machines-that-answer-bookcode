"""Shared fixtures: a runtime on a fixed clock, and a caller that talks to it in text."""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ova.runtime import Clock, Runtime  # noqa: E402
from ova_apps.claims.pack import ClaimsPack  # noqa: E402
from ova_apps.river_plumbing.pack import RiverPlumbingPack  # noqa: E402

MONDAY_MORNING = dt.datetime(2026, 9, 28, 10, 15)     # a Monday, inside office hours
MONDAY_NIGHT = dt.datetime(2026, 9, 28, 22, 15)


def make_runtime(at: dt.datetime = MONDAY_MORNING) -> Runtime:
    return Runtime(packs=[ClaimsPack(), RiverPlumbingPack()],
                   clock=Clock(fixed=at), secret="test-secret",
                   public_url="https://ova.test")


@pytest.fixture
def rt() -> Runtime:
    return make_runtime()


@pytest.fixture
def rt_night() -> Runtime:
    return make_runtime(MONDAY_NIGHT)


class Caller:
    """Drives one call and keeps what the agent said, in order."""

    def __init__(self, rt: Runtime, pack: str = "claims", channel: str = "phone",
                 caller: str = "+13125550142", identity: dict | None = None):
        self.rt = rt
        self.agent = rt.new_call(pack, channel, caller, identity)
        self.events: list[dict] = []

    async def start(self) -> list[str]:
        return self._lines(await self.agent.begin())

    async def say(self, *turns: str) -> list[str]:
        out: list[str] = []
        for t in turns:
            out = self._lines(await self.agent.hear(t))
        return out

    def _lines(self, events: list[dict]) -> list[str]:
        self.events += events
        return [e["text"] for e in events if e["type"] == "say"]

    @property
    def said(self) -> list[str]:
        return [e["text"] for e in self.events if e["type"] == "say"]

    def of(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["type"] == kind]


@pytest.fixture
def caller(rt):
    def make(**kw) -> Caller:
        return Caller(rt, **kw)
    return make


VERIFY_ALEX = ("q m four eight one two seven three", "yes", "march fourth nineteen eighty five")
