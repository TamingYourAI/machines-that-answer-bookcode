"""Builders' Chapter 25 lab: testing voice agents.

A small pyramid on the Service Line, in five steps:

  1. unit tests on the policy layer  eight cases, run on every change
  2. one booking in text             asserted on wording, and on state and
                                     tool calls, against three versions
  3. simulated callers               a polite caller and a realistic one,
                                     the same twenty calls for each version
  4. what twenty runs can prove      intervals, the bound when nothing
                                     failed, and the runs a claim needs
  5. what runs when                  each layer's size, time, and cost

Modes (select with TESTING_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Point step 3's callers at your own agent over
           a test number (evidence class: live laboratory).

  python3 testing_lab.py                  run and print the report
  python3 testing_lab.py --write-fixture  regenerate fixtures/
  python3 testing_lab.py --check          compare with the frozen output

Evidence class: simulated. The agent, the callers, the noise, and the
costs are stand-ins; the callers' habits are working values.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ------------------------------------------ 1. unit tests on the gate

LADDER = ["none", "pin", "pin and code"]
FLOWS = {"visit": {"find_slot", "book_visit", "waive_callout"},
         "billing": {"read_bill", "apply_waiver"},
         "address": {"change_address"}}
TOOLS = {  # the proof it needs, whether it writes, its rung
    "find_slot": ("none", False, "answers"),
    "read_bill": ("pin", False, "answers"),
    "book_visit": ("pin", True, "a yes"),
    "apply_waiver": ("pin", True, "a yes"),
    "waive_callout": ("pin", True, "a person decides"),
    "change_address": ("pin and code", True, "a yes")}
MATERIAL = {"book_visit": {"slot", "address", "fee"},
            "change_address": {"address"}}


def gate(tool: str, flow: str, proof: str, heard=(), meter_days=None) -> str:
    """The policy layer's checks, in order: offered in the live flow, the
    caller's proof, the rules, the rung, and a yes that covers the terms."""
    if tool not in FLOWS.get(flow, set()):
        return "refused: not in this flow"
    need, writes, rung = TOOLS[tool]
    if LADDER.index(proof) < LADDER.index(need):
        return f"refused: needs {need}"
    if tool == "waive_callout" and (meter_days or 999) > 30:
        return "refused: meter not new (5a)"
    if rung == "a person decides":
        return "wait: a person decides"
    missing = MATERIAL.get(tool, set()) - set(heard) if writes else set()
    if missing:
        return "refused: " + ", ".join(sorted(missing)) + " not heard"
    return "allowed"


TERMS = ["slot", "address", "fee"]
UNIT_CASES = [  # a name, the call to the gate, the expected answer
    ["a booking with every term heard",
     {"tool": "book_visit", "flow": "visit", "proof": "pin",
      "heard": TERMS}, "allowed"],
    ["a booking in the billing flow",
     {"tool": "book_visit", "flow": "billing", "proof": "pin",
      "heard": TERMS}, "refused: not in this flow"],
    ["a booking before the PIN",
     {"tool": "book_visit", "flow": "visit", "proof": "none",
      "heard": TERMS}, "refused: needs pin"],
    ["a yes that never heard the fee",
     {"tool": "book_visit", "flow": "visit", "proof": "pin",
      "heard": ["slot", "address"]}, "refused: fee not heard"],
    ["a fee waiver, meter 425 days old",
     {"tool": "waive_callout", "flow": "visit", "proof": "pin",
      "meter_days": 425}, "refused: meter not new (5a)"],
    ["a fee waiver, meter 12 days old",
     {"tool": "waive_callout", "flow": "visit", "proof": "pin",
      "meter_days": 12}, "wait: a person decides"],
    ["an address change on a PIN alone",
     {"tool": "change_address", "flow": "address", "proof": "pin",
      "heard": ["address"]}, "refused: needs pin and code"],
    ["reading a bill after the PIN",
     {"tool": "read_bill", "flow": "billing", "proof": "pin"}, "allowed"],
]


# ------------------------------------------- 2. one booking in text

FEE_LINE = "There's a forty-dollar call-out fee."


def agent_booking(version: str) -> dict:
    """One scripted booking by the recurring caller: what the agent said,
    what the tools did, and the state at the end. B and B2 read the fee
    before asking; C asks first and reads the fee after its own "booked"."""
    said, ops, heard = [], [], []
    if version == "B":
        said += ["Tuesday at nine is open.", FEE_LINE, "Shall I book it?"]
        heard += ["slot", "address", "fee"]
    elif version == "B2":
        said += ["I can do Tuesday at nine, with the forty-dollar call-out "
                 "fee. Book it?"]
        heard += ["slot", "address", "fee"]
    else:
        said += ["Tuesday at nine is open. Shall I book it?"]
        heard += ["slot", "address"]
    # the caller: "Yes, go ahead."
    result = gate("book_visit", "visit", "pin", heard)
    if result == "allowed":
        ops.append({"tool": "book_visit", "id": "op-7f3a",
                    "heard": heard})
    if version == "C":
        said += ["You're booked for Tuesday at nine.", FEE_LINE]
    else:
        said += ["You're booked for Tuesday at nine."]
    return {"said": said, "ops": ops, "gate": result}


def on_wording(run: dict) -> str:
    """The brittle test: the approved fee line appears, and so does
    "You're booked"."""
    ok = FEE_LINE in run["said"] and any("booked" in s for s in run["said"])
    return "pass" if ok else "fail"


def on_state(run: dict) -> str:
    """The test that matters: one booking, under one id, whose yes covered
    every term; and no "booked" without it."""
    ops = [o for o in run["ops"] if o["tool"] == "book_visit"]
    if len(ops) != 1:
        claimed = any("booked" in s for s in run["said"])
        what = "no booking" if not ops else f"{len(ops)} bookings"
        return f"fail: {what}" + (', said "booked"' if claimed else "")
    if ops[0]["id"] != "op-7f3a":
        return "fail: another operation id"
    if set(MATERIAL["book_visit"]) - set(ops[0]["heard"]):
        return "fail: the yes missed a term"
    return "pass"


# ----------------------------------------------- 3. simulated callers

WORDS = "zero one two three four five six seven eight nine".split()
ACCOUNT = "2231"
HABITS = {  # how callers say an account number (working values)
    "plain": lambda n: " ".join(WORDS[int(d)] for d in n),
    "halves": lambda n: " ".join(WORDS[int(d)] for d in n[:2]) + ", "
    + " ".join(WORDS[int(d)] for d in n[2:]),
    "corrected": lambda n: "two three, sorry, "
    + " ".join(WORDS[int(d)] for d in n),
    "restart": lambda n: "two two, um, "
    + " ".join(WORDS[int(d)] for d in n),
}
PERSONAS = {
    "polite": {"habits": {"plain": 1.0}, "noise": 0.0},
    "realistic": {"habits": {"plain": 0.60, "halves": 0.20,
                             "corrected": 0.10, "restart": 0.10},
                  "noise": 0.03},
}


def calls_for(persona: dict, n: int, seed: int) -> list[dict]:
    """The same n simulated calls, generated once, for every version: each
    a habit, the words said, and the words the recognizer wrote."""
    rng = random.Random(seed)
    out = []
    names = list(persona["habits"])
    weights = [persona["habits"][h] for h in names]
    for _ in range(n):
        habit = rng.choices(names, weights)[0]
        said = HABITS[habit](ACCOUNT)
        heard = []
        for w in said.replace(",", "").split():
            if w in WORDS and rng.random() < persona["noise"]:
                w = WORDS[(WORDS.index(w) + 1) % 10]
            heard.append(w)
        out.append({"habit": habit, "said": said, "heard": " ".join(heard)})
    return out


def digits(text: str) -> list[str]:
    return [str(WORDS.index(w)) for w in text.replace(",", "").split()
            if w in WORDS]


def version_a(heard: str) -> str:
    """Keeps the first four digits it hears."""
    return "".join(digits(heard)[:4])


def version_b(heard: str) -> str:
    """Takes the last complete number: what follows a correction or a
    restart, which is how people fix what they just said."""
    return "".join(digits(heard)[-4:])


def score(call: dict, version) -> str:
    """Pass when the agent gets the number the words carried. When the
    recognizer changed a digit, a read-back and one repair are the design,
    and that is counted as hearing, not here; asking the caller to repeat
    words the recognizer got right is this scenario's failure."""
    got = version(call["heard"])
    if got == ACCOUNT:
        return "pass"
    if version_b(call["heard"]) == ACCOUNT:
        return "fail: asked to repeat a number she said right"
    return "pass: misheard, one read-back repair"


# --------------------------------------------- 4. what runs can prove

def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval for k passes in n runs."""
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (
        1 + z * z / n)
    return 100 * max(0.0, centre - half), 100 * min(1.0, centre + half)


def zero_failure_bound(n: int, confidence: float = 0.95) -> float:
    """The highest failure rate still consistent with n clean runs: the
    exact one-sided bound, 1 - (1 - confidence) ** (1 / n)."""
    return 100 * (1 - (1 - confidence) ** (1 / n))


def runs_needed(rate: float, confidence: float = 0.95) -> int:
    """Clean runs needed before a failure rate above `rate` is unlikely."""
    return math.ceil(math.log(1 - confidence) / math.log(1 - rate))


# ------------------------------------------------- 5. what runs when

LAYERS = [  # name, tests, runs of each, minutes per run, $ a minute, when
    ["unit: tools, policy, formatters", 180, 1, 0.0, 0.0, "every change"],
    ["conversations in text", 200, 3, 0.5, 0.01, "every change"],
    ["simulated callers in audio", 200, 5, 3.0, 0.06, "nightly"],
    ["real phone lines", 40, 1, 4.0, 0.08, "weekly"],
    ["load and failure", 1, 1, 60.0 * 400, 0.006, "monthly"],
]
WORKERS = {"conversations in text": 20, "simulated callers in audio": 50,
           "real phone lines": 4,
           "load and failure": 400}


def layer_cost(tests, runs, minutes, rate) -> tuple[float, float]:
    """Machine minutes and dollars for one pass of a layer."""
    m = tests * runs * minutes
    return m, m * rate


# ------------------------------------------------------------ inputs

def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"unit_cases": UNIT_CASES,
                "calls": {name: calls_for(p, 20, seed)
                          for (name, p), seed in
                          zip(PERSONAS.items(), (25, 2025))},
                "layers": LAYERS, "workers": WORKERS}
    if mode == "fixture":
        return json.loads((FIXTURES / "testing.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    """Print text after a lead, wrapped at the page width and aligned."""
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def clock(minutes: float) -> str:
    if minutes < 1:
        return f"{minutes * 60:.0f} s"
    if minutes < 90:
        return f"{minutes:.0f} min"
    return f"{minutes / 60:.1f} h"


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"testing lab, mode={mode}; evidence class: simulated")
    put("")
    put("1. unit tests on the policy layer (no model, no audio, no network)")
    put(f"   {'case':<36}{'expected':<31}result")
    passed = 0
    for name, call, expected in data["unit_cases"]:
        got = gate(**call)
        ok = got == expected
        passed += ok
        put(f"   {name:<36}{expected:<31}{'pass' if ok else 'FAIL: ' + got}")
    put(f"   {passed} of {len(data['unit_cases'])} passed; run on every "
        "change")
    put("")
    put("2. one booking in text, asserted two ways")
    put(f"   {'version':<33}{'wording':<11}state and tools")
    for v, label in (("B", "B, the fee, then the question"),
                     ("B2", "B2, the same, reworded"),
                     ("C", "C, the question, then the fee")):
        run = agent_booking(v)
        put(f"   {label:<33}{on_wording(run):<11}{on_state(run)}")
    put("")
    put("3. simulated callers: the same 20 calls for each version "
        f"(account {ACCOUNT})")
    put(f"   {'caller':<11}{'habits in the 20 calls':<44}"
        f"{'A: first':<10}{'B: last'}")
    results = {}
    for persona, calls in data["calls"].items():
        counts: dict[str, int] = {}
        for c in calls:
            counts[c["habit"]] = counts.get(c["habit"], 0) + 1
        habits = ", ".join(f"{h} {counts[h]}" for h in HABITS if h in counts)
        a = [score(c, version_a) for c in calls]
        b = [score(c, version_b) for c in calls]
        ka = sum(r.startswith("pass") for r in a)
        kb = sum(r.startswith("pass") for r in b)
        results[persona] = (ka, kb, a, b)
        put(f"   {persona:<11}{habits:<44}{ka:>2} of 20  {kb:>2} of 20")
    ka, kb, a, b = results["realistic"]
    fails = sum(r.startswith("fail") for r in a)
    repairs = sum("repair" in r for r in b)
    block(put, "   ", f"A's {fails} failures: asked the caller to repeat a "
          "number she had said right. Misheard digits that a read-back "
          f"repaired: {repairs} of 20 for B, counted as hearing.")
    put("")
    put("4. what twenty runs can prove (95 percent)")
    put(f"   {'result':<38}{'pass rate':>10}{'interval':>20}")
    for label, k in ((f"A, realistic caller, {ka} of 20", ka),
                     (f"B, realistic caller, {kb} of 20", kb)):
        lo, hi = wilson(k, 20)
        put(f"   {label:<38}{100 * k / 20:>8.1f} %{lo:>11.1f} to {hi:>5.1f}")
    block(put, "   ", "with no failure in 20 runs, the failure rate can "
          f"still be up to {zero_failure_bound(20):.1f} percent")
    put(f"   clean runs needed to show a failure rate under 5 percent: "
        f"{runs_needed(0.05)}")
    put(f"   clean runs needed to show a failure rate under 1 percent: "
        f"{runs_needed(0.01)}")
    put("")
    put("5. what runs when (the Service Line's suite; stand-in rates)")
    put(f"   {'layer':<32}{'tests':>6}{'runs':>5}{'time':>9}{'cost':>8}"
        "  when")
    for name, tests, runs, minutes, rate, when in data["layers"]:
        m, cost = layer_cost(tests, runs, minutes, rate)
        wall = m / data["workers"].get(name, 1) if m else tests * 0.02 / 60
        put(f"   {name:<32}{tests:>6}{runs:>5}{clock(wall):>9}"
            f"{'$' + format(cost, ',.0f'):>8}  {when}")
    put(f"   {'people trying to break it':<32}{'':>6}{'':>5}{'2 days':>9}"
        f"{'staff':>8}  quarterly")
    block(put, "   ", "every release candidate also runs on the phone "
          "lines; load and failure, and the red team, run again before a "
          "release that changes what they test")
    name, tests, runs, minutes, rate, _ = data["layers"][2]
    m, cost = layer_cost(tests, 20, minutes, rate)
    block(put, "   ", f"every scenario 20 times in audio, every night: "
          f"{m:,.0f} minutes and ${cost:,.0f} a night, the kind of bill "
          "that stops a suite from running")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("TESTING_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"testing_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "testing.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/testing.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("TESTING_LAB_MODE", "mock")))
    else:
        run_mode()
