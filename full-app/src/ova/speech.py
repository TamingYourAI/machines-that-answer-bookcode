"""Text for the ear: what the agent shows and what it says.

Every line the agent produces has two forms. The display form is what a screen shows ("Your
claim number is CL-204905."). The spoken form is what a voice says ("Your claim number is
C L, two zero four, nine zero five."). Numbers, money, dates, times, and codes are turned into
words here, by our code, not by the voice provider (builders' Chapter 3).

A Line also records where each material term sits in the spoken form. When a caller interrupts,
the transport reports how much of the line was played, and the terms before that point count
as heard. A confirmation covers only heard terms (builders' Chapter 17).

The say_* functions are the ones in the book's Chapter 3 lab.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
ORDINALS = {1: "first", 2: "second", 3: "third", 5: "fifth", 8: "eighth", 9: "ninth",
            12: "twelfth"}
STREETS = {"Rd": "Road", "St": "Street", "Ave": "Avenue", "Dr": "Drive", "Ln": "Lane",
           "Blvd": "Boulevard", "Ct": "Court", "Hwy": "Highway"}
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "max.", "approx.", "no.")


def words(n: int) -> str:
    """0 to 999,999 in words, the way a person says a quantity."""
    if n < 0:
        return "minus " + words(-n)
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


def say_code(code: str) -> str:
    """Letters one by one, then the digits in groups: "QM-481273" -> "Q M, four eight one, ..."."""
    letters = " ".join(c for c in code if c.isalpha())
    digits = say_digits(code)
    return ", ".join(p for p in (letters, digits) if p)


def say_money(amount: float | int | str) -> str:
    value = f"{float(amount):.2f}"
    dollars, _, cents = value.partition(".")
    out = words(int(dollars)) + (" dollar" if dollars == "1" else " dollars")
    if int(cents):
        out += " and " + words(int(cents)) + " cents"
    return out


def say_time(hhmm: str) -> str:
    h, m = (int(x) for x in hhmm.split(":")[:2])
    if (h, m) == (12, 0):
        return "noon"
    part = "in the morning" if h < 12 else "in the afternoon" if h < 17 else "in the evening"
    hour = words(h % 12 or 12)
    if m == 0:
        return f"{hour} {part}"
    minutes = f"oh {ONES[m]}" if m < 10 else words(m)
    return f"{hour} {minutes} {part}"


def show_time(hhmm: str) -> str:
    """The display form of a time: "5 pm", "9:30 am"."""
    h, m = (int(x) for x in hhmm.split(":")[:2])
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12} {suffix}" if m == 0 else f"{h12}:{m:02d} {suffix}"


def on_date(d: dt.date | str, today: dt.date | None = None) -> tuple[str, str]:
    """(shown, spoken) with "on" where English needs it: "yesterday", "on Tuesday the..."."""
    if isinstance(d, str):
        d = dt.date.fromisoformat(d)
    spoken = say_date(d, today)
    if spoken in ("today", "yesterday", "tomorrow"):
        return spoken, spoken
    return "on " + show_date(d), "on " + spoken


def ordinal(n: int) -> str:
    if n in ORDINALS:
        return ORDINALS[n]
    if n < 20:
        return words(n) + "th"
    tens, ones = divmod(n, 10)
    if ones == 0:
        return TENS[tens][:-1] + "ieth"
    return TENS[tens] + "-" + ordinal(ones)


def say_date(d: dt.date | str, today: dt.date | None = None) -> str:
    """"Tuesday the twenty-second of September"; "today" and "yesterday" when they are."""
    if isinstance(d, str):
        d = dt.date.fromisoformat(d)
    if today is not None:
        if d == today:
            return "today"
        if d == today - dt.timedelta(days=1):
            return "yesterday"
        if d == today + dt.timedelta(days=1):
            return "tomorrow"
    return f"{d:%A} the {ordinal(d.day)} of {d:%B}"


def show_date(d: dt.date | str, today: dt.date | None = None) -> str:
    """The display form of a date: "Tue 22 Sep"."""
    if isinstance(d, str):
        d = dt.date.fromisoformat(d)
    if today is not None and d == today:
        return f"today ({d:%a} {d.day} {d:%b})"
    return f"{d:%a} {d.day} {d:%b}"


def say_year(y: int) -> str:
    if 2000 <= y < 2010:
        return "two thousand" + ("" if y == 2000 else " " + ONES[y - 2000])
    hi, lo = divmod(y, 100)
    return words(hi) + " " + ("hundred" if lo == 0 else f"oh {ONES[lo]}" if lo < 10
                              else words(lo))


def say_birthdate(d: dt.date) -> str:
    return f"the {ordinal(d.day)} of {d:%B}, {say_year(d.year)}"


def say_address(addr: str) -> str:
    number, _, street = addr.partition(" ")
    if not number.isdigit():
        return " ".join(STREETS.get(p, p) for p in addr.split())
    parts = [STREETS.get(p.rstrip(","), p) for p in street.split()]
    n = int(number)
    spoken = words(n) if n < 1000 else f"{words(n // 100)} {words(n % 100)}"
    return f"{spoken} {' '.join(parts)}"


def say_phone_tail(phone: str) -> str:
    """The last four digits, the only part of a phone number the agent reads aloud."""
    d = re.sub(r"\D", "", phone)
    return say_digits(d[-4:])


def sentences(text: str) -> list[str]:
    safe = text
    for a in ABBREVIATIONS:                        # "max." does not end a sentence
        safe = re.sub(re.escape(a), a.replace(".", "․"), safe, flags=re.I)
    parts = re.split(r"(?<=[.?!])\s+", safe.strip())
    return [s.replace("․", ".") for s in parts if s]


_MONEY = re.compile(r"\$(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d{2}))?")
_PCT = re.compile(r"(\d+)\s?%")
_AMPM = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s?(a\.?m\.?|p\.?m\.?)", re.I)


def speakable(text: str) -> str:
    """A light pass over free text (a retrieved sentence, a model's answer) before a voice
    reads it: money, percentages, clock times, and street abbreviations."""
    def money(m: re.Match) -> str:
        return say_money(m.group(1).replace(",", "") + "." + (m.group(2) or "00"))

    def clock(m: re.Match) -> str:
        h, mins = int(m.group(1)), int(m.group(2) or 0)
        pm = m.group(3).lower().startswith("p")
        h24 = (h % 12) + (12 if pm else 0)
        stop = "." if m.group(3).endswith(".") and "." not in m.group(3)[:-1] else ""
        return say_time(f"{h24}:{mins:02d}") + stop

    out = _MONEY.sub(money, text)
    out = _PCT.sub(lambda m: f"{words(int(m.group(1)))} percent", out)
    out = _AMPM.sub(clock, out)
    out = re.sub(r"\b(\d+) (Rd|St|Ave|Dr|Ln|Blvd)\b",
                 lambda m: f"{m.group(1)} {STREETS[m.group(2)]}", out)
    return out


# ---------------------------------------------------------------- lines and terms

@dataclass(frozen=True)
class Term:
    """A material term inside a line: what the screen shows and what the voice says."""
    name: str
    shown: str
    spoken: str
    value: str = ""                                 # the canonical value, for binding


@dataclass
class Line:
    """One thing the agent says, in both forms, with the terms it carries."""
    text: str
    speech: str
    terms: dict[str, Term] = field(default_factory=dict)
    spans: dict[str, tuple[int, int]] = field(default_factory=dict)   # in speech
    register: str = "routine"
    backed_by: str | None = None                    # the committed operation it reports

    @classmethod
    def of(cls, *parts: str | Term, register: str = "routine",
           backed_by: str | None = None) -> "Line":
        text, speech = [], []
        terms, spans = {}, {}
        pos = 0
        for p in parts:
            if isinstance(p, Term):
                text.append(p.shown)
                start = pos
                speech.append(p.spoken)
                pos += len(p.spoken)
                terms[p.name] = p
                spans[p.name] = (start, pos)
            else:
                text.append(p)
                spoken = speakable(p)
                speech.append(spoken)
                pos += len(spoken)
        return cls("".join(text), "".join(speech), terms, spans, register, backed_by)

    @classmethod
    def plain(cls, text: str, register: str = "routine") -> "Line":
        return cls.of(text, register=register)

    def heard_terms(self, heard_chars: int | None) -> set[str]:
        """The terms fully played before the line was cut; all of them if it was not cut."""
        if heard_chars is None:
            return set(self.terms)
        return {n for n, (_, end) in self.spans.items() if end <= heard_chars}

    def __add__(self, other: "Line") -> "Line":
        sep_t = "" if not self.text or self.text.endswith(" ") else " "
        offset = len(self.speech) + len(sep_t)
        spans = dict(self.spans)
        spans.update({n: (a + offset, b + offset) for n, (a, b) in other.spans.items()})
        return Line(self.text + sep_t + other.text, self.speech + sep_t + other.speech,
                    {**self.terms, **other.terms}, spans, other.register or self.register,
                    other.backed_by or self.backed_by)
