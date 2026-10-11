"""Builders' Chapter 13 lab: speech-to-speech, and the hybrid's payment turn.

Six steps:

  1. exact words       the disclosure and the storm waiver's terms on 400
                       stand-in sessions: instructed to a speech model, or
                       played on a fixed path
  2. the policy layer  what the speech model proposes during a payment
                       turn, and what the rules outside it decide
  3. who hears the card  audio by recipient while a card is keyed: a pure
                       speech-to-speech session, and the hybrid
  4. checking sound    how much of a wrong sentence plays before a check on
                       its transcript can act
  5. one object        the payment flow's dialogue object compiled for the
                       cascade and for a speech-to-speech model
  6. one call          the recurring caller's booking turn across the
                       speech stack, as Part III built it (the pipeline)

Modes (select with S2S_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point step 1 at your realtime interface with
           recorded caller audio, and score its audio, not its transcript
           (evidence class: live laboratory).

  python3 s2s_lab.py                  run and print the report
  python3 s2s_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 s2s_lab.py --check          compare with the frozen output

Evidence class of every number printed: simulated. The paraphrase rates,
the transcript's lag, and the proposals are stand-ins; they describe no
product.
"""
from __future__ import annotations

import json
import os
import random
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

# ----------------------------------------------------------- 1. exact words

DISCLOSURE = "This is the utility's automated assistant. How can I help?"
WAIVER = ("We can remove one twelve-dollar late fee, once in twelve "
          "months.")
MUST_SAY = {"disclosure": ["automated assistant"],
            "waiver": ["one", "twelve-dollar", "once in twelve months"]}


def instructed(line: str, variants: list[str], rate: float,
               rng: random.Random) -> str:
    """A speech model told to say a line says it, usually."""
    return rng.choice(variants) if rng.random() < rate else line


def terms_kept(said: str, kind: str) -> bool:
    return all(t in said for t in MUST_SAY[kind])


# ------------------------------------------------------------ 2. the policy layer

LADDER = ["none", "pin", "pin + code"]   # the proof ladder (leaders' 7)


def gate(action: str, args: dict, call: dict) -> str:
    """The policy layer decides; the speech model only proposes (JDG-4)."""
    if action == "read_bill":
        return "allowed: a read, at PIN level" if LADDER.index(
            call["verified"]) >= 1 else "refused: verify first"
    if action == "take_payment":
        if LADDER.index(call["verified"]) < 1:
            return "refused: verify first"
        if not call["isolated_path"]:
            return "refused: no isolated path; a person takes it"
        if args["amount"] != call["balance"]:
            return f"refused: {args['amount']:.2f} is not the balance"
        return "allowed: the fixed path reads the amount"
    if action == "apply_waiver":
        if not call["storm_area"]:
            return "refused: outside the storm area (memo 114)"
        if call["waived_in_12_months"]:
            return "refused: one waiver in twelve months"
        return "allowed: the fixed path states the terms"
    return "refused: not a tool this line offers"


# ------------------------------------------------------------ 3. the card

FRAME_MS = 20


def recipients(design: str, keyed_ms: int, digits: int) -> dict:
    """What reaches each party while the card is keyed."""
    frames = keyed_ms // FRAME_MS
    if design == "pure speech-to-speech":
        return {"the speech provider": f"{frames} frames, tones included",
                "the call recording": "the tones, recoverable",
                "the payment processor": "nothing: no path to it"}
    return {"the speech provider": "0 frames: its input is paused",
            "the call recording": "masked tones",
            "the payment processor": f"{digits} digits, as key events"}


# ------------------------------------------------------------ 4. checking

WORDS_PER_MIN = 150                     # the voice brief (Chapter 3)


def check_lag(sentence: str, match: str, lag_ms: int) -> dict:
    """When a check on the transcript can act, against what has played."""
    words = sentence.rstrip(".").split()
    per = 60_000 / WORDS_PER_MIN
    at = next(i for i, w in enumerate(words) if match in w)
    ends = round(len(words) * per)
    acts = round((at + 1) * per) + lag_ms
    heard = min(len(words), round(acts / per))
    return {"ends_ms": ends, "acts_ms": acts, "heard": heard,
            "words": len(words)}


# ------------------------------------------------------------ 5. one object

FLOW = [("greet", "fixed"), ("find out what is needed", "free"),
        ("read the balance", "fixed"), ("take the card", "isolated"),
        ("confirm the payment", "fixed"), ("anything else", "free")]


def compile_step(kind: str, road: str) -> str:
    """One dialogue object, two roads: the kind of step decides."""
    if kind == "fixed":
        return "fixed line, exact"
    if kind == "isolated":
        return ("keypad, isolated" if road == "cascade"
                else "keypad; model's input paused")
    return "line from the object" if road == "cascade" else (
        "the model's own words")


# ------------------------------------------------------ 6. one call

def booking_turn(t: dict) -> list[tuple[int, str, str, bool]]:
    """The booking turn on the pipeline, with only what Part III built:
    each span in order, on the caller's clock. The last field marks the
    layers Part III built; the model and the scheduler come in Part IV."""
    reach = t["in"]
    eot = reach + t["eot"]
    final = eot + t["final"]
    token = final + t["first_token"]
    audio = token + t["first_audio"]
    sent = token + t["tool_call"]
    commit = sent + t["scheduler"]
    token2 = commit + t["first_token"]
    audio2 = token2 + t["first_audio"]
    out = t["send"] + t["out"]
    return [
        (0, "transport", "\"Yes, go ahead.\" leaves the caller", True),
        (reach, "transport", "her audio reaches the agent", True),
        (eot, "turn-taking", f"end of turn after {t['eot']} ms: the words "
         "answer the question", True),
        (final, "hearing", "final transcript: \"yes, go ahead\"", True),
        (token, "thinking", "the model's first token: \"Booking that "
         "now.\"", False),
        (audio, "speaking", "first audio, streamed", True),
        (audio + out, "transport", "the caller hears it", True),
        (sent, "systems", "the model's book_visit call reaches the "
         "scheduler", False),
        (commit, "systems", "the scheduler commits the booking", False),
        (token2, "thinking", "the model's first token of the outcome",
         False),
        (audio2, "speaking", "first audio: \"You're booked for Tuesday at "
         "nine.\"", True),
        (audio2 + out, "transport", "the caller hears it", True)]


# ------------------------------------------------------------ inputs

DISCLOSURE_VARIANTS = [
    "Hi, this is the utility's virtual assistant. What can I do for you?",
    "You're through to the utility's assistant. How can I help?"]
WAIVER_VARIANTS = [
    "We can waive your late fees.",
    "We can waive the twelve-dollar late fee for you.",
    "We can remove one twelve-dollar late fee, once a year."]
RATES = {"disclosure": 0.015, "waiver": 0.04}
SESSIONS, WAIVER_SESSIONS = 400, 100
CALL = {"verified": "none", "balance": 184.20, "isolated_path": True,
        "storm_area": True, "waived_in_12_months": False}
PROPOSALS = [
    ("take_payment", {"amount": 184.20}, {"verified": "none"}),
    ("read_bill", {}, {"verified": "pin"}),
    ("take_payment", {"amount": 180.42}, {"verified": "pin"}),
    ("take_payment", {"amount": 184.20}, {"verified": "pin"}),
    ("apply_waiver", {"amount": 12.00},
     {"verified": "pin", "storm_area": False}),
    ("take_payment", {"amount": 184.20},
     {"verified": "pin", "isolated_path": False})]
KEYED_MS, CARD_DIGITS = 8000, 16
TURN = {"in": 40, "eot": 200, "final": 40, "first_token": 170,
        "tool_call": 150, "first_audio": 85, "send": 10, "out": 45,
        "scheduler": 1_400}          # stand-ins from Chapters 6, 11, 14
WRONG = "We can waive your late fees."
LAG_MS = 300                             # the transcript trails the audio


def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"disclosure_variants": DISCLOSURE_VARIANTS,
                "waiver_variants": WAIVER_VARIANTS, "rates": RATES,
                "sessions": SESSIONS, "waiver_sessions": WAIVER_SESSIONS,
                "call": CALL, "proposals": PROPOSALS,
                "keyed_ms": KEYED_MS, "card_digits": CARD_DIGITS,
                "wrong": WRONG, "lag_ms": LAG_MS, "flow": FLOW,
                "turn": TURN}
    if mode == "fixture":
        return json.loads((FIXTURES / "s2s.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ------------------------------------------------------------ report


def exact_words(data: dict, seed: int = 18) -> dict:
    rng = random.Random(seed)
    out = {"disclosure": [], "waiver": []}
    for s in range(data["sessions"]):
        out["disclosure"].append(instructed(
            DISCLOSURE, data["disclosure_variants"],
            data["rates"]["disclosure"], rng))
        if s < data["waiver_sessions"]:
            out["waiver"].append(instructed(
                WAIVER, data["waiver_variants"], data["rates"]["waiver"],
                rng))
    return out


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"s2s lab, mode={mode}; evidence class: simulated")
    put("")
    said = exact_words(data)
    put(f"1. exact words: {data['sessions']} stand-in sessions "
        "(paraphrase rates are stand-ins)")
    put(f"   {'line':<22}{'instructed':>20}{'fixed path':>16}")
    for kind, line in (("disclosure", DISCLOSURE), ("waiver", WAIVER)):
        lines = said[kind]
        exact = sum(x == line for x in lines)
        label = "the disclosure" if kind == "disclosure" else \
            "the waiver's terms"
        put(f"   {label:<22}{exact:>9} of {len(lines)} exact"
            f"{len(lines):>8} of {len(lines)}")
    changed = [x for x in said["waiver"] if not terms_kept(x, "waiver")]
    for text in sorted(set(changed)):
        put(f"     terms lost: \"{text}\" ({changed.count(text)})")
    lost = [x for x in said["disclosure"]
            if not terms_kept(x, "disclosure")]
    put(f"     disclosures without \"automated\": {len(lost)}")
    put("")
    put("2. the policy layer, outside the speech model (a payment turn)")
    put(f"   {'the model proposes':<30}the policy layer decides")
    for action, args, state in data["proposals"]:
        call = dict(data["call"], **state)
        shown = f"{action}({args.get('amount', ''):.2f})" if args \
            else f"{action}()"
        put(f"   {shown:<30}{gate(action, args, call)}")
    put("")
    put(f"3. who hears the card: {data['keyed_ms'] // 1000} s of keypad "
        f"entry, {data['card_digits']} digits")
    for design in ("pure speech-to-speech", "the hybrid"):
        put(f"   {design}")
        for who, what in recipients(design, data["keyed_ms"],
                                    data["card_digits"]).items():
            put(f"     {who:<24}{what}")
    put("")
    lag = check_lag(data["wrong"], "fees", data["lag_ms"])
    put(f"4. checking sound after the fact: \"{data['wrong']}\"")
    put(f"   ({WORDS_PER_MIN} words a minute; the transcript trails the "
        f"audio by {data['lag_ms']} ms)")
    put(f"   the sentence ends at {lag['ends_ms']} ms; a check on the "
        f"transcript acts at {lag['acts_ms']} ms")
    put(f"   words heard before it can act: {lag['heard']} of "
        f"{lag['words']}")
    put("   on a fixed path the terms are checked before a word is played")
    put("")
    put("5. one dialogue object, two roads (the payment flow)")
    put(f"   {'step':<25}{'cascade':<22}speech-to-speech")
    for step, kind in data["flow"]:
        put(f"   {step:<25}{compile_step(kind, 'cascade'):<22}"
            f"{compile_step(kind, 's2s')}")
    put("")
    put("6. one call, end to end: the recurring caller's booking turn, "
        "stack only")
    put(f"   {'ms':>6}    {'layer':<12}event (* built in Part III)")
    events = booking_turn(data["turn"])
    for ms, layer, event, part3 in events:
        lines = textwrap.wrap(event, 52)
        put(f"   {ms:>6,}  {'*' if part3 else ' '} {layer:<12}{lines[0]}")
        for more in lines[1:]:
            put(f"   {'':>6}    {'':<12}{more}")
    heard = [ms for ms, _, e, _ in events if e == "the caller hears it"]
    put(f"   voice to voice {heard[0]:,} ms, inside the 800 ms wall; the "
        f"outcome at {heard[1]:,} ms")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("S2S_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"s2s_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "s2s.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/s2s.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("S2S_LAB_MODE", "mock")))
    else:
        run_mode()
