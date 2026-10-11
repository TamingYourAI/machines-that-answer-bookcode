"""Scenarios in builders' Appendix M format, checked by the book's own validator.

The suite adds two things to the format, both optional, neither required by the book's runners:

- ``caller.answers``: a list of ``[pattern, words]``. After each of the agent's turns, the caller
  answers with the first unused answer whose pattern (a regular expression, matched without
  regard to case) is found in the agent's last line. Without it, or when nothing matches, the
  caller says the next of ``caller.lines`` in order. Answers let one scenario survive an agent that
  asks for the name before the address.
- the companion's claims line, which is not one of the book's three businesses.
"""
from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "chapters" / "appendix-m" / "scenario_lab.py"
EXTRA_LINES = {"claims line"}            # lines the companion adds to the book's three
PACKS = {"river plumbing": "river", "claims line": "claims"}


def _lab():
    spec = importlib.util.spec_from_file_location("scenario_lab", LAB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate(sc: dict) -> list[str]:
    """The book's validator, with the companion's extra line allowed and the suite's additions
    checked."""
    problems = [p for p in _lab().validate(sc)
                if not (p.startswith("line: unknown:") and sc.get("line") in EXTRA_LINES)]
    for i, a in enumerate(sc.get("caller", {}).get("answers", [])):
        if not (isinstance(a, list) and len(a) == 2 and all(isinstance(x, str) and x for x in a)):
            problems.append(f"caller: answer {i + 1} needs a pattern and words")
        else:
            try:
                re.compile(a[0])
            except re.error as e:
                problems.append(f"caller: answer {i + 1} pattern: {e}")
    return problems


@dataclass
class Turn:
    """One caller turn: its pieces, with the pause the caller leaves inside the turn after each."""
    pieces: list[tuple[str, int, int]]

    @property
    def text(self) -> str:
        return " ".join(p[0] for p in self.pieces)


@dataclass
class Scenario:
    data: dict
    path: Path | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def pack(self) -> str:
        return PACKS.get(self.data["line"], self.data["line"])

    def turns(self) -> list[Turn]:
        """The scripted lines, grouped into turns: a pause above zero stays inside the turn, and a
        pause of zero ends it."""
        out, cur = [], []
        for words, ms, pause in self.data["caller"]["lines"]:
            cur.append((words, ms, pause))
            if pause == 0:
                out.append(Turn(cur))
                cur = []
        if cur:
            out.append(Turn(cur))
        return out

    def answers(self) -> list[tuple[re.Pattern, str]]:
        return [(re.compile(p, re.I), w) for p, w in self.data["caller"].get("answers", [])]


class Caller:
    """The simulated caller's choice of what to say next. It is the same for every runner."""

    def __init__(self, sc: Scenario):
        self.script = sc.turns()
        self.answers = sc.answers()
        self.used: set[int] = set()
        self.next_line = 0

    def reply(self, agent_lines: list[str]) -> Turn | None:
        """What to say after the agent's turn. The agent's last line is searched first, because
        the question usually ends the turn; an answer not yet used wins over one already used, and
        a question asked again gets the same answer again."""
        texts = [ln.strip().lower() for ln in reversed(agent_lines) if ln.strip()]
        for fresh in (True, False):
            for text in texts:
                for i, (pat, words) in enumerate(self.answers):
                    if (i not in self.used) == fresh and pat.search(text):
                        self.used.add(i)
                        return Turn([(words, max(400, 70 * len(words.split())), 0)])
        if self.next_line < len(self.script):
            t = self.script[self.next_line]
            self.next_line += 1
            return t
        return None


def load(paths: list[Path]) -> list[Scenario]:
    """Every scenario under the paths, each with the problems the validator found."""
    files = []
    for p in paths:
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    out = []
    for f in files:
        data = json.loads(f.read_text())
        out.append(Scenario(data, f, validate(data)))
    return out
