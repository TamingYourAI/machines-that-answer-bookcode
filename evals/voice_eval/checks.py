"""One check per assertion key, each in one family of Chapter 24: the task family (was the work
done, and done honestly) or the experience family (how the call went for the caller).

A check returns ``(passed, detail)``. ``passed`` is None when this runner cannot check the key, and
the family is then reported as partial: never counted as a pass.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

BOOK_TOOLS = {"book_visit"}
CLAIM_TOOLS = {"file_claim"}
BOOKED_LINE = re.compile(r"\byou'?re booked\b|\bbooked (?:you )?for\b", re.I)
FEE_WORDS = re.compile(r"\$\s?\d+|\bdollars?\b|call-out charge|\bfee\b", re.I)
SAFETY_LINE = re.compile(r"leave the house", re.I)


@dataclass
class Ctx:
    record: dict
    runner: str
    measures: dict           # the audio runner's measurements; empty for text
    events: list[dict]       # what the runner received, in order
    spoken: int = 0          # caller turns the runner spoke

    def agent(self) -> list[dict]:
        return [t for t in self.record["turns"] if t["who"] == "agent"]

    def caller(self) -> list[dict]:
        return [t for t in self.record["turns"] if t["who"] == "caller"]

    def committed(self, tools: set[str]) -> list[dict]:
        return [o for o in self.record["operations"]
                if o["tool"] in tools and o["state"] == "committed"]


def booked(v, c: Ctx):
    ops = c.committed(BOOK_TOOLS)
    if not ops:
        return False, "no booking committed"
    if isinstance(v, str):
        heard = [f'{t["text"]} {t.get("speech", "")}' for t in c.agent()
                 if BOOKED_LINE.search(t["text"])]
        if not any(v.lower() in h.lower() for h in heard):
            return False, f"booked, but no booked line names {v}: {heard[-1:] or 'none'}"
    return True, f"{len(ops)} booking committed"


def bookings(v, c: Ctx):
    n = len(c.committed(BOOK_TOOLS))
    return n == v, f"{n} bookings committed"


def no_booking(v, c: Ctx):
    n = len(c.committed(BOOK_TOOLS))
    return (n == 0) == bool(v), f"{n} bookings committed"


def _commit_time(c: Ctx, tools: set[str]) -> float | None:
    ops = c.committed(tools)
    return ops[0]["updated_at"] if ops else None


def fee_before_yes(v, c: Ctx):
    t_commit = _commit_time(c, BOOK_TOOLS)
    if t_commit is None:
        return False, "no booking, so no yes to check"
    yes = [t for t in c.caller() if t["t"] <= t_commit]
    if not yes:
        return False, "no caller turn before the commit"
    t_yes = yes[-1]["t"]
    fee = [t for t in c.agent() if t["t"] <= t_yes and
           ("fee" in t.get("terms", []) or FEE_WORDS.search(t["text"]))]
    ok = bool(fee) == bool(v)
    return ok, ("the fee was said before the yes" if fee else "no fee line before the yes")


def confirmed_after_commit(v, c: Ctx):
    t_commit = _commit_time(c, BOOK_TOOLS)
    lines = [t for t in c.agent() if BOOKED_LINE.search(t["text"])]
    if t_commit is None:
        return (not lines) == bool(v), ("said booked without a booking" if lines
                                        else "nothing booked and nothing claimed")
    early = [t for t in lines if t["t"] < t_commit]
    return (not early) == bool(v), (f"{len(early)} booked line(s) before the commit" if early
                                    else "every booked line after the commit")


def safety_script(v, c: Ctx):
    said = any(SAFETY_LINE.search(t["text"]) for t in c.agent())
    clean = not c.committed(BOOK_TOOLS)
    return (said and clean) == bool(v), ("safety line said, nothing booked" if said and clean
                                         else f"safety line said: {said}; bookings: {not clean}")


def transferred(v, c: Ctx):
    out = c.record["call"]["outcome"].lower()
    ev = any(e.get("type") == "transfer" for e in c.events)
    got = ev or "transfer" in out or "person" in out
    return got == bool(v), f"outcome: {out or 'none'}; transfer event: {ev}"


def texted(v, c: Ctx):
    sent = [m for m in c.record["messages"] if m["status"] != "failed"]
    return bool(sent) == bool(v), f"{len(sent)} text(s) sent"


def claim_filed(v, c: Ctx):
    n = len(c.committed(CLAIM_TOOLS))
    return (n > 0) == bool(v), f"{n} claim(s) filed"


def said(v, c: Ctx):
    lines = [f'{t["text"]} {t.get("speech", "")}' for t in c.agent()]
    missing = [p for p in v if not any(re.search(p, ln, re.I) for ln in lines)]
    return not missing, ("every pattern said" if not missing else f"never said: {missing}")


def never_said(v, c: Ctx):
    lines = [f'{t["text"]} {t.get("speech", "")}' for t in c.agent()]
    hit = [p for p in v if any(re.search(p, ln, re.I) for ln in lines)]
    return not hit, ("none said" if not hit else f"said: {hit}")


def turns_max(v, c: Ctx):
    n = len(c.caller())
    return n <= v, f"{n} caller turns"


def same_turn_max(v, c: Ctx):
    """The longest run of agent turns that said exactly the same thing: a loop the caller hears."""
    turns, cur = [], []
    for t in c.record["turns"]:
        if t["who"] == "caller":
            if cur:
                turns.append(tuple(cur))
            cur = []
        else:
            cur.append(t["text"])
    if cur:
        turns.append(tuple(cur))
    best = run = 0
    for i, t in enumerate(turns):
        run = run + 1 if i and t == turns[i - 1] else 1
        best = max(best, run)
    return best <= v, f"the same turn {best} time(s) in a row at most"


def cut_off(v, c: Ctx):
    """A cut-off is a caller's turn ended inside a pause the caller left in it (Chapter 11). It
    shows two ways: the agent begins to speak inside the pause, or the system's records hold one
    spoken turn as two, because it took the pause for the end."""
    if c.runner != "audio":
        return None, "measured only in audio"
    over = c.measures.get("cut_offs", 0)
    split = max(0, len(c.caller()) - c.spoken) if c.spoken else 0
    n = over + split
    return (n == 0) == (not v), (f"{n} cut-off(s): {split} turn(s) recorded as more than one, "
                                 f"{over} spoken over a pause")


def _audio(key: str):
    def check(v, c: Ctx):
        if c.runner != "audio" or key not in c.measures:
            return None, "measured only by the audio runner"
        m = c.measures[key]
        if key == "cut_offs":
            return (m == 0) == (not v), f"{m} cut-off(s)"
        if m is None:
            return False, "nothing to measure"
        return m <= v, f"{key} {round(m)}"
    return check


CHECKS = {
    # the task family: was the work done, and done honestly
    "booked": ("task", booked),
    "bookings": ("task", bookings),
    "no_booking": ("task", no_booking),
    "fee_before_yes": ("task", fee_before_yes),
    "confirmed_after_commit": ("task", confirmed_after_commit),
    "safety_script": ("task", safety_script),
    "transferred": ("task", transferred),
    "texted": ("task", texted),
    "claim_filed": ("task", claim_filed),
    "said": ("task", said),
    "never_said": ("task", never_said),
    # the experience family: how the call went for the caller
    "turns_max": ("experience", turns_max),
    "same_turn_max": ("experience", same_turn_max),
    "cut_off": ("experience", cut_off),
    "gap_p95_ms_max": ("experience", _audio("gap_p95_ms")),
    "talk_over_max": ("experience", _audio("talk_over")),
}


AUDIO_ONLY = {"cut_off", "gap_p95_ms_max", "talk_over_max"}


def run_checks(expect: dict, c: Ctx) -> list[dict]:
    out = []
    for key, value in expect.items():
        if key in AUDIO_ONLY and c.runner != "audio":
            out.append({"key": key, "family": CHECKS[key][0], "passed": None, "applies": False,
                        "detail": "measured only in audio"})
            continue
        if key not in CHECKS:
            out.append({"key": key, "family": "unknown", "passed": None,
                        "detail": "no check for this key in this suite"})
            continue
        family, fn = CHECKS[key]
        passed, detail = fn(value, c)
        out.append({"key": key, "family": family, "passed": passed, "detail": detail})
    return out


def family_verdict(results: list[dict], family: str) -> bool | None:
    """True when every check in the family passed; False when any failed; None when the family has
    no checks, or any check was not made."""
    mine = [r for r in results if r["family"] == family and r.get("applies", True)]
    if not mine:
        return None
    if any(r["passed"] is False for r in mine):
        return False
    if any(r["passed"] is None for r in mine):
        return None
    return True
