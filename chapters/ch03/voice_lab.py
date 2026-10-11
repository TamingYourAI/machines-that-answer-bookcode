"""Builders' Chapter 3 lab: the voice brief as data, lines for the ear, and a listening test.

Four steps:

  1. the brief          the Service Line's voice brief, loaded and checked for completeness
  2. the ear check      a line written for the eye fails; the same facts written for the ear pass
  3. saying things      numbers, money, times, dates, addresses, and codes, as the agent says them
  4. listening test     a small panel scores two candidate voices on the brief's nine test lines,
                        heard at phone bandwidth, against written pass criteria

Modes (select with VOICE_LAB_MODE or run(mode=...)):
  mock     the brief and the panel's scores are built in this file (default; runs anywhere)
  fixture  both are loaded from fixtures/brief.json and fixtures/panel.json (committed)
  live     not in this lab. Render the nine test lines with your candidate voices at 8 kHz,
           collect your own panel's scores in the fixture's schema, and load them.

Other entry points:
  python3 voice_lab.py                  run in the selected mode and print the report
  python3 voice_lab.py --write-fixture  regenerate the fixtures from the data here
  python3 voice_lab.py --check          compare with the frozen output in outputs/

Evidence class: simulated. The panel's scores are stand-in values, generated from a seed to show
the method and the arithmetic. They say nothing about any real voice or product.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ---------------------------------------------------------------- 1. the brief

def service_line_brief() -> dict:
    """The Service Line's voice brief, as data that the prompt, the synthesizer settings,
    and the test suite all read."""
    return {
        "version": "1.3",
        "owner": "head of customer operations",
        "approved_by": "brand lead",
        "speaker": "the utility's automated assistant",
        "attributes": {"warmth": "warm, not chatty", "pace_wpm": 150,
                       "max_spoken_words": 20, "formality": "plain and polite"},
        "registers": ["routine", "bad news", "anger", "emergency"],
        "languages": ["first language", "second language"],
        "disclosure": {
            "opening": "This is the utility's automated assistant. How can I help?",
            "are_you_a_person": "No, I'm an automated assistant. I can pass you to a person.",
        },
        "never_say": ["as an AI", "I understand your frustration", "per policy",
                      "unfortunately, I am unable"],
        "lexicon": {"Alder": "AL-der", "Kestrel Way": "KES-trel way",
                    "Ashby": "ASH-bee"},
        "test_lines": [
            "This is the utility's automated assistant. How can I help?",
            "That's account four four, one seven. Is that right?",
            "Your balance is one hundred twenty-four dollars and fifty cents.",
            "The first opening is Tuesday at nine in the morning.",
            "Is the visit at fourteen Alder Road?",
            "I'm sorry, the earliest visit is Thursday.",
            "Your reference is K for kilo, seven, B for bravo.",
            "I'll pass you to a colleague now, with everything you've told me.",
            "If you smell gas, leave the house now and call the gas emergency line "
            "from outside.",
        ],
        "number_lines": [2, 3, 4, 5, 7],
    }


REQUIRED = ("version", "owner", "approved_by", "speaker", "attributes", "registers",
            "languages", "disclosure", "never_say", "lexicon", "test_lines")


def check_brief(b: dict) -> list[str]:
    problems = [f"missing: {k}" for k in REQUIRED if k not in b]
    if problems:
        return problems
    if "automated" not in sentences(b["disclosure"]["opening"])[0]:
        problems.append("the first sentence does not say it is automated")
    if len(b["test_lines"]) != 9:
        problems.append(f"{len(b['test_lines'])} test lines, not nine")
    for line in b["test_lines"]:
        for phrase in b["never_say"]:
            if phrase.lower() in line.lower():
                problems.append(f"a test line uses a never-say phrase: {phrase!r}")
    return problems


# ---------------------------------------------------------------- 2. the ear check

ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "max.", "approx.", "acct", "no.")
SYMBOLS = "/%&#()"


def sentences(text: str) -> list[str]:
    safe = text
    for a in ABBREVIATIONS:                        # "max." does not end a sentence
        safe = re.sub(re.escape(a), a.replace(".", "\u2024"), safe, flags=re.I)
    parts = re.split(r"(?<=[.?!])\s+", safe.strip())
    return [s.replace("\u2024", ".") for s in parts if s]


def ear_check(text: str, max_words: int = 20) -> list[str]:
    """What a listener cannot do: scroll back, see brackets, or hold four numbers."""
    problems = []
    for s in sentences(text):
        words = len(s.split())
        if words > max_words:
            problems.append(f"{words} words in one sentence (limit {max_words})")
        numbers = re.findall(r"\d+", s)
        if len(numbers) > 1:
            problems.append(f"{len(numbers)} numbers in one sentence")
        if "(" in s:
            problems.append("brackets: the ear cannot hear them")
        for a in ABBREVIATIONS:
            if re.search(r"(^|[\s(])" + re.escape(a), s.lower()):
                problems.append(f"abbreviation: {a!r}")
                break
        if s.count(",") >= 3:
            problems.append("a list of four or more in one sentence")
    return problems


MEMO = ("Per Policy Memo 114, customers in the designated storm area who incurred late "
        "payment charges on statements issued between 1 and 30 September are eligible "
        "for a one-time waiver (max. $12) of late fees, subject to account verification.")
FOR_THE_EAR = ("Yes: if your bill was due during the storm, we can remove the "
               "twelve-dollar late fee once. Shall I check your account?")


# ---------------------------------------------------------------- 3. saying things

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
ORDINALS = {1: "first", 2: "second", 3: "third", 5: "fifth", 8: "eighth", 9: "ninth",
            12: "twelfth"}
SPELLING = {"A": "alfa", "B": "bravo", "C": "charlie", "D": "delta", "E": "echo",
            "F": "foxtrot", "K": "kilo", "M": "mike", "N": "november", "P": "papa",
            "S": "sierra", "T": "tango", "V": "victor"}
STREETS = {"Rd": "Road", "St": "Street", "Ave": "Avenue"}


def words(n: int) -> str:
    """0 to 9,999 in words, the way a person says a quantity."""
    if n < 10:
        return ONES[n]
    if n < 20:
        return TEENS[n - 10]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " " + words(rest))
    rest = n % 1000
    return words(n // 1000) + " thousand" + ("" if rest == 0 else " " + words(rest))


def say_digits(s: str) -> str:
    """Read an identifier digit by digit, in groups the ear can hold."""
    d = [ONES[int(c)] for c in s if c.isdigit()]
    size = 2 if len(d) == 4 else 3
    groups = [d[i:i + size] for i in range(0, len(d), size)]
    if len(groups) > 1 and len(groups[-1]) == 1:   # never strand one digit
        groups[-2:] = [groups[-2] + groups[-1]]
    return ", ".join(" ".join(g) for g in groups)


def say_money(amount: str) -> str:
    dollars, _, cents = amount.partition(".")
    out = words(int(dollars)) + (" dollar" if dollars == "1" else " dollars")
    if cents and int(cents):
        out += " and " + words(int(cents)) + " cents"
    return out


def say_time(hhmm: str) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    part = "in the morning" if h < 12 else "in the afternoon" if h < 17 else "in the evening"
    hour = words(h % 12 or 12)
    return f"{hour} {part}" if m == 0 else f"{hour} {words(m)} {part}"


def ordinal(n: int) -> str:
    if n in ORDINALS:
        return ORDINALS[n]
    if n < 20:
        return words(n) + "th"
    tens, ones = divmod(n, 10)
    if ones == 0:
        return TENS[tens][:-1] + "ieth"
    return TENS[tens] + "-" + ordinal(ones)


def say_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d:%A} the {ordinal(d.day)} of {d:%B}"


def say_address(addr: str) -> str:
    number, _, street = addr.partition(" ")
    parts = [STREETS.get(p, p) for p in street.split()]
    n = int(number)
    spoken = words(n) if n < 1000 else f"{words(n // 100)} {words(n % 100)}"
    return f"{spoken} {' '.join(parts)}"


def say_code(code: str) -> str:
    out = []
    for c in code:
        out.append(ONES[int(c)] if c.isdigit() else f"{c} for {SPELLING[c]}")
    return ", ".join(out)


SAY = {"digits": say_digits, "money": say_money, "time": say_time, "date": say_date,
       "address": say_address, "code": say_code}
EXAMPLES = [("digits", "4417"), ("digits", "2125550142"), ("money", "12"),
            ("money", "124.50"), ("time", "09:00"), ("time", "20:10"),
            ("date", "2026-09-29"), ("address", "14 Alder Rd"),
            ("address", "1260 Kestrel Way"), ("code", "K7B")]


# ---------------------------------------------------------------- 4. the listening test

VOICES = {"A": {"label": "voice A, the most natural in the studio",
                "natural": 4.4, "fits": 4.1, "digits_ok": 0.80},
          "B": {"label": "voice B, clear and a little slower",
                "natural": 3.9, "fits": 4.2, "digits_ok": 0.97}}
PANEL = 6
CRITERIA = {"digits_ok": 0.95, "fits": 4.0, "worst_line": 3.5}


def make_panel(brief: dict, seed: int = 12) -> dict:
    """Stand-in panel scores: each listener rates each line 1 to 5 for fit to the brief,
    and writes down every number line as heard; heard correctly or not is recorded."""
    rng = random.Random(seed)
    panel = {}
    for v, spec in VOICES.items():
        rows = []
        for i in range(1, 10):
            for listener in range(1, PANEL + 1):
                fits = min(5, max(1, round(rng.gauss(spec["fits"], 0.5))))
                natural = min(5, max(1, round(rng.gauss(spec["natural"], 0.5))))
                heard = None
                if i in brief["number_lines"]:
                    heard = rng.random() < spec["digits_ok"]
                rows.append({"line": i, "listener": listener, "fits": fits,
                             "natural": natural, "heard_ok": heard})
        panel[v] = rows
    return panel


def score(rows: list[dict]) -> dict:
    heard = [r["heard_ok"] for r in rows if r["heard_ok"] is not None]
    by_line: dict[int, list[int]] = {}
    for r in rows:
        by_line.setdefault(r["line"], []).append(r["fits"])
    line_means = {k: sum(v) / len(v) for k, v in by_line.items()}
    return {"digits_ok": sum(heard) / len(heard), "n_digits": len(heard),
            "fits": sum(r["fits"] for r in rows) / len(rows),
            "natural": sum(r["natural"] for r in rows) / len(rows),
            "worst_line": min(line_means.items(), key=lambda kv: kv[1])}


def verdict(s: dict) -> list[str]:
    fails = []
    if s["digits_ok"] < CRITERIA["digits_ok"]:
        fails.append(f"numbers heard correctly {100 * s['digits_ok']:.0f} % "
                     f"(needs {100 * CRITERIA['digits_ok']:.0f} %)")
    if s["fits"] < CRITERIA["fits"]:
        fails.append(f"fits the brief {s['fits']:.2f} (needs {CRITERIA['fits']:.1f})")
    if s["worst_line"][1] < CRITERIA["worst_line"]:
        fails.append(f"line {s['worst_line'][0]} scored {s['worst_line'][1]:.2f}")
    return fails


# ---------------------------------------------------------------- report

def load(mode: str) -> tuple[dict, dict]:
    if mode == "mock":
        brief = service_line_brief()
        return brief, make_panel(brief)
    if mode == "fixture":
        return (json.loads((FIXTURES / "brief.json").read_text()),
                json.loads((FIXTURES / "panel.json").read_text()))
    raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")


def report(mode: str) -> str:
    brief, panel = load(mode)
    lines: list[str] = []
    say = lines.append
    say(f"voice lab, mode={mode}; evidence class: simulated (stand-in panel)")
    say("")
    say(f"1. the brief: version {brief['version']}, owner {brief['owner']}")
    problems = check_brief(brief)
    say(f"   {len(brief['test_lines'])} test lines, {len(brief['never_say'])} never-say "
        f"phrases, {len(brief['lexicon'])} lexicon entries")
    say(f"   completeness check: {len(problems)} problems")
    for p in problems:
        say(f"     - {p}")
    say("")
    limit = brief["attributes"]["max_spoken_words"]
    say(f"2. the ear check (at most {limit} words and one number a sentence)")
    for name, text in (("the memo, as written", MEMO), ("the same facts, for the ear",
                                                        FOR_THE_EAR)):
        found = ear_check(text, limit)
        say(f"   {name:<44}{len(found)} problems")
        for p in found:
            say(f"     - {p}")
    say("")
    say("3. saying numbers, names, addresses, and codes")
    say(f"   {'kind':<10}{'written':<18}said")
    for kind, value in EXAMPLES:
        say(f"   {kind:<10}{value:<18}{SAY[kind](value)}")
    say("")
    say(f"4. the listening test: {PANEL} listeners, nine lines, phone bandwidth")
    say(f"   {'':<6}{'numbers heard':>15}{'fits brief':>12}{'natural':>9}  verdict")
    for v in sorted(panel):
        s = score(panel[v])
        fails = verdict(s)
        say(f"   {'voice ' + v:<6}{100 * s['digits_ok']:>9.0f} % of {s['n_digits']:<2}"
            f"{s['fits']:>10.2f}{s['natural']:>9.2f}  {'pass' if not fails else 'fail'}")
        for f in fails:
            say(f"     - {f}")
    say("   pass: numbers heard 95 %, fits 4.0, no line under 3.5; natural not scored")
    return "\n".join(lines) + "\n"


def run(mode: str | None = None) -> str:
    mode = mode or os.environ.get("VOICE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"voice_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        brief = service_line_brief()
        (FIXTURES / "brief.json").write_text(json.dumps(brief, indent=1))
        (FIXTURES / "panel.json").write_text(json.dumps(make_panel(brief), indent=0))
        print("wrote fixtures/brief.json and fixtures/panel.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("VOICE_LAB_MODE", "mock")))
    else:
        run()
