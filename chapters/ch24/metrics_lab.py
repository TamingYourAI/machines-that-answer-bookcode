"""Builders' Chapter 24 lab: metrics the business will accept.

Five steps:

  1. three recorded calls      both families from one metrics record per
                               call: latency at the caller and at the
                               server, word error rate and critical
                               entities, cut-offs; then containment, task
                               completion, resolution that lasts, and cost
  2. one week, three ways      the contact center's containment, a
                               spreadsheet joined by phone number, and the
                               metrics record, over the same calls
  3. every number split        task completion and resolution that lasts
                               by language, seat, and age band, each with
                               an interval
  4. Simpson's paradox         containment up for the week and down in
                               every flow, and the week at a fixed mix
  5. the case's lines          week 8 against the business case, and the
                               cost per resolved case with the desk in it,
                               beside what it assumes of the human path

Modes (select with METRICS_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Feed step 1 your own traces and step 2 a week
           of your own metrics records (evidence class: field).

  python3 metrics_lab.py                  run and print the report
  python3 metrics_lab.py --write-fixture  regenerate fixtures/
  python3 metrics_lab.py --check          compare with the frozen output

Evidence class: simulated. The calls, the weeks, and the costs are
stand-ins built to show the arithmetic, not estimates of any real rate.
"""
from __future__ import annotations

import json
import math
import os
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

AGENT_PER_MIN = 0.18   # the business case's assumed rate for the agent
PERSON_PER_MIN = 1.00  # a person's time, all in: six minutes is $6.00
WIDEST = 10.0          # points: a wider interval is too few calls to judge


# ------------------------------------------- 1. three recorded calls

def turn(said, heard, entities=(), server=0, caller=0, cut_off=False,
         interrupted=False):
    """One caller turn: the words said and the words the recognizer wrote,
    the critical entities in them (kind, said, heard), and the time from
    the end of the caller's speech to the agent's first audio, measured at
    the server and at the caller's ear."""
    return {"said": said, "heard": heard, "entities": [list(e) for e in
            entities], "server": server, "caller": caller,
            "cut_off": cut_off, "interrupted": interrupted}


CALLS = [
    {"id": "r1", "task": "a visit", "lang": "first", "seat": "phone",
     "turns": [
         turn("my meter's display has gone blank",
              "my meter's display has gone blank", (), 520, 700),
         turn("two two three one", "two two three one",
              [("account", "2231", "2231")], 480, 660),
         turn("yes that's right", "yes that's right",
              [("yes", "yes", "yes")], 410, 590),
         turn("yes fourteen alder road", "yes fourteen alder road",
              [("address", "14 Alder Road", "14 Alder Road")], 560, 750),
         turn("the lights are on", "the light are on", (), 470, 650),
         turn("tuesday at nine is fine", "tuesday at nine is fine",
              [("slot", "Tuesday 9:00", "Tuesday 9:00")], 540, 720),
         turn("yes go ahead", "yes go ahead", [("yes", "yes", "yes")],
              650, 840),
         turn("no that's all thanks", "no that's all thanks", (), 450,
              630)],
     "handed_over": False, "done_by": "agent", "again_days": None,
     "agent_min": 5.3, "person_min": 0.0, "again_min": 0.0},
    {"id": "r2", "task": "a bill", "lang": "first", "seat": "phone",
     "turns": [
         turn("why has my bill gone up", "why has my bill gone up", (),
              560, 740),
         turn("six one five two", "six one five two",
              [("account", "6152", "6152")], 500, 690),
         turn("it went up by fifty dollars",
              "it went up by fifteen dollars",
              [("amount", "50", "15")], 610, 800),
         turn("oh okay", "oh okay", (), 380, 560, interrupted=True),
         turn("and that's the estimated reading",
              "and that's the estimated reading", (), 700, 890),
         turn("fine", "fine", (), 420, 600)],
     "handed_over": False, "done_by": "agent", "again_days": 4,
     "agent_min": 4.1, "person_min": 0.0, "again_min": 7.4},
    {"id": "r3", "task": "a person", "lang": "first", "seat": "phone",
     "turns": [
         turn("a person please", "a person please", (), 450, 630),
         turn("it's about my bill it's six one",
              "it's about my bill it's six one", (), 300, 480,
              cut_off=True),
         turn("six one seven seven", "six one seven seven",
              [("account", "6177", "6177")], 530, 710),
         turn("yes please", "yes please", [("yes", "yes", "yes")], 480,
              660)],
     "handed_over": True, "done_by": "a person", "again_days": None,
     "agent_min": 1.6, "person_min": 7.2, "again_min": 0.0},
]


def word_errors(said: str, heard: str) -> tuple[int, int]:
    """Substitutions, deletions, and insertions between the words said and
    the words written, by edit distance; and the number of words said."""
    a, b = said.split(), heard.split()
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(b)], len(a)


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p percent
    of the values at or below it."""
    s = sorted(values)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


def voice_family(call: dict) -> dict:
    turns = call["turns"]
    errs = sum(word_errors(t["said"], t["heard"])[0] for t in turns)
    words = sum(word_errors(t["said"], t["heard"])[1] for t in turns)
    ents = [e for t in turns for e in t["entities"]]
    return {"turns": len(turns),
            "p50 caller": percentile([t["caller"] for t in turns], 50),
            "slowest caller": max(t["caller"] for t in turns),
            "wer": 100 * errs / words,
            "entities": len(ents),
            "entities wrong": sum(e[1] != e[2] for e in ents),
            "cut-offs": sum(t["cut_off"] for t in turns),
            "interruptions": sum(t["interrupted"] for t in turns)}


def business_family(call: dict) -> dict:
    """What the call achieved. Task completion counts only the agent's own
    work; a task a person finished after a transfer is the service's."""
    by_agent = call["done_by"] == "agent" and not call["handed_over"]
    return {"contained": not call["handed_over"],
            "completed by the agent": by_agent,
            "lasted": by_agent and call["again_days"] is None,
            "cost": round(AGENT_PER_MIN * call["agent_min"]
                          + PERSON_PER_MIN * (call["person_min"]
                                              + call["again_min"]), 2)}


# -------------------------------------- 2. and 3. one week of records

CELLS_WEEK_4 = [  # the pilot's fourth week, by cohort
    # language, age band, seat, calls, lasted, came back, unfinished,
    # handed over, lasted but a later unrelated call from the same number,
    # finished through a texted link
    ["first", "under 65", "phone", 1560, 560, 124, 330, 546, 51, 22],
    ["first", "under 65", "app", 380, 168, 26, 60, 126, 15, 14],
    ["first", "65 and over", "phone", 440, 118, 30, 118, 174, 11, 3],
    ["first", "65 and over", "app", 60, 24, 4, 12, 20, 2, 1],
    ["second", "under 65", "phone", 270, 64, 17, 78, 111, 6, 2],
    ["second", "under 65", "app", 60, 22, 5, 11, 22, 2, 1],
    ["second", "65 and over", "phone", 90, 20, 8, 30, 32, 2, 0],
    ["second", "65 and over", "app", 10, 3, 1, 4, 2, 0, 0],
]
MACHINE_CALLS_WEEK_4 = 14  # reported apart (Chapter 22)


def records(cells: list[list]) -> list[dict]:
    """Expand a week's counts into one metrics record per call, the shape
    both families write to."""
    out = []
    for lang, age, seat, n, lasted, back, unfinished, over, other, link in \
            cells:
        kinds = (["lasted"] * lasted + ["came back"] * back
                 + ["unfinished"] * unfinished + ["handed over"] * over)
        for i, kind in enumerate(kinds):
            out.append({
                "lang": lang, "age": age, "seat": seat,
                "handed_over": kind == "handed over",
                "done_by_agent": kind in ("lasted", "came back"),
                "same_task_again_7d": kind in ("came back", "unfinished"),
                "any_call_from_number_7d": kind != "lasted" or i < other,
                "by_link": kind in ("lasted", "came back") and i < link,
                "disposition": ("resolved" if kind in ("lasted", "came back")
                                else "transferred" if kind == "handed over"
                                else "caller hung up")})
    return out


def dashboard_containment(recs: list[dict]) -> float:
    """The contact center's number: calls not handed to a person."""
    return 100 * sum(not r["handed_over"] for r in recs) / len(recs)


def spreadsheet_resolved(recs: list[dict]) -> float:
    """The first spreadsheet: disposition resolved, and no call from the
    same phone number within seven days, whatever that call was about."""
    return 100 * sum(r["disposition"] == "resolved"
                     and not r["any_call_from_number_7d"]
                     for r in recs) / len(recs)


def business(recs: list[dict]) -> dict:
    """The business family from the metrics record: one row per call, the
    task checked in the system of record, repeats joined by account and
    task over seven days."""
    n = len(recs)
    done = [r for r in recs if r["done_by_agent"]]
    return {"calls": n,
            "containment": 100 * sum(not r["handed_over"] for r in recs) / n,
            "task completion": 100 * len(done) / n,
            "resolution that lasts": 100 * sum(
                not r["same_task_again_7d"] for r in done) / n,
            "contained, not done": 100 * sum(
                not r["handed_over"] and not r["done_by_agent"]
                for r in recs) / n,
            "by link": sum(r["by_link"] for r in recs)}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval for k successes in n trials."""
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (
        1 + z * z / n)
    return 100 * (centre - half), 100 * (centre + half)


def review(lo: float, hi: float, week: float) -> str:
    """A group's place in the weekly review. A group whose whole interval
    sits below the week's value is a gap and gets its own item. A group
    whose interval is wider than WIDEST points is too few to judge: it gets
    an item too, and its calls are sampled and heard. A low number with a
    wide interval is a question, never a pass."""
    if hi < week:
        return "own item"
    if hi - lo > WIDEST:
        return "too few"
    return ""


def split(recs: list[dict], field: str) -> list[tuple]:
    """Task completion and resolution that lasts for each group, with the
    interval on resolution that lasts and the group's place in the
    review."""
    week = business(recs)["resolution that lasts"]
    rows = []
    for value in sorted({r[field] for r in recs}):
        grp = [r for r in recs if r[field] == value]
        b = business(grp)
        k = sum(r["done_by_agent"] and not r["same_task_again_7d"]
                for r in grp)
        lo, hi = wilson(k, len(grp))
        rows.append((value, len(grp), b["task completion"],
                     b["resolution that lasts"], lo, hi,
                     review(lo, hi, week)))
    return rows


# ---------------------------------------------- 4. Simpson's paradox

FLOWS = {  # calls, and calls the agent contained, by flow
    "week 5": {"billing": [1700, 1224], "visits": [1200, 648]},
    "week 6": {"billing": [2500, 1750], "visits": [800, 416]},
}


def containment_by_flow(weeks: dict) -> dict:
    out = {}
    for week, flows in weeks.items():
        n = sum(v[0] for v in flows.values())
        k = sum(v[1] for v in flows.values())
        out[week] = {"all": 100 * k / n, "mix": {f: v[0] / n for f, v in
                                                 flows.items()},
                     **{f: 100 * v[1] / v[0] for f, v in flows.items()}}
    return out


def at_fixed_mix(rates: dict, mix: dict) -> float:
    """A week's containment at another week's mix of flows: the rates
    move, the mix does not."""
    return sum(rates[f] * share for f, share in mix.items())


# ------------------------------------------------- 5. the case's lines

CASE = {  # leaders' volume, Chapter 4: planning value and failing line
    "resolution that lasts": (45.0, 30.0, "below"),
    "what a repeat call costs": (6.00, 9.00, "above"),
    "agent cost per call": (0.90, 1.50, "above"),
    "cost per resolved case": (4.20, None, None),
}

WEEK_8 = {"calls": 2900, "lasted": 1102, "came back": 174,
          "unfinished": 754, "handed over": 870,
          "back within 7 days": 734,   # the 174 and 560 of the unfinished
          # The stand-in's assumption: the desk's disposition said every
          # handover was resolved, and every repeat call closed its case.
          # In production both come from the disposition (Chapter 21) and
          # the system of record, case by case.
          "handovers resolved": 870, "repeats resolved": 734,
          "agent invoices": 3248.00,
          "minutes per handed-over call": 6.6,
          "minutes before the pilot": 6.0,
          "minutes per repeat call": 6.2,
          "review and tuning hours": 16, "rate per hour": 60.00,
          "groups": {  # calls, and calls that lasted, in the lowest groups
              "language: second": [450, 140],
              "age band: 65 and over": [610, 206]}}


def case_lines(w: dict) -> dict:
    """Week 8's measured values against the case, and the cost per resolved
    case: every cost the calls caused, divided by the cases the service
    resolved, by the agent or by a person. A handover or a repeat call
    counts only when it resolved the case; one that did not adds its cost
    and nothing to the count. A caller who gave up is a failure, never a
    resolved case."""
    agent = w["agent invoices"]
    over = PERSON_PER_MIN * w["minutes per handed-over call"] * \
        w["handed over"]
    again = PERSON_PER_MIN * w["minutes per repeat call"] * \
        w["back within 7 days"]
    upkeep = w["review and tuning hours"] * w["rate per hour"]
    cost = agent + over + again + upkeep
    resolved = w["lasted"] + w["handovers resolved"] + w["repeats resolved"]
    unresolved = (w["handed over"] + w["back within 7 days"]
                  - w["handovers resolved"] - w["repeats resolved"])
    gave_up = w["came back"] + w["unfinished"] - w["back within 7 days"]
    return {"resolution that lasts": 100 * w["lasted"] / w["calls"],
            "what a repeat call costs":
                PERSON_PER_MIN * w["minutes per repeat call"],
            "agent cost per call": agent / w["calls"],
            "cost per resolved case": cost / resolved,
            "parts": {"agent": agent, "handed over": over,
                      "repeat calls": again, "upkeep": upkeep,
                      "cost": cost, "resolved": resolved,
                      "unresolved": unresolved, "gave up": gave_up}}


def break_even(w: dict) -> int:
    """How many more handovers and repeats could end unresolved before a
    resolved case costs more than a person's call did before the pilot."""
    p = case_lines(w)["parts"]
    person = PERSON_PER_MIN * w["minutes before the pilot"]
    return math.ceil(p["resolved"] - p["cost"] / person)


def holds(name: str, value: float) -> str:
    plan, line, side = CASE[name]
    if line is None:
        return ""
    return "yes" if (value >= line if side == "below" else value <= line) \
        else "no"


# ------------------------------------------------------------ inputs

def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"calls": CALLS, "week_4": CELLS_WEEK_4,
                "machine_calls": MACHINE_CALLS_WEEK_4, "flows": FLOWS,
                "case": {k: list(v) for k, v in CASE.items()},
                "week_8": WEEK_8}
    if mode == "fixture":
        return json.loads((FIXTURES / "metrics.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# -------------------------------------------------------------- report

def block(put, lead: str, text: str, width: int = 78) -> None:
    """Print text after a lead, wrapped at the page width and aligned."""
    lines = textwrap.wrap(text, width - len(lead), break_on_hyphens=False)
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def yes(flag: bool) -> str:
    return "yes" if flag else "no"


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    put(f"metrics lab, mode={mode}; evidence class: simulated")
    put("")
    calls = data["calls"]
    put("1. three recorded calls, scored on both families")
    put(f"   {'':<30}" + "".join(f"{c['id'] + ', ' + c['task']:<14}"
                                for c in calls))
    v = [voice_family(c) for c in calls]
    b = [business_family(c) for c in calls]
    put("   voice family")
    rows = [("turns", [str(x["turns"]) for x in v]),
            ("voice to voice, p50 (ms)", [str(x["p50 caller"]) for x in v]),
            ("slowest turn (ms)", [str(x["slowest caller"]) for x in v]),
            ("word error rate", [f"{x['wer']:.1f} %" for x in v]),
            ("critical entities wrong",
             [f"{x['entities wrong']} of {x['entities']}" for x in v]),
            ("false cut-offs", [str(x["cut-offs"]) for x in v]),
            ("interruptions", [str(x["interruptions"]) for x in v])]
    rows_b = [("handed to a person", [yes(c["handed_over"]) for c in calls]),
              ("done in the record by",
               ["the agent" if c["done_by"] == "agent" else "a person"
                for c in calls]),
              ("same task again in 7 days",
               [f"yes, day {c['again_days']}" if c["again_days"] else "no"
                for c in calls]),
              ("cost, with any repeat call",
               [f"${x['cost']:.2f}" for x in b])]
    for label, vals in rows:
        put(f"     {label:<28}" + "".join(f"{x:<14}" for x in vals))
    put("   business family")
    for label, vals in rows_b:
        put(f"     {label:<28}" + "".join(f"{x:<14}" for x in vals))
    k = len(calls)
    block(put, "     ", f"containment {sum(x['contained'] for x in b)} of "
          f"{k}; task completion by the agent "
          f"{sum(x['completed by the agent'] for x in b)} of {k}; "
          f"resolution that lasts {sum(x['lasted'] for x in b)} of {k}")
    turns = [t for c in calls for t in c["turns"]]
    at_c = [t["caller"] for t in turns]
    at_s = [t["server"] for t in turns]
    head = f"all {len(turns)} turns, voice to voice (ms)"
    put(f"   {head:<32}{'p50':>5}{'p95':>7}{'mean':>7}")
    for label, xs in (("at the caller's ear", at_c),
                      ("at the server", at_s)):
        put(f"     {label:<30}{percentile(xs, 50):>5}{percentile(xs, 95):>7}"
            f"{sum(xs) / len(xs):>7.0f}")
    put("")
    recs = records(data["week_4"])
    week = business(recs)
    put(f"2. one week counted three ways (pilot week 4, {len(recs):,} "
        "stand-in calls)")
    put(f"   {'the contact center dashboard: not handed to a person':<60}"
        f"{dashboard_containment(recs):>6.1f} %")
    put(f"   {'a spreadsheet: resolved, no call from the number in 7 days':<60}"
        f"{spreadsheet_resolved(recs):>6.1f} %")
    put("   the metrics record: one row per call, one schema")
    for name in ("containment", "task completion", "resolution that lasts",
                 "contained, not done"):
        label = {"task completion": "task completion by the agent",
                 "resolution that lasts":
                     "resolution that lasts (account and task, 7 days)"
                 }.get(name, name)
        put(f"     {label:<58}{week[name]:>6.1f} %")
    other = sum(1 for r in recs if r["done_by_agent"]
                and not r["same_task_again_7d"]
                and r["any_call_from_number_7d"])
    block(put, "   ", f"the spreadsheet's gap: {other} lasting calls were "
          "followed by a call from the same number about something else. "
          f"Task completion includes {week['by link']} tasks finished "
          "through a texted link, credited to the call that sent it. "
          f"{data['machine_calls']} machine callers are reported apart.")
    put("")
    put("3. every number split (week 4; interval on resolution that lasts)")
    put(f"   {'group':<22}{'calls':>6}{'task done':>11}{'lasts':>8}"
        f"{'95% interval':>15}  review")
    for field, name in (("lang", "language"), ("seat", "seat"),
                        ("age", "age band")):
        for value, n, tc, rtl, lo, hi, flag in split(recs, field):
            label = f"{name}: {value}"
            put(f"   {label:<22}{n:>6,}{tc:>9.1f} %{rtl:>6.1f} %"
                f"{lo:>7.1f} to {hi:>4.1f}  {flag}")
    put(f"   {'the whole week':<22}{len(recs):>6,}"
        f"{week['task completion']:>9.1f} %"
        f"{week['resolution that lasts']:>6.1f} %")
    put("")
    cf = containment_by_flow(data["flows"])
    put("4. Simpson's paradox: containment by flow")
    put(f"   {'':<24}{'week 5':>10}{'week 6':>10}")
    for f in ("billing", "visits"):
        put(f"   {f:<24}{cf['week 5'][f]:>8.1f} %{cf['week 6'][f]:>8.1f} %")
    put(f"   {'every call':<24}{cf['week 5']['all']:>8.1f} %"
        f"{cf['week 6']['all']:>8.1f} %")
    fixed = at_fixed_mix({f: cf["week 6"][f] for f in ("billing", "visits")},
                         cf["week 5"]["mix"])
    put(f"   {'week 6 at week 5 mix':<24}{'':>10}{fixed:>8.1f} %")
    mix5 = 100 * cf["week 5"]["mix"]["billing"]
    mix6 = 100 * cf["week 6"]["mix"]["billing"]
    block(put, "   ", f"billing was {mix5:.0f} percent of calls in week 5 "
          f"and {mix6:.0f} percent in week 6, after a bill run; the agent "
          "contains billing calls more often, so the week rose while "
          "both flows fell")
    put("")
    w = data["week_8"]
    got = case_lines(w)
    put(f"5. week 8 against the business case ({w['calls']:,} stand-in "
        "calls)")
    put(f"   {'line':<27}{'planned':>9}{'the case fails':>18}"
        f"{'measured':>11}{'holds':>7}")
    case = data["case"]
    for name in ("resolution that lasts", "what a repeat call costs",
                 "agent cost per call", "cost per resolved case"):
        plan, line, side = case[name]
        pct = name == "resolution that lasts"
        fmt = (lambda x: f"{x:.1f} %") if pct else (lambda x: f"${x:.2f}")
        fails = f"{side} {fmt(line)}" if line is not None else "not a line"
        put(f"   {name:<27}{fmt(plan):>9}{fails:>18}{fmt(got[name]):>11}"
            f"{holds(name, got[name]):>7}")
    p = got["parts"]
    block(put, "     ", f"agent ${p['agent']:,.0f}; people on "
          f"{w['handed over']:,} handed-over calls ${p['handed over']:,.0f}"
          f" ({w['minutes per handed-over call']} minutes each, "
          f"{w['minutes before the pilot']} before the pilot); people on "
          f"{w['back within 7 days']:,} repeat calls "
          f"${p['repeat calls']:,.0f}; review and tuning ${p['upkeep']:,.0f};"
          f" {p['resolved']:,} cases resolved; {p['gave up']:,} callers "
          "gave up and are not counted as resolved")
    human = w["handed over"] + w["back within 7 days"]
    person = PERSON_PER_MIN * w["minutes before the pilot"]
    more = break_even(w)
    if more <= 0:
        note = "a resolved case already costs more than a person's call"
    elif p["unresolved"]:
        note = (f"{p['unresolved']:,} of the {human:,} handovers and "
                f"repeats ended unresolved; if {more:,} more had, a resolved "
                f"case would cost more than a person's ${person:.2f} call")
    else:
        note = (f"the stand-in assumes every handover and repeat ended "
                f"resolved; if {more:,} of those {human:,} cases "
                f"({100 * more / human:.1f} %) had not, a resolved case "
                f"would cost more than a person's ${person:.2f} call")
    block(put, "     ", note)
    name, (n, k) = min(w["groups"].items(),
                       key=lambda kv: kv[1][1] / kv[1][0])
    lo, hi = wilson(k, n)
    flag = review(lo, hi, got["resolution that lasts"])
    flag = f", {flag}" if flag else ""
    put(f"   lowest group: {name}, {100 * k / n:.1f} % of {n} "
        f"({lo:.1f} to {hi:.1f}){flag}")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("METRICS_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"metrics_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "metrics.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/metrics.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("METRICS_LAB_MODE", "mock")))
    else:
        run_mode()
