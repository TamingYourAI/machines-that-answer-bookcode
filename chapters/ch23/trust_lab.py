"""Builders' Chapter 23 lab: trust on the live call.

Four steps:

  1. where a card number lands   every place the call's audio and words
                                 go, for week 8, the launch fix, and the
                                 isolated path
  2. proving isolation           a marker tone after the pause: a fork
                                 that says "paused" and still receives
                                 bytes keeps the payment path shut, and
                                 the payment finishes another way
  3. redaction before write      card digits as a recognizer writes them,
                                 through a naive filter, a checksum
                                 filter, and a redactor that follows
                                 spans across a call's turns
  4. security signals            one evening's stand-in log: accounts
                                 probed from one number, failed checks on
                                 one account, and a flood of silent calls

Modes (select with TRUST_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point step 2 at your own forks' counters and a
           test card in your processor's sandbox (evidence class: live
           laboratory).

  python3 trust_lab.py                  run and print the report
  python3 trust_lab.py --write-fixture  regenerate fixtures/
  python3 trust_lab.py --check          compare with the frozen output

Evidence class: simulated. The forks, the processor, the utterances, and
the evening's log are stand-ins; the card is a public test number.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ---------------------------------------- 1. where a card number lands

FORKS = [  # every place the Service Line's call audio or its words go
    {"name": "recognizer", "carries": "audio", "live": True},
    {"name": "model", "carries": "words", "live": True},
    {"name": "transcript", "carries": "words", "live": True},
    {"name": "evaluation copy", "carries": "audio", "live": True},
    {"name": "recording", "carries": "audio", "live": True},
    {"name": "supervisor monitor", "carries": "audio", "live": False},
    {"name": "error payloads", "carries": "words", "live": False},
]


def lands(forks: list[dict], design: str) -> dict[str, str]:
    """Which places receive the card number, whole or in part.

    live False: nobody was listening, and nothing failed, on this call."""
    got = {}
    for f in forks:
        if not f["live"]:
            continue
        if design == "week 8":           # read aloud to the agent
            got[f["name"]] = "whole"
        elif design == "at launch":      # stopped after four digits
            if f["name"] != "transcript":    # redacted before the write
                got[f["name"]] = "part"
    if design == "at launch":
        got["a person on the payments line"] = "whole"
    if design == "isolated path":
        got["the payment processor"] = "whole"
    return got


# ------------------------------------------- 2. proving isolation

def prove_isolation(forks: list[dict]) -> tuple[bool, list[tuple]]:
    """Open the payment path only if no fork received audio while a
    marker tone played after the pause. A fork's "paused" is a claim;
    a byte count that did not move is the proof."""
    rows, ok = [], True
    for f in forks:
        moved = f["bytes_after"] - f["bytes_before"]
        if moved == 0:
            verdict = "stopped"
        elif f["says"] == "paused":
            verdict, ok = "said paused; still receiving", False
        else:
            verdict, ok = "did not pause", False
        rows.append((f["name"], f["says"], moved, verdict))
    return ok, rows


def take_payment(isolated: bool, keys: str, amount: str,
                 processor: dict) -> dict:
    """What the agent receives: a token and a status, never the digits.

    If isolation was not proven, the keys are never collected at all."""
    if not isolated:
        return {"status": "not taken", "offer": OFFER}
    return {"token": processor["token"], "status": processor["status"],
            "amount": amount, "card_ends": keys[12:16]}


OFFER = ("I can't take a card on this call right now. I can text you a "
         "secure link to pay, or the payments team can call you back "
         "within the hour.")


# -------------------------------------- 3. redaction before write

WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
WORDS["oh"] = "0"
TENS = {w: str(i) for i, w in zip(range(2, 10), (
    "twenty thirty forty fifty sixty seventy eighty ninety".split()))}
REPEAT = {"double": 2, "triple": 3}
CARD_WORDS = {"card", "visa", "mastercard", "amex", "debit", "credit"}


def naive(text: str) -> str:
    """The filter most teams start with: a run of 13 to 19 digits."""
    return re.sub(r"\b(?:\d[ -]?){12,18}\d\b", "[card]", text)


def spoken_digits(text: str) -> list[str]:
    """Rewrite number words as digits, keeping every other word. "Double
    one" is 11, the way callers read a card."""
    out, again = [], None
    for tok in re.findall(r"[a-z]+(?:-[a-z]+)?|\d+|[^\sa-z\d]", text.lower()):
        if tok in REPEAT and again is None:
            again = tok
            continue
        if "-" in tok and tok.split("-")[0] in TENS:
            tens, unit = tok.split("-", 1)
            word = TENS[tens] + WORDS.get(unit, "0")
        elif tok in TENS:
            word = TENS[tok] + "0"
        else:
            word = WORDS.get(tok, tok)
        if again:
            if word.isdigit():
                word *= REPEAT[again]
            else:
                out.append(again)
            again = None
        out.append(word)
    return out + ([again] if again else [])


def luhn(digits: str) -> bool:
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def mask(toks: list[str], is_card, context: bool = False) -> tuple:
    """Mask digit runs and security codes in a turn's tokens. is_card
    decides which runs are cards; a code is three or four digits after
    "code". Returns the masked text and whether anything was masked."""
    out, i, masked = [], 0, False
    while i < len(toks):
        j, run = i, ""
        while j < len(toks) and (toks[j].isdigit() or toks[j] in ",-"):
            run += toks[j] if toks[j].isdigit() else ""
            j += 1
        if run and is_card(run, context):
            out.append("[card]" if luhn(run) else "[digits]")
            i, masked = j, True
            continue
        if run:
            out += toks[i:j]
            i = j
            continue
        if toks[i] in ("code", "cvv", "cvc"):
            window = range(i + 1, min(i + 9, len(toks)))
            start = next((k for k in window if toks[k].isdigit()), None)
            k, code = start, ""
            while k is not None and k < len(toks) and toks[k].isdigit():
                code += toks[k]
                k += 1
            if start is not None and len(code) in (3, 4):
                out += toks[i:start] + ["[code]"]
                i, masked = k, True
                continue
        out.append(toks[i])
        i += 1
    return " ".join(out), masked


def checksum(text: str) -> str:
    """The second filter: number words become digits, and a run of 13 to
    19 digits is masked only if it passes the Luhn check."""
    return mask(spoken_digits(text),
                lambda run, _: 13 <= len(run) <= 19 and luhn(run))[0]


class Redactor:
    """Masks card and code digits in one call, turn by turn, before
    anything is written. It errs toward masking.

    A run of 13 to 19 digits is a card whatever its checksum, because one
    misheard digit fails the Luhn check and is still a card number. While
    the call is about a card (the word was said this turn, or a run was
    masked in one of the last two), a run of four digits or more is
    masked too, so a number read in pieces is masked piece by piece. The
    Luhn check only labels what was masked."""

    def __init__(self) -> None:
        self.context = 0      # turns left in which the call is about a card

    def turn(self, text: str) -> str:
        toks = spoken_digits(text)
        if CARD_WORDS & set(toks):
            self.context = 2
        out, masked = mask(toks, lambda run, ctx: 13 <= len(run) <= 19
                           or (ctx and len(run) >= 4), self.context > 0)
        self.context = 2 if masked else max(self.context - 1, 0)
        return out


def left(text: str) -> int:
    """Digits left in a turn, read the way a person reading the trace
    would read them, number words included."""
    return len(re.sub(r"\D", "", " ".join(spoken_digits(text))))


# ------------------------------------------- 4. security signals

LIMITS = {"accounts per number": (3, 10), "failures per account": (3, 30),
          "silent calls a minute": 10}


def evening(seed: int = 23) -> dict:
    """A stand-in evening: ordinary checks, plus three attacks."""
    rng = random.Random(seed)
    checks = []
    for n in range(180):                      # ordinary callers
        t = 18 * 60 + rng.randrange(0, 270)   # 18:00 to 22:30
        ok = rng.random() > 0.07              # a mistyped PIN, now and then
        checks.append([t, f"555 {1000 + n:04d}", f"{5000 + n}", ok])
    for i, acct in enumerate(range(3001, 3007)):   # one number, six accounts
        checks.append([21 * 60 + 2 + i, "555 0188", str(acct), False])
    for i, num in enumerate(("555 0107", "555 0122", "555 0140",
                             "555 0161")):         # one account, four numbers
        checks.append([21 * 60 + 10 + 4 * i, num, "4012", False])
    silent = [22 * 60 + m for m in (0, 1, 1, 2, 3) for _ in range(9)]
    return {"checks": sorted(checks), "silent": silent}


def signals(log: dict) -> list[tuple]:
    """Each detector, what it saw, and when it first fired."""
    fired = []
    lim, win = LIMITS["accounts per number"]
    for t, num, _, _ in log["checks"]:
        seen = {a for u, n, a, _ in log["checks"]
                if n == num and t - win < u <= t}
        if len(seen) > lim:
            fired.append(("accounts tried from one number",
                          f"{lim} in {win} min",
                          f"{num}: {len(seen)} accounts", t))
            break
    lim, win = LIMITS["failures per account"]
    for t, _, acct, ok in log["checks"]:
        failed = [n for u, n, a, k in log["checks"]
                  if a == acct and not k and t - win < u <= t]
        if not ok and len(failed) > lim:
            fired.append(("failed checks on one account",
                          f"{lim} in {win} min",
                          f"{acct}: {len(set(failed))} numbers", t))
            break
    per_min: dict[int, int] = {}
    for t in log["silent"]:
        per_min[t] = per_min.get(t, 0) + 1
    over = [t for t in sorted(per_min)
            if per_min[t] > LIMITS["silent calls a minute"]]
    if over:
        fired.append(("silent calls a minute",
                      str(LIMITS["silent calls a minute"]),
                      str(per_min[over[0]]), over[0]))
    return fired


RESPONSE = {
    "accounts tried from one number": "no more checks by voice from that "
    "number today; its attempts go to the fraud review",
    "failed checks on one account": "voice checks locked on the account; "
    "the next change needs the app, and the holder is told by text",
    "silent calls a minute": "spike mode, and the carrier asked to filter; "
    "callers already talking are not touched",
}


# -------------------------------------------------------------- inputs

CARD = "4111111111111111"   # a public test number, never a real card
CODE = "123"

UTTERANCES = [  # call, turn as the recognizer wrote it, what it holds
    [1, "my card is 4111 1111 1111 1111", "card"],
    [2, "4 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1", "card"],
    [3, "four one one one one one one one one one one one one one one one",
     "card"],
    [4, "forty-one eleven, eleven eleven, eleven eleven, eleven eleven",
     "card"],
    [5, "four double one double one double one double one double one "
        "double one double one one", "card"],
    [6, "my card is 4111 1111 1111 1112", "misheard"],
    [7, "my card is 4111 1111", "first half"],
    [7, "1111 1111", "second half"],
    [8, "the code on the back is one two three", "code"],
    [9, "my account is 2231 and my number is 555 0131", "neither"],
    [10, "my order number is 4111111111111111", "neither"],
]

RUNS = {
    "A": [{"name": f["name"], "says": "paused", "bytes_before": 96000,
           "bytes_after": 96000} for f in FORKS if f["live"]],
    "B": [{"name": f["name"], "says": "paused", "bytes_before": 96000,
           "bytes_after": 100000 if f["name"] == "recording" else 96000}
          for f in FORKS if f["live"]],
}

PROCESSOR = {"token": "tok-5108-8841", "status": "approved"}
LINK = {"sent": "20:15", "paid": "20:19", "token": "tok-5108-8907",
        "status": "approved"}


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"forks": FORKS, "runs": RUNS, "card": CARD, "code": CODE,
                "amount": "184.20", "processor": PROCESSOR, "link": LINK,
                "utterances": UTTERANCES, "evening": evening()}
    if mode == "fixture":
        return json.loads((FIXTURES / "trust.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    """Print text after a lead, wrapped at the page width and aligned."""
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"trust lab, mode={mode}; evidence class: simulated")
    put("")
    put("1. where a card number lands (a public test card)")
    put(f"   {'design':<35}{'the whole number':<30}part of it")
    for design, label in (("week 8", "week 8: read aloud to the agent"),
                          ("at launch", "at launch: stopped, then a person"),
                          ("isolated path", "the isolated path: keyed")):
        got = lands(data["forks"], design)
        whole = [k for k, v in got.items() if v == "whole"]
        part = [k for k, v in got.items() if v == "part"]
        w = whole[0] if len(whole) == 1 else f"{len(whole)} places"
        put(f"   {label:<35}{w:<30}"
            f"{str(len(part)) + ' places' if part else 'none'}")
    wk8 = [k for k, v in lands(data["forks"], "week 8").items()]
    block(put, "   week 8 reached: ", ", ".join(wk8))
    put("")
    put("2. proving isolation: a 500 ms marker tone after the pause")
    for run, label in (("A", "every fork stops"),
                       ("B", "the recording says paused and keeps going")):
        ok, rows = prove_isolation(data["runs"][run])
        put(f"   run {run}, {label}")
        for name, says, moved, verdict in rows:
            put(f"     {name:<17}{says:<8}{moved:>6,} bytes   {verdict}")
        res = take_payment(ok, data["card"], data["amount"],
                           data["processor"])
        if ok:
            block(put, "     then: ", "the path opens; the caller keys 16 "
                  "digits, the expiry, and the code; the processor alone "
                  "receives them")
            block(put, "     the agent receives: ",
                  f"token {res['token']}, {res['status']}, "
                  f"${res['amount']}, card ending {res['card_ends']}")
        else:
            block(put, "     then: ", "the path stays shut, and the agent "
                  f"says: \"{res['offer']}\"")
            ln = data["link"]
            block(put, "     the payment: ", f"link texted at {ln['sent']}; "
                  f"paid through it at {ln['paid']}: token {ln['token']}, "
                  f"{ln['status']}; the case closes paid")
            block(put, "     and: ", "an incident for the compliance lead; "
                  "card payments on calls stay off until the recording "
                  "passes the marker test again")
    put("")
    put("3. redaction before the transcript is written")
    put(f"   {'what the recognizer wrote':<40}{'holds':<12}"
        f"{'digits left':>21}")
    put(f"   {'':<52}{'naive':>7}{'luhn':>7}{'spans':>7}")
    totals, kept, call, red = [0, 0, 0], [], None, None
    for c, u, holds in data["utterances"]:
        if c != call:
            call, red = c, Redactor()
        outs = (naive(u), checksum(u), red.turn(u))
        shown = u if len(u) <= 38 else u[:35] + "..."
        if holds == "neither":
            kept.append((shown, ["masked" if "[" in o else "kept"
                                 for o in outs]))
            continue
        n = [left(o) for o in outs]
        totals = [a + b for a, b in zip(totals, n)]
        put(f"   {shown:<40}{holds:<12}{n[0]:>7}{n[1]:>7}{n[2]:>7}")
    put(f"   {'digits of a card or code left in the trace':<52}"
        f"{totals[0]:>7}{totals[1]:>7}{totals[2]:>7}")
    for shown, v in kept:
        put(f"   {shown:<40}{'neither':<12}{v[0]:>7}{v[1]:>7}{v[2]:>7}")
    put("")
    ev = data["evening"]
    put(f"4. security signals from one evening ({len(ev['checks'])} "
        f"checks, {len(ev['silent'])} silent calls; stand-ins)")
    put(f"   {'signal':<31}{'limit':<13}{'seen':<22}first")
    for name, limit, seen, t in signals(ev):
        put(f"   {name:<31}{limit:<13}{seen:<22}{clock(t)}")
        block(put, "     response: ", RESPONSE[name])
    quiet = sum(1 for _, n, _, ok in ev["checks"]
                if not ok and n not in ("555 0188", "555 0107", "555 0122",
                                        "555 0140", "555 0161"))
    block(put, "   ", f"{quiet} ordinary failed checks, one per caller, "
          "stayed below every limit")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("TRUST_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"trust_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "trust.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/trust.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("TRUST_LAB_MODE", "mock")))
    else:
        run_mode()
