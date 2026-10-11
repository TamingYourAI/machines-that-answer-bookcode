"""Builders' Chapter 12 lab: speaking, from the model's text to the sound.

Six steps:

  1. streaming        when the first audio starts: the whole reply, by
                      sentence, by clause, or streamed; and the number a
                      careless chunker splits in two
  2. the buffer       a synthesizer slowed at the start of a line: stutter,
                      and the start buffer that prevents it
  3. the formatter    one rebooking said in three locales
  4. the lexicon      the brief's names compiled for three kinds of
                      synthesizer
  5. lists and markup what the model wrote, and what the agent may say
  6. the panel        two versions of one voice: mean opinion score, and
                      numbers heard correctly

Modes (select with SPEAKING_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point step 1 at your synthesizer's streaming
           interface and step 6 at your own panel's score sheets (evidence
           class: live laboratory).

  python3 speaking_lab.py                  run and print the report
  python3 speaking_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 speaking_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The synthesizer's
timings are stand-ins, and the panel's scores are invented to show the
method; they say nothing about any product.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

TOKEN_MS = 25            # the model writes one token every 25 ms
TTFB_MS = 85             # first audio byte after a chunk is sent (Chapter 6)

# ------------------------------------------------------------ the formatter

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven",
        "eight", "nine"]
TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety"]
ORD = {1: "first", 2: "second", 3: "third", 5: "fifth", 8: "eighth",
       9: "ninth", 12: "twelfth"}


def words(n: int) -> str:
    """0 to 999,999 in English words, as a person says a quantity."""
    if n < 10:
        return ONES[n]
    if n < 20:
        return TEENS[n - 10]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + (" " + words(rest) if rest
                                              else "")
    rest = n % 1000
    return words(n // 1000) + " thousand" + (" " + words(rest) if rest
                                             else "")


def ordinal(n: int) -> str:
    if n in ORD:
        return ORD[n]
    if n < 20:
        return words(n) + "th"
    tens, ones = divmod(n, 10)
    if ones == 0:
        return TENS[tens][:-1] + "ieth"
    return TENS[tens] + "-" + ordinal(ones)


DE_ONES = ["null", "eins", "zwei", "drei", "vier", "fünf", "sechs",
           "sieben", "acht", "neun"]
DE_TEENS = ["zehn", "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn",
            "sechzehn", "siebzehn", "achtzehn", "neunzehn"]
DE_TENS = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig",
           "siebzig", "achtzig", "neunzig"]
DE_DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
           "Samstag", "Sonntag"]
DE_MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]


def de_words(n: int) -> str:
    """0 to 999 in German: units come before the tens ("vierundachtzig")."""
    if n < 10:
        return DE_ONES[n]
    if n < 20:
        return DE_TEENS[n - 10]
    if n < 100:
        ones = n % 10
        unit = "ein" if ones == 1 else DE_ONES[ones]
        return (unit + "und" if ones else "") + DE_TENS[n // 10]
    rest = n % 100
    return ("ein" if n // 100 == 1 else DE_ONES[n // 100]) + "hundert" + (
        de_words(rest) if rest else "")


def de_ordinal_dative(n: int) -> str:
    """The day after "am ... dem": the ending depends on the sentence."""
    special = {1: "ersten", 3: "dritten", 7: "siebten", 8: "achten"}
    if n in special:
        return special[n]
    return de_words(n) + ("ten" if n < 20 else "sten")


def say(kind: str, value: str, locale: str) -> str:
    """Written values to the words a locale's listeners expect."""
    if kind == "time":
        h, m = (int(x) for x in value.split(":"))
        if locale == "de-DE":
            return f"um {de_words(h)} Uhr {de_words(m)}"
        if locale == "en-GB":
            return f"at {words(h)} {words(m)}"
        part = ("in the morning" if h < 12 else "in the afternoon"
                if h < 17 else "in the evening")
        return f"at {words(h % 12 or 12)} {words(m)} {part}"
    if kind == "date":
        d = dt.date.fromisoformat(value)
        if locale == "de-DE":
            return (f"am {DE_DAYS[d.weekday()]}, dem "
                    f"{de_ordinal_dative(d.day)} {DE_MONTHS[d.month - 1]}")
        if locale == "en-GB":
            return f"on {d:%A} the {ordinal(d.day)} of {d:%B}"
        return f"on {d:%A}, {d:%B} {ordinal(d.day)}"
    # money carries its currency ("EUR 84.50"); the locale decides only how it is said
    code, _, amount = value.rpartition(" ")
    units, cents = (int(x) for x in amount.split("."))
    code = code or "USD"
    if locale == "de-DE":
        name = {"EUR": "Euro", "USD": "Dollar", "GBP": "Pfund"}[code]
        return f"{de_words(units)} {name} {de_words(cents)}"
    name = {"EUR": "euros", "USD": "dollars", "GBP": "pounds"}[code]
    if locale == "en-GB":
        return f"{words(units)} {name} {words(cents)}"
    return f"{words(units)} {name} and {words(cents)} cents"


MONEY = re.compile(r"\$(\d+)(?:\.(\d\d))?")
TIME = re.compile(r"\b(\d{1,2}):(\d\d) ?(AM|PM)\b")


def speakable_numbers(text: str) -> str:
    """Money, clock times, and bare numbers become words (en-US)."""
    text = MONEY.sub(lambda m: say("money", f"{m[1]}.{m[2] or '00'}",
                                   "en-US"), text)
    text = text.replace(" and zero cents", "")

    def clock(m):
        h = int(m[1]) % 12 + (12 if m[3] == "PM" else 0)
        spoken = say("time", f"{h}:{m[2]}", "en-US")[3:]
        return spoken.replace(" zero", "")
    text = TIME.sub(clock, text)
    return re.sub(r"\b\d+\b", lambda m: words(int(m[0])), text)


# ------------------------------------------------------------ 1. streaming


def tokens(text: str) -> list[str]:
    """A stand-in tokenizer: words, and numbers split at their points."""
    return re.findall(r"\$|\d+|\.|,|\?|[A-Za-z']+", text)


def join(toks: list[str]) -> str:
    out = ""
    for t in toks:
        glue = out and t not in ".,?" and not out.endswith("$") and not (
            t.isdigit() and out.endswith("."))
        out += (" " if glue else "") + t
    return out


def chunks(toks: list[str], how: str) -> list[tuple[int, str]]:
    """(index of the last token, text) for each chunk sent to the voice."""
    out, start = [], 0
    for i, t in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        inside_number = t == "." and nxt.isdigit()
        if how == "whole reply":
            end = i == len(toks) - 1
        elif how == "by sentence":
            end = t in ".?" and not inside_number
        elif how == "by clause":
            end = t in ".,?" and not inside_number
        elif how == "by clause, careless":
            end = t in ".,?"
        else:                                  # streamed, entity-safe
            end = not (t == "$" or t.isdigit() or inside_number
                       or (t == "." and toks[i - 1].isdigit()))
        if end or i == len(toks) - 1:
            out.append((i, join(toks[start:i + 1])))
            start = i + 1
    return out


def first_audio_ms(toks: list[str], how: str) -> int:
    """From the model's first token to the first audio byte."""
    return chunks(toks, how)[0][0] * TOKEN_MS + TTFB_MS


# ------------------------------------------------------------ 2. the buffer

CHUNK_MS = 200           # the synthesizer returns audio in 200 ms pieces
RTF = 0.3                # it makes 1 s of audio in 0.3 s, normally
SLOW_RTF, SLOW_UNTIL = 1.6, 900      # under load, slower than real time


def play(line_ms: int, start_buffer_ms: int,
         loaded: bool) -> tuple[int, int, int]:
    """First audio, underruns, and silence heard inside the line (ms)."""
    ready, t = [], TTFB_MS
    for k in range(0, line_ms, CHUNK_MS):
        ready.append(t)
        slow = loaded and t < SLOW_UNTIL
        t += CHUNK_MS * (SLOW_RTF if slow else RTF)
    need = start_buffer_ms // CHUNK_MS
    clock = ready[min(need, len(ready) - 1)]
    first, underruns, gap = clock, 0, 0
    for at in ready:
        if at > clock:
            underruns += 1
            gap += at - clock
            clock = at
        clock += CHUNK_MS
    return round(first), underruns, round(gap)


# ------------------------------------------------------------ 4. the lexicon


def compile_lexicon(name: str, entry: dict, kind: str) -> str:
    """One entry of the brief's lexicon, in the form a synthesizer takes."""
    if kind == "loads a lexicon file":
        return (f"<lexeme><grapheme>{name}</grapheme>"
                f"<phoneme>{entry['x-sampa']}</phoneme></lexeme>")
    if kind == "takes phoneme tags":
        return (f"<phoneme alphabet=\"x-sampa\" ph='{entry['x-sampa']}'>"
                f"{name}</phoneme>")
    return entry["respell"]


# ------------------------------------------------------------ 5. markup

SPELLED = {"Rd": "Road", "St": "Street", "approx.": "about"}


def speakable(text: str, limit: int = 3) -> tuple[str, list[str]]:
    """What the agent may say, and what the filter found on the way."""
    found = []
    if re.search(r"\*\*|^\d+\. |^- ", text, re.M):
        found.append("markdown")
    lines = text.replace("**", "").splitlines()
    listed = re.compile(r"^(?:\d+\.|-) ")
    items = [listed.sub("", ln) for ln in lines if listed.match(ln)]
    rest = [ln for ln in lines if not listed.match(ln)]
    if len(items) > limit:
        found.append(f"{len(items)} options (at most {limit} are spoken)")
    if re.search(r"https?://\S+", text):
        found.append("a link (never read aloud; sent by text)")
    if MONEY.search(text) or TIME.search(text):
        found.append("money and times in digits")
    opts = [speakable_numbers(i) for i in items[:limit]]
    said = f"{rest[0].rstrip(':')}: {', '.join(opts[:-1])}, or {opts[-1]}."
    for line in rest[1:]:
        line = re.sub(r"See https?://\S+ for [a-z ]+\.", "", line).strip()
        if line:
            said += " " + speakable_numbers(line)
    if len(items) > limit or any("link" in f for f in found):
        said += " I'll text you the full list."
    n = len(re.findall(r"[.?!](?:\s|$)", said))
    if n > 2:
        found.append(f"{n} sentences in one turn (a design finding)")
    return said, found


# ------------------------------------------------------------ 6. the panel


def mean_ci(scores: list[int]) -> tuple[float, float]:
    """Mean opinion score, with a 95 percent interval (normal approx.)."""
    n = len(scores)
    m = sum(scores) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in scores) / (n - 1))
    return m, 1.96 * sd / math.sqrt(n)


def wilson(right: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = right / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) \
        / (1 + z * z / n)
    return centre - half, centre + half


# ------------------------------------------------------------ inputs

BILL = ("Your September bill is $184.20, and August's was $91.60. "
        "September includes an estimated reading from the new meter.")
LINE_MS = 3200                            # the first sentence, spoken
REBOOKING = [("time", "19:40"), ("date", "2026-09-30"), ("money", "EUR 84.50")]
LEXICON = {"Alder": {"respell": "AL-der", "x-sampa": "\"{l.d@`"},
           "Kestrel": {"respell": "KES-trel", "x-sampa": "\"kEs.tr\\@l"},
           "Ashby": {"respell": "ASH-bee", "x-sampa": "\"{S.bi"}}
TEST_LINES = ["Is the visit at fourteen Alder Road?",
              "Is there an outage in Ashby?",
              "The visit is at twelve sixty Kestrel Way."]
MODEL_TEXT = ("Here are the openings:\n"
              "1. **Tuesday** at 9:00 AM\n2. **Tuesday** at 1:00 PM\n"
              "3. **Wednesday** at 9:00 AM\n4. **Saturday** at 9:00 AM\n"
              "The call-out charge is $60.00. See https://example.com/book "
              "for the full calendar.")
PROMPTS = ["the fee line", "the balance", "a date", "an address",
           "a repair turn", "bad news"]
NUMBER_PROMPTS = [0, 1, 2, 3]
# eight listeners x six prompts, at telephone bandwidth, 1 to 5 (ACR)
PANEL = {
    "voice B, pinned": {
        "scores": [[4, 4, 4, 4, 3, 4], [5, 4, 4, 5, 4, 4], [4, 4, 5, 4, 3, 4],
                   [4, 5, 4, 4, 4, 5], [4, 4, 4, 4, 3, 4], [5, 4, 4, 4, 4, 4],
                   [4, 4, 4, 5, 3, 4], [4, 4, 5, 4, 4, 5]],
        "heard": [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1],
                  [1, 1, 1, 1], [1, 0, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]},
    "voice B, updated": {
        "scores": [[5, 4, 4, 5, 3, 4], [5, 5, 4, 5, 4, 5], [4, 4, 5, 4, 4, 4],
                   [5, 5, 4, 4, 4, 5], [4, 4, 5, 4, 3, 4], [5, 5, 4, 4, 4, 4],
                   [4, 4, 4, 5, 4, 5], [5, 4, 5, 4, 4, 5]],
        "heard": [[0, 1, 1, 1], [1, 1, 1, 1], [1, 0, 1, 1], [1, 1, 1, 1],
                  [0, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]}}
LINE = 0.95                               # numbers heard (Chapter 3)


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"bill": BILL, "line_ms": LINE_MS, "rebooking": REBOOKING,
                "lexicon": LEXICON, "test_lines": TEST_LINES,
                "model_text": MODEL_TEXT, "prompts": PROMPTS,
                "number_prompts": NUMBER_PROMPTS, "panel": PANEL,
                "line": LINE}
    if mode == "fixture":
        return json.loads((FIXTURES / "speaking.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ------------------------------------------------------------ report

HOWS = ("whole reply", "by sentence", "by clause", "streamed")


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"speaking lab, mode={mode}; evidence class: simulated")
    put("")
    toks = tokens(data["bill"])
    put("1. streaming: first audio after the model's first token")
    put(f"   (one token every {TOKEN_MS} ms; {TTFB_MS} ms from a chunk to "
        "its first audio)")
    for i, part in enumerate(textwrap.wrap(data["bill"], 62)):
        put(f"   {'reply' if i == 0 else '':<7}{part}")
    put(f"   {'chunking':<22}{'first audio':>12}{'chunks':>8}")
    for how in HOWS:
        put(f"   {how:<22}{first_audio_ms(toks, how):>9} ms"
            f"{len(chunks(toks, how)):>8}")
    careless = [text for _, text in chunks(toks, "by clause, careless")]
    spoken = " ".join(speakable_numbers(careless[0]).split()[-6:])
    put("   a chunker that ends a clause at every point splits the amount:")
    put(f"     sends \"{careless[0]}\"")
    put(f"       and the voice says \"...{spoken}\"")
    put(f"     then sends \"{careless[1]}\" and the voice says "
        f"\"{speakable_numbers(careless[1])}\"")
    put("")
    put(f"2. the buffer: a {data['line_ms'] / 1000:.1f} s line; synthesis at "
        f"{RTF}x real time, or at {SLOW_RTF}x")
    put(f"   for the first {SLOW_UNTIL} ms under load")
    put(f"   {'start buffer':<20}{'first audio':>12}{'underruns':>11}"
        f"{'silence heard':>16}")
    for loaded, bufs in ((False, (0, 200)), (True, (0, 200, 400))):
        put(f"   {'under load' if loaded else 'normal load'}")
        for buf in bufs:
            first, n, gap = play(data["line_ms"], buf, loaded)
            put(f"     {str(buf) + ' ms':<18}{first:>9} ms{n:>11}"
                f"{gap:>13} ms")
    put("")
    put("3. one rebooking, three locales (the Disruption Desk)")
    put("   written: departs 19:40 on 2026-09-30; fare difference EUR 84.50")
    for loc in ("en-US", "en-GB", "de-DE"):
        spoken = "; ".join(say(k, v, loc) for k, v in data["rebooking"])
        for i, part in enumerate(textwrap.wrap(spoken, 60)):
            put(f"   {loc if i == 0 else '':<8}{part}")
    put("")
    put("4. the lexicon (brief 1.3), compiled for three kinds of synthesizer")
    name, entry = "Alder", data["lexicon"]["Alder"]
    put(f"   Alder: the brief says {entry['respell']}; in X-SAMPA "
        f"{entry['x-sampa']}")
    for kind in ("loads a lexicon file", "takes phoneme tags",
                 "takes plain text only"):
        put(f"   {kind}")
        put(f"     {compile_lexicon(name, entry, kind)}")
    names = set(data["lexicon"])
    used = {w.strip("?.") for line in data["test_lines"]
            for w in line.split()} & names
    put(f"   coverage: {len(used)} of {len(names)} service-area names in the "
        "test lines have an entry")
    put("")
    said, found = speakable(data["model_text"])
    put("5. what the model wrote, and what the agent may say")
    first_line = data["model_text"].splitlines()[1]
    put(f"   wrote: {data['model_text'].splitlines()[0]} {first_line} ...")
    for i, f in enumerate(found):
        put(f"   {'found:' if i == 0 else '':<7}{f}")
    for i, part in enumerate(textwrap.wrap(said, 62)):
        put(f"   {'said:' if i == 0 else '':<7}{part}")
    put("")
    line = data["line"]
    n_listeners = len(next(iter(data["panel"].values()))["scores"])
    put(f"6. the panel: {n_listeners} listeners, {len(data['prompts'])} "
        "prompts, telephone bandwidth")
    put(f"   {'version':<20}{'MOS':>6}{'95% interval':>15}"
        f"{'numbers heard':>15}{'verdict':>9}")
    worst = {}
    for version, p in data["panel"].items():
        flat = [s for row in p["scores"] for s in row]
        m, h = mean_ci(flat)
        right = sum(sum(r) for r in p["heard"])
        total = sum(len(r) for r in p["heard"])
        lo, _ = wilson(right, total)
        verdict = "pass" if right / total >= line else "fail"
        put(f"   {version:<20}{m:>6.2f}{m - h:>9.2f} to {m + h:.2f}"
            f"{right:>8} of {total}{verdict:>9}")
        per = [sum(row[k] for row in p["scores"]) / len(p["scores"])
               for k in range(len(data["prompts"]))]
        worst[version] = min(zip(per, data["prompts"]))
    for version, (score, prompt) in worst.items():
        put(f"   lowest prompt, {version}: {prompt} ({score:.2f})")
    put(f"   pass: numbers heard {line * 100:.0f}% or more; MOS is reported, "
        "not decisive")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("SPEAKING_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"speaking_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "speaking.json").write_text(
            json.dumps(inputs("mock"), indent=1, ensure_ascii=False))
        print("wrote fixtures/speaking.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("SPEAKING_LAB_MODE", "mock")))
    else:
        run_mode()
