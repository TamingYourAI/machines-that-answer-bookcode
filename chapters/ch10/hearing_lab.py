"""Builders' Chapter 10 lab: hearing, measured on the Service Line's words.

Six steps:

  1. word error rate  the same eleven utterances under four conditions, and
                      what the rate hides: the account numbers, amounts,
                      and street names the call depends on
  2. partials         a recognizer's partial results for one account number,
                      and when it is safe to act on them
  3. vocabulary       boosting the service area's names: what it fixes, and
                      what it starts to hear that nobody said
  4. numbers          spoken numbers normalized, validated, and read back
  5. cohorts          accuracy by group of callers, with its uncertainty
  6. what is kept     transcripts redacted before they are stored

Modes (select with HEARING_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Replace the stand-in recognizer with your own,
           run on recorded calls (evidence class: recorded replay).

  python3 hearing_lab.py                  run and print the report
  python3 hearing_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 hearing_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The recognizer is a
stand-in whose confusions are modelled on narrowband audio and noise; the
cohort counts are invented to show the method.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

# ---------------------------------------------------------------- 1. WER


def align(ref: list[str], hyp: list[str]) -> tuple[int, int, int]:
    """Substitutions, deletions, and insertions, by edit distance."""
    d = [[(0, 0, 0, 0)] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(1, len(ref) + 1):
        d[i][0] = (i, 0, i, 0)
    for j in range(1, len(hyp) + 1):
        d[0][j] = (j, 0, 0, j)
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            c, s, dl, ins = d[i - 1][j - 1]
            same = ref[i - 1] == hyp[j - 1]
            options = [(c + (not same), s + (not same), dl, ins)]
            c, s, dl, ins = d[i - 1][j]
            options.append((c + 1, s, dl + 1, ins))
            c, s, dl, ins = d[i][j - 1]
            options.append((c + 1, s, dl, ins + 1))
            d[i][j] = min(options)
    return d[-1][-1][1:]


def wer(pairs: list[tuple[str, str]]) -> float:
    errors = words = 0
    for ref, hyp in pairs:
        s, dl, ins = align(ref.split(), hyp.split())
        errors += s + dl + ins
        words += len(ref.split())
    return errors / words


# The stand-in recognizer: for each word, the alternatives it weighs and
# their acoustic scores, by condition. Boost adds weight to listed names.
CONDITIONS = ("app, wideband", "phone", "phone, kitchen noise",
              "speakerphone")


def hear(text: str, condition: str, lattice: dict, vocab: list[str],
         boost: float = 0.0) -> str:
    level = CONDITIONS.index(condition)
    out, prev = [], ""
    for w in text.split():
        options = {w: 1.0}
        for lv, key, alts in lattice:
            if lv <= level and key in (w, f"{prev} {w}"):
                options = dict(alts)
        best = max(options, key=lambda o: options[o]
                   + (boost if o in vocab else 0))
        if best:
            out.append(best)
        prev = w
    if level >= 3:
        out.insert(0, "okay")              # the agent's own voice, echoed
    return " ".join(out)


# ---------------------------------------------------------------- 4. numbers

DIGITS = {"zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4,
          "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
TEENS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
         "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
        "seventy": 70, "eighty": 80, "ninety": 90}
NAMES = [k for k in DIGITS if k != "oh"]          # zero, one, two, ...
SOUND_ALIKE = {15: 50, 50: 15, 16: 60, 60: 16, 13: 30, 30: 13, 14: 40,
               40: 14, 17: 70, 70: 17, 18: 80, 80: 18, 19: 90, 90: 19}


def digits(words: list[str]) -> str:
    """Spoken digits, doubles, and pairs ("twenty two") to a digit string."""
    out, i = "", 0
    while i < len(words):
        w = words[i]
        if w == "double" and i + 1 < len(words) and words[i + 1] in DIGITS:
            out += str(DIGITS[words[i + 1]]) * 2
            i += 2
            continue
        if w in TENS:
            nxt = words[i + 1] if i + 1 < len(words) else ""
            out += str(TENS[w] + DIGITS.get(nxt, 0))
            i += 2 if nxt in DIGITS and nxt not in ("zero", "oh") else 1
            continue
        if w in TEENS:
            out += str(TEENS[w])
        elif w in DIGITS:
            out += str(DIGITS[w])
        i += 1
    return out


def account(spoken: str) -> str:
    """An account number is four digits; anything else is asked again."""
    got = digits(spoken.split())
    if len(got) == 4:
        return f"{got}: read back as {' '.join(NAMES[int(c)] for c in got)}"
    return f"{got or 'nothing'}: {len(got)} digits; ask again, offer keypad"


def amount(spoken: str) -> str:
    """An amount the phone line can confuse is read back digit by digit."""
    value = int(digits(spoken.split()) or 0)
    if value in SOUND_ALIKE:
        spelled = " ".join(NAMES[int(c)] for c in str(value))
        return (f"{value}: sounds like {SOUND_ALIKE[value]}; "
                f"confirm \"{spelled}\"")
    return f"{value}: confirm"


# The entities the call depends on, read from a transcript.
STREETS = ("alder road", "kestrel way")
PLACES = ("ashby",)


def entities(text: str) -> dict:
    found = {}
    m = re.search(r"account number is ((?:\w+ ?){1,6})$", text)
    if m or re.fullmatch(r"(?:(?:zero|one|two|three|four|five|six|seven|"
                         r"eight|nine) ?){4}", text):
        found["account"] = digits((m.group(1) if m else text).split())
    for street in STREETS:
        if street in text:
            head = text.split(street)[0].split()
            found["address"] = f"{digits(head)} {street}"
    for place in PLACES:
        if place in text.split():
            found["place"] = place
    m = re.search(r"pay (\w+) dollars", text)
    if m:
        found["amount"] = digits([m.group(1)])
    if text.startswith("yes") or text.endswith("yes book it"):
        found["yes"] = "yes"
    return found


def entity_accuracy(pairs: list[tuple[str, str]]) -> tuple[int, int]:
    right = total = 0
    for ref, hyp in pairs:
        want, got = entities(ref), entities(hyp)
        total += len(want)
        right += sum(got.get(k) == v for k, v in want.items())
    return right, total


# ---------------------------------------------------------------- 2. partials


def stable_prefix(partials: list[str], k: int = 3) -> list[str]:
    """Words unchanged across the last k partials are safe to act on."""
    out = []
    for n in range(len(partials)):
        window = [p.split() for p in partials[max(0, n - k + 1):n + 1]]
        if len(window) < k:
            out.append("")
            continue
        common = []
        for words in zip(*window):
            if len(set(words)) > 1:
                break
            common.append(words[0])
        out.append(" ".join(common))
    return out


# ---------------------------------------------------------------- 5. cohorts


def wilson(right: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """A 95 percent interval for a share measured on n calls."""
    p = right / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) \
        / (1 + z * z / n)
    return centre - half, centre + half


def verdict(right: int, n: int, line: float) -> str:
    lo, hi = wilson(right, n)
    if lo >= line:
        return "meets"
    if hi < line:
        return "below"
    return "unknown"


# ---------------------------------------------------------------- 6. kept

CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def normalize(spoken: str) -> str:
    """Spoken forms to written ones, before anything is stored."""
    text = spoken.replace(" dot ", ".").replace(" at ", "@")
    words, out, run = text.split(), [], []
    for w in words + [""]:
        if w in DIGITS or w == "double":
            run.append(w)
            continue
        if run:
            d = digits(run)
            out.append(" ".join(d[i:i + 4] for i in range(0, len(d), 4)))
            run = []
        if w:
            out.append(w)
    return " ".join(out)


def keep(final: str) -> str:
    """What the transcript store may hold: never a card number."""
    text = normalize(final)
    if CARD.search(text):
        return "nothing: a card number reached the recognizer; incident"
    text = re.sub(r"\S+@\S+", "[email]", text)
    return re.sub(r"\b\d{4}\b", "[account]", text)


# ---------------------------------------------------------------- inputs

UTTERANCES = [
    "my account number is two two three one",
    "fourteen alder road",
    "the display on my meter has gone blank",
    "i can pay fifteen dollars a week",
    "twelve sixty kestrel way",
    "is there an outage in ashby",
    "four four one seven",
    "yes book it",
    "i want to talk to a person",
    "i need to alter my payment date",
    "the older meter was fine"]

LATTICE = [                      # level, word (or "previous word"), options
    (0, "blank", [("black", 0.55), ("blank", 0.45)]),
    (1, "fifteen", [("fifty", 0.55), ("fifteen", 0.45)]),
    (1, "kestrel", [("castrel", 0.6), ("kestrel", 0.3)]),
    (1, "ashby", [("ashley", 0.55), ("ashby", 0.4)]),
    (1, "alter", [("alter", 0.8), ("alder", 0.15)]),
    (1, "older", [("older", 0.7), ("alder", 0.2)]),
    (2, "is two", [("to", 0.52), ("two", 0.48)]),
    (2, "a", [("", 0.6), ("a", 0.4)])]

VOCAB = ["alder", "kestrel", "ashby"]

PARTIALS = [(200, "my"), (400, "my account"), (600, "my account number"),
            (800, "my account number is to"),
            (1000, "my account number is to two"),
            (1200, "my account number is two two three"),
            (1400, "my account number is two two three one"),
            (1600, "my account number is two two three one"),
            (1900, "my account number is two two three one")]

SPOKEN_ACCOUNTS = ["two two three one", "double two three one",
                   "twenty two thirty one", "to two three one",
                   "four four one seven"]
SPOKEN_AMOUNTS = ["fifteen", "fifty", "twenty five"]

COHORTS = [("all callers", 400, 372), ("65 and over", 60, 48),
           ("second-language speakers", 45, 39),
           ("on a speakerphone", 12, 10)]
LINE = 0.90

FINALS = ["my account number is two two three one",
          "my email is dana dot moran at example dot com",
          "my card number is four one one one one one one one one one one "
          "one one one one one"]


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"utterances": UTTERANCES, "lattice": LATTICE, "vocab": VOCAB,
                "partials": PARTIALS, "accounts": SPOKEN_ACCOUNTS,
                "amounts": SPOKEN_AMOUNTS, "cohorts": COHORTS, "line": LINE,
                "finals": FINALS}
    if mode == "fixture":
        return json.loads((FIXTURES / "hearing.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ---------------------------------------------------------------- report


def results(data: dict, condition: str, boost: float = 0.0) -> list:
    return [(u, hear(u, condition, data["lattice"], data["vocab"], boost))
            for u in data["utterances"]]


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    say = out.append
    say(f"hearing lab, mode={mode}; evidence class: simulated")
    say("")
    n = len(data["utterances"])
    say(f"1. word error rate, and what it hides ({n} utterances)")
    say(f"   {'condition':<24}{'word errors':>12}{'entities right':>17}")
    for c in CONDITIONS:
        pairs = results(data, c)
        right, total = entity_accuracy(pairs)
        say(f"   {c:<24}{wer(pairs) * 100:>11.1f}%{right:>11} of {total}")
    ref = data["utterances"][3]
    hyp = hear(ref, "phone, kitchen noise", data["lattice"], data["vocab"])
    s, dl, ins = align(ref.split(), hyp.split())
    say(f"   heard \"{hyp}\"")
    say(f"   for   \"{ref}\":")
    say(f"   {s} substituted, {dl} deleted, {ins} inserted; the amount is "
        "wrong")
    say("")
    say("2. partials for one account number (phone)")
    texts = [t for _, t in data["partials"]]
    say(f"   {'ms':>6}  {'partial':<40}stable up to")
    for (ms, text), stable in zip(data["partials"], stable_prefix(texts)):
        say(f"   {ms:>6}  {text:<40}{(stable.split() or [''])[-1]}")
    early = entities(texts[4]).get("account")
    final = entities(texts[-1]).get("account")
    say(f"   acting on the partial at {data['partials'][4][0]} ms reads "
        f"account {early}; the final reads {final}")
    say("")
    say("3. boosting the service area's names (phone)")
    say(f"   {'boost':>7}{'names heard right':>20}"
        f"{'names heard, not said':>24}")
    for b in (0.0, 0.2, 0.4, 0.6, 0.8):
        pairs = results(data, "phone", b)
        right = sum(v in h.split() for u, h in pairs for v in data["vocab"]
                    if v in u.split() and v != "alder")
        false = sum(max(0, h.split().count(v) - u.split().count(v))
                    for u, h in pairs for v in data["vocab"])
        say(f"   {b:>7.1f}{right:>14} of 2{false:>18}")
    say("")
    say("4. numbers: normalized, checked, read back")
    for spoken in data["accounts"]:
        label = f'account "{spoken}"'
        say(f"   {label:<34}{account(spoken)}")
    for spoken in data["amounts"]:
        label = f'amount "{spoken}"'
        say(f"   {label:<34}{amount(spoken)}")
    say("")
    line = data["line"]
    say(f"5. entity accuracy by cohort (line {line * 100:.0f}%, "
        "95% interval)")
    say(f"   {'cohort':<26}{'n':>4}{'right':>8}{'interval':>16}  verdict")
    for name, total, right in data["cohorts"]:
        lo, hi = wilson(right, total)
        say(f"   {name:<26}{total:>4}{right / total * 100:>7.1f}%"
            f"{lo * 100:>8.1f} to {hi * 100:>4.1f}%  "
            f"{verdict(right, total, line)}")
    say("")
    say("6. what is kept")
    for final in data["finals"]:
        heard = normalize(final)
        say(f"   heard: {heard}")
        say(f"   kept:  {keep(final)}")
    return "\n".join(line.rstrip() for line in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("HEARING_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"hearing_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "hearing.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/hearing.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("HEARING_LAB_MODE", "mock")))
    else:
        run_mode()
