"""Runners: each one meets the system under test the way a caller would, on one surface."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunResult:
    scenario: str
    runner: str
    call_id: str = ""
    events: list[dict] = field(default_factory=list)
    caller_turns: list[str] = field(default_factory=list)
    say_terms: dict = field(default_factory=dict)
    measures: dict = field(default_factory=dict)
    error: str = ""
