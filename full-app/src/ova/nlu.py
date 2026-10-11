"""Understanding by rules: the deterministic half of the hybrid.

Rules run first on every turn. They are cheap, fast, and testable, and they own the acts that
must never depend on a model: yes and no, asking for a person, digits, dates, and the words that
end a call. What the rules cannot place goes to the model, when one is configured
(`ova.brain`). Everything here works on recognizer text, so it expects lower case, no
punctuation, and numbers either as digits or as words.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------- the result

ACTS = ("value", "yes", "no", "person", "goodbye", "repeat", "help", "emergency",
        "silence", "unclear", "question", "dtmf", "skip")


@dataclass
class Understanding:
    act: str
    intent: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "rules"
    text: str = ""
    target: str | None = None                   # for "person": who they asked for


@dataclass
class SlotSpec:
    name: str
    kind: str                                   # see EXTRACTORS
    choices: dict[str, list[str]] | None = None
    id_prefix: str = ""
    id_digits: int = 0


@dataclass
class Frame:
    """What the agent is waiting for, so the rules know how to read a short answer."""
    expecting: SlotSpec | None = None
    yes_no: bool = False                        # a yes or no question is open
    other_slots: list[SlotSpec] = field(default_factory=list)
    intents: list[tuple[str, list[str]]] = field(default_factory=list)
    today: dt.date = field(default_factory=dt.date.today)


# ---------------------------------------------------------------- words to numbers

UNITS = {"zero": 0, "oh": 0, "o": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9}
TEEN = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90}
ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
                 "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
                 "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
                 "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
                 "twentieth": 20, "thirtieth": 30}
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
WEEKDAYS = {d: i for i, d in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}


def clean(text: str) -> str:
    t = text.lower().replace("’", "'")
    t = re.sub(r"[^\w\s'@./:-]", " ", t)
    t = re.sub(r"(?<=\D)[.](?=\s|$)", " ", t)      # sentence stops, not decimals or emails
    return re.sub(r"\s+", " ", t).strip()


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+", text.replace("-", " "))


def digit_string(text: str) -> str:
    """Spoken digits to a digit string: "four eight one, two seven three" -> "481273";
    "double seven" -> "77"; "forty eight twelve" -> "4812"; numerals pass through."""
    out: list[str] = []
    toks = tokens(clean(text))
    i, repeat = 0, 1
    while i < len(toks):
        t = toks[i]
        if t in ("double", "triple"):
            repeat = 2 if t == "double" else 3
            i += 1
            continue
        if t.isdigit():
            out.append(t * repeat if len(t) == 1 else t)
        elif t in UNITS and not (t == "o" and not out and i + 1 < len(toks)
                                 and toks[i + 1] not in UNITS):
            out.append(str(UNITS[t]) * repeat)
        elif t in TEEN:
            out.append(str(TEEN[t]))
        elif t in TENS:
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            if nxt in UNITS and UNITS[nxt] > 0 and nxt not in ("oh", "o"):
                out.append(str(TENS[t] + UNITS[nxt]))
                i += 1
            else:
                out.append(str(TENS[t]))
        elif t == "hundred" and out:
            out.append("00")
        repeat = 1
        i += 1
    return "".join(out)


def number_value(text: str) -> int | None:
    """A quantity in words or digits: "twenty-two" -> 22, "nineteen eighty five" -> 1985."""
    toks = tokens(clean(text))
    if not toks:
        return None
    if len(toks) == 1 and toks[0].isdigit():
        return int(toks[0])
    total, current, seen = 0, 0, False
    pairs: list[int] = []
    for t in toks:
        if t.isdigit():
            pairs.append(int(t))
            seen = True
            continue
        if t in UNITS and t not in ("o",):
            current += UNITS[t]
        elif t in TEEN:
            if current:
                pairs.append(current)
                current = 0
            current += TEEN[t]
        elif t in TENS:
            if current and current >= 10:
                pairs.append(current)
                current = 0
            current += TENS[t]
        elif t == "hundred":
            current = (current or 1) * 100
        elif t == "thousand":
            total += (current or 1) * 1000
            current = 0
        elif t == "and":
            continue
        else:
            continue
        seen = True
    if not seen:
        return None
    if pairs and not total:                      # "nineteen eighty five": two pairs
        pairs.append(current)
        if len(pairs) == 2 and pairs[0] >= 10 and pairs[1] < 100:
            return pairs[0] * 100 + pairs[1]
        return pairs[-1] if pairs[-1] else pairs[0]
    return total + current


def year_value(text: str) -> int | None:
    found = year_span(text)
    return found[0] if found else None


def year_span(text: str) -> tuple[int, int] | None:
    """(year, where it starts in the cleaned text): "1985", "nineteen eighty five",
    "two thousand one". The last plausible year wins: "twenty second nineteen seventy
    eight" is 1978, not a year starting at "twenty"."""
    t = clean(text)
    m = list(re.finditer(r"\b(19\d\d|20\d\d)\b", t))
    if m:
        return int(m[-1].group(1)), m[-1].start()
    for head in reversed(list(re.finditer(r"\b(nineteen|twenty|two thousand)\b", t))):
        rest = t[head.end():].strip()
        if head.group(1) == "two thousand":
            n = number_value(rest) if rest else 0
            if n is not None and n < 100:
                return 2000 + (n or 0), head.start()
            continue
        if not rest:
            continue
        lo = number_value(rest.replace("oh ", ""))
        if lo is None or lo >= 100 or not re.match(r"(oh |zero )?[a-z]+", rest):
            continue
        if rest.split()[0] in ORDINAL_WORDS or rest.split()[0].endswith(("th", "st", "nd",
                                                                          "rd")):
            continue
        return (19 if head.group(1) == "nineteen" else 20) * 100 + lo, head.start()
    return None


# ---------------------------------------------------------------- dates and times

def _day_number(t: str) -> int | None:
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m and 1 <= int(m.group(1)) <= 31:
        return int(m.group(1))
    for w, n in sorted(ORDINAL_WORDS.items(), key=lambda kv: -len(kv[0])):
        m = re.search(r"\b(twenty|thirty)[\s-]" + w + r"\b", t)
        if m:
            return {"twenty": 20, "thirty": 30}[m.group(1)] + n
    for w, n in ORDINAL_WORDS.items():
        if re.search(r"\b" + w + r"\b", t):
            return n
    return None


def parse_date(text: str, today: dt.date, direction: str = "past") -> dt.date | None:
    """A date the caller said, relative to today. direction="past" for a loss date,
    "future" for an appointment."""
    t = clean(text)
    if re.search(r"\b(today|this morning|this afternoon|this evening|tonight|just now|"
                 r"an hour ago|a few hours ago|earlier today)\b", t):
        return today
    if re.search(r"\b(yesterday|last night)\b", t):
        return today - dt.timedelta(days=1)
    if re.search(r"\btomorrow\b", t):
        return today + dt.timedelta(days=1)
    m = re.search(r"\b(\w+) days? ago\b", t)
    if m:
        n = number_value(m.group(1))
        if n is not None and n < 60:
            return today - dt.timedelta(days=n)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        y = y + 2000 if y < 100 else y
        try:
            return _nearest(dt.date(y, mo, d), today, direction, explicit_year=bool(m.group(3)))
        except ValueError:
            return None
    month = next((MONTHS[w] for w in re.findall(r"[a-z]+", t) if w in MONTHS), None)
    if month:
        day = _day_number(re.sub(r"\b(19|20)\d\d\b", "", t))
        if day:
            year = year_value(t)
            try:
                return _nearest(dt.date(year or today.year, month, day), today, direction,
                                explicit_year=bool(year))
            except ValueError:
                return None
    for name, wd in WEEKDAYS.items():
        if re.search(r"\b" + name + r"\b", t):
            if direction == "past":
                delta = (today.weekday() - wd) % 7
                if "last " + name in t and delta == 0:
                    delta = 7
                return today - dt.timedelta(days=delta)
            delta = (wd - today.weekday()) % 7 or 7
            if "next " + name in t and delta < 7:
                delta += 7 if (wd - today.weekday()) % 7 == 0 else 0
            return today + dt.timedelta(days=delta)
    m = re.search(r"\bthe (\w+(?:[\s-]\w+)?)\b", t)
    if m and re.search(r"(st|nd|rd|th)\b", m.group(1)):
        day = _day_number(m.group(1))
        if day:
            try:
                return _nearest(today.replace(day=day), today, direction)
            except ValueError:
                return None
    return None


def _nearest(d: dt.date, today: dt.date, direction: str, explicit_year: bool = False
             ) -> dt.date:
    if explicit_year:
        return d
    if direction == "past" and d > today:
        if d.month > today.month or (d.month == today.month and d.day > today.day):
            try:
                return d.replace(year=d.year - 1) if d.month > today.month else \
                    (d.replace(month=d.month - 1) if d.month > 1 else d.replace(
                        year=d.year - 1, month=12))
            except ValueError:
                return d
    if direction == "future" and d < today:
        try:
            return d.replace(year=d.year + 1)
        except ValueError:
            return d
    return d


def parse_birthdate(text: str) -> dt.date | None:
    t = clean(text)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", t)
    if m:
        mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + (1900 if y > 30 else 2000) if y < 100 else y
        try:
            return dt.date(y, mo, d)
        except ValueError:
            return None
    month = next((MONTHS[w] for w in re.findall(r"[a-z]+", t) if w in MONTHS), None)
    found = year_span(t)
    if not month or not found:
        return None
    year, at = found
    day = _day_number(t[:at])
    if not day:
        return None
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


PARTS_OF_DAY = {"morning": "09:00", "afternoon": "14:00", "evening": "19:00",
                "night": "22:00", "noon": "12:00", "midday": "12:00", "midnight": "00:00",
                "lunchtime": "12:30"}


def parse_time(text: str) -> tuple[str | None, str | None]:
    """(HH:MM, part of day). Either may be None: "this morning" -> (None, "morning")."""
    t = clean(text)
    part = next((p for p in ("morning", "afternoon", "evening", "night", "noon", "midnight",
                             "midday", "lunchtime") if re.search(r"\b" + p + r"\b", t)), None)
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?=\s|$)", t)
    hour = minute = None
    ampm = None
    if m and (m.group(2) or m.group(3) or re.search(r"\b(at|around|about)\s+" + m.group(1),
                                                    t)):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ampm = m.group(3)
    else:
        m = re.search(r"\b(?:at|around|about|by)\s+(\w+)(?:\s+(o'clock|thirty|fifteen|"
                      r"forty five))?\b", t)
        if m and (m.group(1) in UNITS or m.group(1) in TEEN):
            hour = UNITS.get(m.group(1), TEEN.get(m.group(1)))
            minute = {"thirty": 30, "fifteen": 15, "forty five": 45}.get(m.group(2) or "", 0)
        ampm_m = re.search(r"\b(a\.?m\.?|p\.?m\.?)\b", t)
        ampm = ampm_m.group(1) if ampm_m else None
    if re.search(r"\bhalf past (\w+)\b", t):
        h = re.search(r"\bhalf past (\w+)\b", t).group(1)
        hour, minute = UNITS.get(h, TEEN.get(h, int(h) if h.isdigit() else None)), 30
    if hour is None or hour > 23 or minute is None or minute > 59:
        return (PARTS_OF_DAY.get(part) if part in ("noon", "midnight", "midday") else None,
                part)
    if ampm and ampm.startswith("p") and hour < 12:
        hour += 12
    elif ampm and ampm.startswith("a") and hour == 12:
        hour = 0
    elif not ampm and part in ("afternoon", "evening", "night") and hour < 12:
        hour += 12
    elif not ampm and not part and 1 <= hour <= 6:
        hour += 12                               # "at three" means three in the afternoon
    return f"{hour:02d}:{minute:02d}", part


# ---------------------------------------------------------------- acts

YES = re.compile(r"^(?:(?:oh|um|uh|well|so)\s+)*(yes|yeah|yea|yep|yup|ya|correct|right|"
                 r"that's right|that is right|that's correct|sure|ok|okay|go ahead|please do|"
                 r"do it|absolutely|affirmative|sounds good|that works|perfect|exactly|"
                 r"yes please|uh huh|mm hmm|definitely|please|confirm|confirmed)\b")
NO = re.compile(r"^(?:(?:oh|um|uh|well|so)\s+)*(no|nope|nah|not right|wrong|incorrect|"
                r"that's wrong|that's not right|not quite|negative|don't|do not|not really|"
                r"no thanks|no thank you|not now|cancel)\b")
PERSON = re.compile(          # never a bare "a person": "a person hit my car" is a value
    r"\b(real person|live person|live agent|human being|a human|representative|operator|"
    r"customer service|(?:speak|talk) (?:to|with) (?:a|an|someone|somebody|my adjuster|"
    r"the adjuster|a human|a person|a real person|an agent)|(?:get|give) me (?:a|an) "
    r"(?:person|human|agent)|(?:want|need) (?:a|an) (?:person|human|agent)|transfer me|"
    r"put me through)\b")
ASK_HUMAN = re.compile(r"\b(?:are you|am i (?:talking|speaking) (?:to|with)|is this|is that) "
                       r"(?:a |an )?(?:real |actual |live )?(?:person|human|robot|machine|"
                       r"computer|bot|ai|recording)\b")
AGENT_ALONE = re.compile(r"^(?:(?:an?|the)\s+)?(agent|representative|operator|person)"
                         r"(?:\s+please)?$")
GOODBYE = re.compile(r"^(?:no\s+)?(?:thanks?|thank you)?\s*(?:,\s*)?(bye|goodbye|good bye|"
                     r"that's all|that is all|that's it|nothing else|i'm done|i am done|"
                     r"all done|that's everything)\b|\b(bye bye|goodbye|good bye|hang up)\b")
REPEAT = re.compile(r"^(?:sorry\s*)?(?:what|pardon|come again|say (?:that|it) again|"
                    r"repeat(?: that)?|can you repeat(?: that)?|could you repeat(?: that)?|"
                    r"what did you say|one more time)\??$")
HELP = re.compile(r"^(help|what can you do|what are my options|options|menu)\b")
SKIP = re.compile(r"\b(i don't know|i do not know|not sure|no idea|don't remember|"
                  r"can't remember|skip|rather not say|unknown)\b")
QUESTION = re.compile(r"^(what|what's|whats|how|when|where|why|which|who|does|do|is|are|"
                      r"can|could|will|would|should|am|if)\b")


# ---------------------------------------------------------------- slot extractors

def extract_digits(text: str, spec: SlotSpec) -> str | None:
    d = digit_string(text)
    if not d:
        return None
    if spec.id_digits:
        if len(d) != spec.id_digits:
            return None
        return f"{spec.id_prefix}-{d}" if spec.id_prefix else d
    return d


def extract_choice(text: str, spec: SlotSpec) -> str | None:
    t = " " + clean(text) + " "
    best: tuple[int, str] | None = None
    for canon, synonyms in (spec.choices or {}).items():
        for s in [canon.replace("_", " ")] + synonyms:
            m = re.search(r"\b" + re.escape(s) + r"\b", t)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), canon)
    return best[1] if best else None


PLACE = re.compile(
    r"\b(?:on|at|near|in|by|outside|off)\s+((?:the\s+)?(?:corner of\s+)?[\w' -]*?\b(?:"
    r"street|st|road|rd|avenue|ave|drive|dr|lane|ln|boulevard|blvd|highway|hwy|parkway|pkwy|"
    r"way|place|court|freeway|interstate|parking lot|parking garage|garage|driveway|"
    r"intersection|mall|lot|bridge|exit \d+|i \d+)\b(?:\s+and\s+[\w' -]+?\b(?:street|st|road|"
    r"rd|avenue|ave|drive|dr|lane|ln|way|boulevard|blvd)\b)?)")
FILLER = re.compile(r"^(?:um|uh|so|well|it was|it happened|it's|its|i was|we were|"
                    r"that was|this was|at|on|in|near)\s+")


def extract_place(text: str, spec: SlotSpec | None = None, strict: bool = False
                  ) -> str | None:
    """strict (a place the agent did not ask for): only a phrase that names a road or a
    place. Otherwise the caller's whole answer, without the filler, up to 80 characters."""
    t = clean(text)
    if strict:
        m = PLACE.search(t)
        return _tidy(m.group(1)) if m else None
    if YES.fullmatch(t) or NO.fullmatch(t) or extract_yes_no(t) is not None and \
            len(t.split()) <= 2:
        return None
    for _ in range(3):
        t = FILLER.sub("", t)
    return _tidy(t[:80]) if len(t) >= 3 else None


def _tidy(s: str) -> str:
    s = s.strip(" .,")
    return " ".join(w if w in ("and", "of", "the", "on", "at", "near") else w.capitalize()
                    for w in s.split())


def extract_text(text: str, spec: SlotSpec | None = None) -> str | None:
    """Free text: anything but a bare yes, no, or filler, without the punctuation and stray
    symbols a recognizer leaves at its edges ("Jordan. //" is Jordan)."""
    t = re.sub(r"^[\s.,;:!?/\\|_*~#^<>\-]+|[\s.,;:!?/\\|_*~#^<>\-]+$", "", text)
    c = clean(t)
    if len(c) < 2 or YES.fullmatch(c) or NO.fullmatch(c) or \
            c in ("um", "uh", "hmm", "okay", "ok", "so", "well"):
        return None
    return t


def extract_yes_no(text: str) -> bool | None:
    t = clean(text)
    if NO.search(t) or re.search(r"\b(no one|nobody|none|not at all|no injuries)\b", t):
        return False
    if YES.search(t):
        return True
    return None


def extract_phone(text: str, spec: SlotSpec | None = None) -> str | None:
    d = digit_string(text)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"+1{d}" if len(d) == 10 else None


def extract_email(text: str, spec: SlotSpec | None = None) -> str | None:
    t = clean(text).replace(" at ", "@").replace(" dot ", ".")
    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", t.replace(" ", ""))
    return m.group(0) if m else None


def _date(text, spec, today, direction):
    d = parse_date(text, today, direction)
    return d.isoformat() if d else None


EXTRACTORS = {
    "digits": lambda t, s, today: extract_digits(t, s),
    "id": lambda t, s, today: extract_digits(t, s),
    "choice": lambda t, s, today: extract_choice(t, s),
    "place": lambda t, s, today: extract_place(t, s),
    "text": lambda t, s, today: extract_text(t, s),
    "yesno": lambda t, s, today: extract_yes_no(t),
    "date_past": lambda t, s, today: _date(t, s, today, "past"),
    "date_future": lambda t, s, today: _date(t, s, today, "future"),
    "birthdate": lambda t, s, today: (lambda d: d.isoformat() if d else None)(
        parse_birthdate(t)),
    "time": lambda t, s, today: (lambda r: r[0] or r[1])(parse_time(t)),
    "phone": lambda t, s, today: extract_phone(t, s),
    "email": lambda t, s, today: extract_email(t, s),
}
# Extractors strong enough to fill a slot the agent did not ask about yet.
OPPORTUNISTIC = {"choice", "date_past", "date_future", "id"}


def understand(text: str, frame: Frame) -> Understanding:
    """The rules' reading of one caller turn."""
    raw = text
    t = clean(text)
    u = Understanding(act="unclear", text=raw, confidence=0.0)
    if not t:
        u.act = "silence"
        return u
    if ASK_HUMAN.search(t):
        u.act, u.intent, u.confidence = "question", "are_you_a_person", 0.95
        return u
    if PERSON.search(t) or AGENT_ALONE.match(t):
        u.act, u.confidence = "person", 0.95
        if re.search(r"\badjuster\b", t):
            u.target = "adjuster"
        return u
    if REPEAT.match(t):
        u.act, u.confidence = "repeat", 0.9
        return u
    if GOODBYE.search(t) and len(t.split()) <= 8:
        u.act, u.confidence = "goodbye", 0.9
        return u
    if HELP.match(t):
        u.act, u.confidence = "help", 0.8
        return u

    slots: dict[str, Any] = {}
    exp = frame.expecting
    if exp is not None:
        if SKIP.search(t) and exp.kind not in ("yesno",):
            u.act, u.confidence = "skip", 0.8
        else:
            v = EXTRACTORS[exp.kind](raw, exp, frame.today)
            if v is not None and exp.kind != "yesno":
                slots[exp.name] = v
            elif v is not None:
                slots[exp.name] = v
    for spec in frame.other_slots:
        if spec.name in slots or spec.kind not in OPPORTUNISTIC and spec.kind != "place":
            continue
        if spec.kind == "place":
            v = extract_place(raw, spec, strict=True)
        elif spec.kind == "id" and not re.search(r"\d|" + "|".join(UNITS), t):
            v = None
        else:
            v = EXTRACTORS[spec.kind](raw, spec, frame.today)
        if v is not None:
            slots[spec.name] = v

    intent = None
    for name, patterns in frame.intents:
        if any(re.search(p, t) for p in patterns):
            intent = name
            break
    u.intent = intent

    yn = extract_yes_no(t) if frame.yes_no or (exp and exp.kind == "yesno") else None
    if u.act == "skip":
        u.slots = slots
        return u
    if frame.yes_no and yn is not None:
        u.act = "yes" if yn else "no"
        u.slots = {k: v for k, v in slots.items() if not (exp and exp.kind == "yesno"
                                                          and k == exp.name)}
        u.confidence = 0.9
        return u
    if slots:
        u.act, u.slots, u.confidence = "value", slots, 0.85
        return u
    if intent:
        u.act, u.confidence = ("question" if QUESTION.match(t) or t.endswith("?")
                               else "value"), 0.75
        return u
    if QUESTION.match(t) or raw.strip().endswith("?"):
        u.act, u.confidence = "question", 0.6
        return u
    if yn is not None:
        u.act = "yes" if yn else "no"
        u.confidence = 0.7
    return u
