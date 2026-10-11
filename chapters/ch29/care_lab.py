"""Builders' Chapter 29 lab: keeping it good.

The Service Line's upkeep, on stand-ins:

  1. the care calendar      every recurring task as data, with a cadence and
                            an owner; what is overdue, due, and coming up
  2. a release diff         two release manifests compared, the regression
                            runs each changed part triggers, and the result
  3. what expires           knowledge items and other things with end dates;
                            expiring loudly against expiring silently
  4. drift and limits       a month of daily numbers against a trailing
                            14-day baseline, which moved, when, and which
                            move the calendar already explains; and the
                            fixed limits that catch a slow slide
  5. cost drift             the agent's cost per call split by who billed
                            it, with an alarm when any part rises a tenth

Modes (select with CARE_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Feed step 4 your own daily numbers and limits,
           and step 5 your invoices by line (evidence class: field).

  python3 care_lab.py                  run and print the report
  python3 care_lab.py --write-fixture  regenerate fixtures/
  python3 care_lab.py --check          compare with the frozen output

Evidence class: simulated. Every number is a stand-in; the agent's $1.12 a
call is the pilot's week 8 (Chapter 24).
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ------------------------------------------------------ 1. the care calendar

CADENCE = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 91,
           "yearly": 365}

CALENDAR = [  # task, cadence, owner, days since last done
    ["dashboards, alerts, and failure triage", "daily", "engineer on call", 0],
    ["the weekly review; failures into the suite", "weekly",
     "product owner", 6],
    ["knowledge updates", "weekly", "product owner", 3],
    ["turn-taking check on recorded calls", "monthly", "engineering lead", 12],
    ["lexicon review", "monthly", "head of customer operations", 40],
    ["provider benchmark on the held-out set", "monthly", "engineering lead",
     20],
    ["cost review, split by who billed it", "monthly", "product owner", 31],
    ["failover drill", "monthly", "engineering lead", 47],
    ["full suite on the live release", "quarterly", "product owner", 60],
    ["fairness audit by language and age band", "quarterly",
     "product owner", 95],
    ["security review", "quarterly", "compliance lead", 80],
    ["re-read the voice brief", "quarterly", "head of customer operations",
     30],
    ["architecture review: is the first fork still right?", "yearly",
     "engineering lead", 200],
    ["contract renewal, priced on the busiest month", "yearly",
     "procurement", 330],
    ["restore from backup, end to end", "yearly", "engineering lead", 370],
]


def due(calendar: list[list], window: int = 45) -> dict:
    """Days until each task is due; negative means overdue."""
    out = {"overdue": [], "due": [], "coming": []}
    for task, cadence, owner, since in calendar:
        left = CADENCE[cadence] - since
        if left < 0:
            out["overdue"].append((task, owner, -left))
        elif left <= 7:
            out["due"].append((task, owner, left))
        elif left <= window:
            out["coming"].append((task, owner, left))
    for k in out:
        out[k].sort(key=lambda r: -r[2] if k == "overdue" else r[2])
    return out


# ---------------------------------------------------- 4. drift and limits

NOISE = [0.10, -0.10, 0.05, -0.05, 0.0, 0.08, -0.08]


def month() -> dict:
    """Thirty days of daily numbers. On day 18 the utility's carrier moved
    part of the line's calls to a route that compressed the audio twice,
    and account numbers began to be misheard; every version stayed pinned.
    The carrier moved the line back on the evening of day 19, after the
    alert. Resolution that lasts closes seven days after each call, so
    those two days' callers show on days 25 and 26. The bill run fills days
    24 to 26 with billing calls, as the calendar says it will. The voice to
    voice p95 creeps about 3.5 ms a day, a slide too slow for a trailing
    median to see."""
    days = range(1, 31)
    n = lambda d, scale: NOISE[d % 7] * scale
    return {
        "entity errors, account numbers (%)":
            [round(2.0 + n(d, 1) + (3.8 if 18 <= d <= 19 else 0), 2)
             for d in days],
        "transfers after a repair (%)":
            [round(4.8 + n(d, 1) + (2.1 if 18 <= d <= 19 else 0), 2)
             for d in days],
        "resolution that lasts (%)":
            [round(38.0 + n(d, 3) - (2.4 if 25 <= d <= 26 else 0), 2)
             for d in days],
        "billing share of calls (%)":
            [round(58 + n(d, 10) + (16 if 24 <= d <= 26 else 0), 1)
             for d in days],
        "voice to voice p95 (ms)":
            [round(740 + 3.5 * (d - 1) + n(d, 100)) for d in days],
    }


KNOWN_EVENTS = [  # metric, first day, last day, why
    ["billing share of calls (%)", 24, 26, "the bill run"],
]

MIN_CHANGE = {  # the smallest change worth an alert, per metric
    "entity errors, account numbers (%)": 1.0,
    "transfers after a repair (%)": 1.0,
    "resolution that lasts (%)": 1.5,
    "billing share of calls (%)": 8.0,
    "voice to voice p95 (ms)": 60,
}


FIXED = {  # limits that never move with the data: the service level for the
          # wait (Chapter 1) and the case's line for resolution (Chapter 24)
    "voice to voice p95 (ms)": ["over", 800],
    "resolution that lasts (%)": ["under", 30.0],
}


def drift(series: dict, known: list[list], window: int = 14) -> list[tuple]:
    """Compare each day with the median of the 14 days before it. A metric
    alerts on the second day in a row that it sits further from that
    median than both four robust spreads and its minimum change. A move
    inside a known event on the calendar is reported, not alerted."""
    rows = []
    for metric, values in series.items():
        first, streak = None, 0
        for i in range(window, len(values)):
            past = values[i - window:i]
            base = statistics.median(past)
            spread = 1.4826 * statistics.median([abs(v - base) for v in past])
            far = abs(values[i] - base) > max(4 * spread, MIN_CHANGE[metric])
            streak = streak + 1 if far else 0
            if streak == 2:
                first = (i + 1, base, values[i])
                break
        why = ""
        if first:
            for m, a, b, reason in known:
                if m == metric and a <= first[0] <= b:
                    why = f"expected: {reason}, days {a} to {b}"
        rows.append((metric, first, why))
    return rows


def limits(series: dict, fixed: dict) -> list[tuple]:
    """The first day each fixed limit was breached two days running, or
    None. A fixed limit catches the slide a trailing median moves with."""
    rows = []
    for metric, (side, bound) in fixed.items():
        first, streak = None, 0
        for day, v in enumerate(series[metric], 1):
            out = v > bound if side == "over" else v < bound
            streak = streak + 1 if out else 0
            if streak == 2:
                first = day
                break
        rows.append((metric, side, bound, first))
    return rows


# ---------------------------------------------------------- 3. what expires

EXPIRING = [  # item, owner, days until it ends (negative: already ended)
    ["knowledge: storm late-fee waiver, memo 114", "billing policy lead", -1],
    ["knowledge: Saturday walk-in hours", "head of customer operations", 3],
    ["knowledge: outage map link text", "communications lead", 5],
    ["knowledge: winter reconnection rules", "billing policy lead", 40],
    ["certificate: the webhook endpoint", "engineering lead", 21],
    ["contract: the service number with the carrier", "procurement", 60],
    ["knowledge: the $40 call-out fee", "field operations manager", 200],
]


def expire(items: list[list], loud: bool, warn: int = 30) -> list[tuple]:
    """Loud expiry pulls an ended knowledge item from the index and pages
    its owner, and warns ahead of every end date. Silent expiry does
    neither: the item keeps answering."""
    out = []
    for item, owner, left in items:
        if left < 0:
            action = ("pulled from the index; owner paged" if loud and
                      item.startswith("knowledge") else
                      "owner paged" if loud else "still live, nobody told")
        elif left <= warn:
            action = "owner reminded" if loud else "no one"
        else:
            action = ""
        if action:
            out.append((item, owner, left, action))
    return out


# ------------------------------------------------------ 2. a release diff

RELEASE_35 = {"instructions (core)": "1.4", "voice brief": "1.3",
              "billing procedure": "2.2", "fixed lines": "3.2",
              "knowledge": "k-123", "turn-taking rules": "v2.4",
              "model": "m-12", "recognizer": "r-2.8", "voice": "B 4.1",
              "tools": "t-19"}
RELEASE_36 = dict(RELEASE_35, knowledge="k-124", recognizer="r-2.9")

RUNS = {  # a changed part, and the runs it triggers
    "recognizer": ["entity scenarios", "audio suite (5 runs of each)",
                   "40 calls on test numbers"],
    "knowledge": ["knowledge scenarios", "cross-chapter scenarios"],
    "model": ["the whole suite"],
    "voice": ["listening panel", "audio suite (5 runs of each)"],
    "fixed lines": ["listening panel", "40 calls on test numbers"],
    "turn-taking rules": ["turn-taking scenarios", "audio suite (5 runs of each)"],
}

RESULTS = {  # run: (passed on the old release, passed on the new, total)
    "entity scenarios": (48, 44, 48),
    "audio suite (5 runs of each)": (996, 991, 1000),
    "40 calls on test numbers": (40, 39, 40),
    "knowledge scenarios": (62, 62, 62),
    "cross-chapter scenarios": (4, 4, 4),
}


def diff(old: dict, new: dict) -> list[tuple]:
    return [(k, old[k], new[k]) for k in old if old[k] != new[k]]


def runs_for(changes: list[tuple]) -> list[str]:
    out = []
    for part, _, _ in changes:
        for r in RUNS.get(part, ["the whole suite"]):
            if r not in out:
                out.append(r)
    return out


# ---------------------------------------------------------- 5. cost drift

COST = {  # the agent's cost per call, by who billed it, over three months
    "telephony": [0.14, 0.14, 0.14],
    "platform minutes": [0.38, 0.41, 0.45],
    "speech": [0.27, 0.27, 0.28],
    "model": [0.21, 0.24, 0.27],
    "tools and storage": [0.12, 0.12, 0.12],
}


def cost_alarms(cost: dict, rise: float = 0.10) -> list[tuple]:
    rows = []
    for part, (m1, m2, m3) in cost.items():
        change = (m3 - m1) / m1
        rows.append((part, m1, m2, m3, change, change > rise))
    return rows


# ------------------------------------------------------------ inputs

def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"calendar": CALENDAR, "old": RELEASE_35,
                "new": RELEASE_36, "results": RESULTS,
                "expiring": EXPIRING, "month": month(),
                "known": KNOWN_EVENTS, "fixed": FIXED, "cost": COST}
    if mode == "fixture":
        return json.loads((FIXTURES / "care.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"care lab, mode={mode}; evidence class: simulated")
    put("")
    d = due(data["calendar"])
    put(f"1. the care calendar: {len(data['calendar'])} recurring tasks, "
        "each with an owner")
    plural = lambda n: f"{n} day" + ("" if n == 1 else "s")
    for label, key, fmt in (("overdue", "overdue", "{} late"),
                            ("due this week", "due", "in {}"),
                            ("coming up", "coming", "in {}")):
        put(f"   {label}:")
        for task, owner, days in d[key]:
            block(put, "     ", f"{task} ({owner}), "
                  f"{fmt.format(plural(days))}")
    put("")
    changes = diff(data["old"], data["new"])
    put("2. a release diff: release 35 to release 36")
    for part, a, b in changes:
        put(f"   {part}: {a} to {b}")
    put(f"   {'runs it triggers':<32}{'release 35':>14}{'release 36':>14}")
    failed = []
    for r in runs_for(changes):
        old, new, total = data["results"][r]
        put(f"   {r:<32}{f'{old:,} of {total:,}':>14}"
            f"{f'{new:,} of {total:,}':>14}")
        if new < old:
            failed.append(r)
    block(put, "   ", f"worse on release 36: {', '.join(failed)}. Hold r-2.9, "
          "ship k-124 on r-2.8, and send the provider the failing calls")
    put("")
    put("3. what expires: loud against silent")
    for item, owner, left, action in expire(data["expiring"], loud=True):
        when = (f"ended {-left} day{'' if left == -1 else 's'} ago"
                if left < 0 else f"{left} days left")
        put(f"   {item} ({when})")
        put(f"      loud: {action}")
    ended = [i for i in expire(data["expiring"], loud=False) if i[2] < 0]
    name = ended[0][0].split(": ", 1)[1]
    block(put, "   ", f"silent expiry: the {name} is {ended[0][3]}")
    put("")
    put("4. drift: a month of daily numbers against a trailing 14-day median")
    put(f"   {'metric':<37}{'alert':>6}{'median':>9}{'value':>8}")
    for metric, first, why in drift(data["month"], data["known"]):
        if not first:
            put(f"   {metric:<37}{'none':>6}")
            continue
        day, base, value = first
        f1 = (lambda v: f"{v:.0f}") if "ms" in metric else (
            lambda v: f"{v:.1f}")
        put(f"   {metric:<37}{'day ' + str(day):>6}{f1(base):>9}"
            f"{f1(value):>8}")
        if why:
            put(f"   {'':<37}{why}")
    block(put, "   ", "every version in the spans is unchanged: from day 18 "
          "the misheard calls came through a carrier's new route, which "
          "compressed the audio twice, until the carrier moved the line back "
          "on day 19")
    put(f"   {'fixed limits, two days running':<37}{'limit':>9}{'alert':>9}")
    for metric, side, bound, first in limits(data["month"], data["fixed"]):
        put(f"   {metric:<37}{side + ' ' + format(bound, 'g'):>9}"
            f"{('day ' + str(first)) if first else 'none':>9}")
    block(put, "   ", "the p95 crept about 3.5 ms a day; its trailing median "
          "moved with it, so only the fixed limit caught it")
    put("")
    put("5. cost drift: the agent's cost per call, by who billed it")
    put(f"   {'part':<20}{'month 1':>9}{'month 2':>9}{'month 3':>9}"
        f"{'change':>8}{'alarm':>7}")
    rows = cost_alarms(data["cost"])
    for part, m1, m2, m3, change, alarm in rows:
        mark = "yes" if alarm else ""
        put(f"   {part:<20}{m1:>9.2f}{m2:>9.2f}{m3:>9.2f}{change:>8.0%}"
            f"{mark:>7}")
    # math.fsum: the same exact total on every Python, since sum() over
    # floats changed in 3.12
    t1, t2, t3 = (math.fsum(r[i] for r in rows) for i in (1, 2, 3))
    put(f"   {'total':<20}{t1:>9.2f}{t2:>9.2f}{t3:>9.2f}"
        f"{(t3 - t1) / t1:>8.0%}")
    put("   the alarm: any part up more than a tenth on month 1")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("CARE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"care_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "care.json").write_text(json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/care.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("CARE_LAB_MODE", "mock")))
    else:
        run_mode()
