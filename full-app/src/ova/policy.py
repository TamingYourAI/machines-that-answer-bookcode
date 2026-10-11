"""The policy gate: the model proposes, policy disposes.

Every line passes here before it is queued for speech. Three checks, all deterministic:

  1. the never-say list: phrases the business rejects (a coverage promise, a guarantee), each
     with the line that replaces it;
  2. the commitment check: a sentence that says something is done ("I've filed", "you're
     booked") must be backed by an operation that committed, or by a record read from the
     system of record this turn ("record:<kind>:<id>"); otherwise it is blocked (builders'
     Chapter 18);
  3. redaction before logs land: card-shaped and SSN-shaped numbers, emails, and phone numbers
     are masked in what the store keeps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .speech import Line

COMMITMENT = re.compile(
    r"\b(?:i've|i have|we've|we have)\s+(?:just\s+)?(?:booked|filed|opened|created|sent|"
    r"texted|emailed|scheduled|cancel+ed|refunded|paid|moved|arranged|updated|added|"
    r"logged|registered|reserved|rebooked)\b|\byou're (?:booked|all set|rebooked)\b|"
    r"\byour claim number is\b|\bis (?:booked|confirmed)\b", re.I)

GLOBAL_NEVER_SAY = [
    (r"\bi(?:'m| am) (?:a|an) (?:human|real person)\b",
     "I'm an automated assistant."),
    (r"\b(?:we|i) (?:can )?guarantee\b|\bis guaranteed\b", None),
]


@dataclass
class Verdict:
    action: str                     # allow | rewrite | block
    line: Line
    reason: str = ""


@dataclass
class Policy:
    never_say: list[tuple[str, str | None]] = field(default_factory=list)
    blocked_line: str = "Let me check that before I tell you it's done."
    log: list[dict] = field(default_factory=list)

    def check(self, line: Line, committed: set[str]) -> Verdict:
        text = line.text
        for pattern, replacement in self.never_say + GLOBAL_NEVER_SAY:
            if re.search(pattern, text, re.I):
                if replacement is None:
                    v = Verdict("block", Line.plain(self.blocked_line), f"never-say: {pattern}")
                else:
                    v = Verdict("rewrite", Line.plain(replacement, line.register),
                                f"never-say: {pattern}")
                self.log.append({"reason": v.reason, "text": text})
                return v
        backed = line.backed_by is not None and (
            line.backed_by in committed or line.backed_by.startswith("record:"))
        if COMMITMENT.search(text) and not backed:
            v = Verdict("block", Line.plain(self.blocked_line), "commitment without a "
                        "committed operation")
            self.log.append({"reason": v.reason, "text": text})
            return v
        return Verdict("allow", line)


_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL = re.compile(r"\b([\w.+-])[\w.+-]*@([\w-]+\.[\w.-]+)\b")
_PHONE = re.compile(r"(?<![\w-])\+?1?[ -.(]*\d{3}[ -.)]*\d{3}[ -.]*(\d{4})\b")


def redact(text: str) -> str:
    """Mask what should never land in a log: cards, SSNs, full emails, full phone numbers."""
    t = _SSN.sub("[ssn]", text)
    t = _CARD.sub(lambda m: "[card]" if len(re.sub(r"\D", "", m.group(0))) >= 13
                  else m.group(0), t)
    t = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", t)
    t = _PHONE.sub(lambda m: f"***-***-{m.group(1)}", t)
    return t
