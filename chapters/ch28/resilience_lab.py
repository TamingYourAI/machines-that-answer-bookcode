"""Builders' Chapter 28 lab: keep it up.

Capacity, failure, and recovery on the Service Line, with stand-ins:

  1. one capacity model      every limit on the call path at a storm peak,
                             the human desk included, and which one binds
  2. fail over mid-call      the recognizer or the model fails during a call;
                             failover for the next call only, or mid-call,
                             and what the caller would notice
  3. four failure classes    a provider swap, a worker restart, a speech
                             session rebuilt, a region lost: what each costs
                             the caller, and whether the call survives
  4. nothing done twice      the Disruption Desk's drill: a rebooking
                             commits, its answer is lost, and the region is
                             lost; copies behind, the journal in both
                             regions, and a fence
  5. the drill               the primary recognizer cut at 10:00; which alarm
                             fires, and how many callers meet a deaf agent
  6. the degradation ladder  rungs agreed in advance, and the rung a storm
                             evening's signals put the line on

Modes (select with RESILIENCE_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     not in this lab. Feed step 1 your own limits and a peak hour,
           and step 4 your own drill's signals (evidence class: field).

  python3 resilience_lab.py                  run and print the report
  python3 resilience_lab.py --write-fixture  regenerate fixtures/
  python3 resilience_lab.py --check          compare with the frozen output

Evidence class: simulated. Limits, timings, and signals are stand-ins; the
700 ms holding line, the 2 s handoff, and the counters that act at two are
the Service Line's working values (Chapters 15 and 18). Step 4's counts are
the Disruption Desk's stand-ins.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"


# ------------------------------------------------- 1. one capacity model

PEAK = {  # a storm evening's busiest half hour
    "calls_per_min": 30.0,          # arriving at the agent
    "agent_minutes": 4.5,           # average length of an agent's call
    "turns_per_min": 4.0,           # model requests per call per minute
    "tool_calls_per_call": 3.0,     # reads and writes per call
    "asks_for_person_per_min": 6.5,
    "desk_answers_per_min": 5.0,
}

LIMITS = [  # layer, what limits it, the limit, and its unit
    ["carrier", "concurrent calls on the trunk", 400, "calls"],
    ["platform", "concurrent agent sessions", 300, "calls"],
    ["recognizer", "concurrent streams", 250, "calls"],
    ["model", "requests a minute", 1200, "per min"],
    ["tools", "billing requests a minute", 240, "per min"],
    ["desk", "calls answered a minute", 5.0, "per min"],
]


def loads(peak: dict) -> dict:
    """What the peak asks of each layer. Concurrency by Little's law:
    calls in progress = arrival rate x time in the system."""
    concurrent = peak["calls_per_min"] * peak["agent_minutes"]
    return {"carrier": concurrent, "platform": concurrent,
            "recognizer": concurrent,
            "model": concurrent * peak["turns_per_min"],
            "tools": peak["calls_per_min"] * peak["tool_calls_per_call"],
            "desk": peak["asks_for_person_per_min"]}


def binding(peak: dict, limits: list[list]) -> list[tuple]:
    need = loads(peak)
    rows = [(layer, what, limit, unit, need[layer], need[layer] / limit)
            for layer, what, limit, unit in limits]
    return rows


# ---------------------------------------- 2. fail over mid-call, or next call

HOLD_MS = 700          # the holding line, "One moment." (Chapter 15)
HANDOFF_MS = 2000      # nothing by 2 s: a person with context
COUNTER_ACTS_AT = 2    # repairs of one kind before the agent hands over

CALL = [  # the caller's turns on a visit booking: words, seconds of speech
    ["my meter's display has gone blank", 2.4],
    ["two two, three one", 2.0],
    ["yes, that's the address", 1.6],
    ["tuesday doesn't work for me", 1.8],
    ["wednesday at nine is fine", 1.7],
    ["yes, book it", 0.9],
]
FAIL_AT = 3            # the part fails during the fourth turn

RECOGNIZER = {"detect_s": 0.8, "reconnect_s": 0.3, "buffer_s": 3.0}
MODEL = {"fallback_answer_s": 1.6, "fallback_slower_s": 0.3}


def recognizer_fails(call: list[list], mid_call: bool) -> dict:
    """The recognizer's stream dies during a turn. For the next call only:
    this call's transcripts come back empty, the repair counter reaches
    two, and a person takes the call. Mid-call: empty finals with voice
    present are detected, a warm stream to the second recognizer opens,
    and the orchestrator replays its audio buffer, so no words are lost if
    the turn fits in the buffer."""
    words, seconds = call[FAIL_AT]
    if not mid_call:
        repairs = COUNTER_ACTS_AT
        times = {1: "once", 2: "twice"}.get(repairs, f"{repairs} times")
        return {"hears": f"\"Sorry, I didn't catch that\" {times}, then a "
                "person", "extra_s": None, "repairs": repairs,
                "outcome": "handed over; the booking left to a person"}
    lost = max(0.0, seconds - RECOGNIZER["buffer_s"])
    extra = RECOGNIZER["detect_s"] + RECOGNIZER["reconnect_s"]
    return {"hears": f"one slower answer, {extra:.1f} s longer",
            "extra_s": extra, "repairs": 1 if lost else 0,
            "outcome": "booked by the agent; nothing to repeat"
            if not lost else "booked by the agent after one repeat"}


def model_fails(call: list[list], mid_call: bool) -> dict:
    """The model stops answering during a turn. For the next call only:
    the holding line plays at 700 ms, nothing answers by 2 s, and a person
    takes the call with its context. Mid-call: the same request goes to
    the fallback model at 700 ms, and the rest of the call runs there."""
    if not mid_call:
        return {"hears": "\"One moment.\", then a person",
                "extra_s": HANDOFF_MS / 1000, "repairs": 0,
                "outcome": "handed over; the booking left to a person"}
    turns_left = len(call) - FAIL_AT - 1
    extra = MODEL["fallback_answer_s"] + MODEL["fallback_slower_s"] * turns_left
    return {"hears": "\"One moment.\" once; later answers a little slower",
            "extra_s": round(extra, 1), "repairs": 0,
            "outcome": "booked by the agent"}


# ------------------------------------------------- 3. four failure classes

CLASSES = [  # name, dead air (s), what is lost, and whether the call lives
    {"name": "a provider swapped for the next call", "dead_air": 0.0,
     "lost": "nothing for new calls; calls in progress keep the old one",
     "survives": True},
    {"name": "a worker restarted mid-call", "dead_air": 1.8,
     "lost": "nothing, if the state was saved before the turn",
     "survives": True},
    {"name": "a speech session rebuilt mid-call", "dead_air": 2.5,
     "lost": "the audio context: the caller repeats the last answer",
     "survives": True},
    {"name": "a carrier or a region lost", "dead_air": None,
     "lost": "the call itself; a verified callback follows, with the "
             "operations in flight reconciled first",
     "survives": False},
]


# ---------------------------------------------- 4. nothing done twice

TAKEOVER = {  # the Disruption Desk's drill before the season: the eastern
              # region's border controllers cut at the peak, its workers
              # still running, as when only the media edge fails
    "copy_behind_s": 4,      # the west's copies of the case store
    # the rebookings that left the east in those 4 s: committed in the
    # airline's system before the cut, or never arrived
    "rebookings": ["committed"] * 7 + ["lost"] * 2,
    "changed_flight": 1,     # of the lost, passengers who choose another
                             # flight when the west calls them back
}

DESIGNS = [  # the design's name on two lines, the journal written in both
             # regions before a request leaves, and a fencing token
    ["copies", "behind", False, False],
    ["journal", "in both", True, False],
    ["journal in", "both, fenced", True, True],
]


def takeover(t: dict, journal_both: bool, fence: bool) -> dict:
    """The west takes the east's cases and calls each passenger back. It
    knows a rebooking only if its journal entry reached the west before the
    request left. A known rebooking is read back by id and its outcome said
    first; a lost one is offered again under its first id, unless the
    passenger chooses another flight. An unknown one is offered as new, so
    a yes is a second operation. The east's workers, still running, resend
    every rebooking they read back as absent, under its first id, unless a
    fence refuses them. Each rebooking's entry in "each" says why it was
    booked twice, or is None."""
    known = 0
    each: list[str | None] = []
    changed = t["changed_flight"]
    for fate in t["rebookings"]:
        why = None
        if journal_both:
            known += 1
            if fate == "lost" and changed and not fence:
                why = "the east's resend"   # beside the flight the
                changed -= 1                # passenger chose instead
        elif fate == "committed":
            why = "a second yes"            # beside the first
        elif not fence:
            why = "the east's resend"       # beside the new one
        each.append(why)
    return {"known": known, "twice": sum(1 for w in each if w),
            "each": each}


# ------------------------------------------------------------ 5. the drill

DRILL = {  # the monthly drill: the primary recognizer cut at 10:00
    "start": "10:00", "new_calls_per_min": 12, "in_progress": 54,
    # per minute from the cut: error rate, timeout rate, empty transcripts
    "signals": [[0.4, 0.1, 96.0], [0.4, 0.2, 97.0], [0.5, 0.1, 97.0],
                [0.4, 0.1, 96.0], [0.4, 0.1, 97.0]],
    "baseline_empty": 3.0,
    "error_alarm": 2.0,          # percent of turns
    "empty_alarm": 20.0,         # percent of finals empty with voice present
    "human_minutes": 26,         # when someone noticed, with no empty alarm
}


def drill(d: dict) -> dict:
    """Which alarm fires first, and how many new callers met an agent that
    could not hear them before the second recognizer took new calls."""
    fired_error = next((m for m, (e, t, _) in enumerate(d["signals"], 1)
                        if e > d["error_alarm"] or t > d["error_alarm"]),
                       None)
    fired_empty = next((m for m, (_, _, x) in enumerate(d["signals"], 1)
                        if x > d["empty_alarm"]), None)
    with_alarm = (fired_empty or d["human_minutes"]) * d["new_calls_per_min"]
    without = d["human_minutes"] * d["new_calls_per_min"]
    return {"error_alarm_at": fired_error, "empty_alarm_at": fired_empty,
            "deaf_with_alarm": with_alarm, "deaf_without": without}


# -------------------------------------------------- 6. the degradation ladder

LADDER = [  # rung, what callers get, the trigger agreed in advance
    [0, "the full agent", "normal"],
    [1, "the fallback model; money on fixed lines",
     "model p95 over 1 s for 5 minutes"],
    [2, "spike mode: outage status first, callbacks in place of a queue",
     "desk wait over 10 minutes"],
    [3, "status lines only; everything else a callback",
     "model rate-limited in both regions"],
    [4, "the kill switch: the old menu and the queues",
     "empty transcripts over 20 percent, or a release-blocking failure"],
]

EVENING = [  # time, model p95 (ms), desk wait (min), both regions limited,
             # empty transcripts (percent)
    ["18:00", 720, 4, False, 3],
    ["18:30", 1150, 7, False, 3],
    ["19:00", 1180, 12, False, 4],
    ["19:30", 1300, 16, True, 4],
    ["20:00", 900, 13, False, 3],
    ["20:30", 760, 8, False, 3],
]


def rung(p95: int, desk_wait: float, limited: bool, empty: float) -> int:
    """The highest rung whose trigger holds. The 5-minute condition on the
    model's p95 is taken as met at a half-hour reading."""
    if empty > 20:
        return 4
    if limited:
        return 3
    if desk_wait > 10:
        return 2
    if p95 > 1000:
        return 1
    return 0


# ------------------------------------------------------------ inputs

def inputs(mode: str) -> dict:
    if mode == "mock":
        return {"peak": PEAK, "limits": LIMITS, "call": CALL,
                "classes": CLASSES, "takeover": TAKEOVER,
                "designs": DESIGNS, "drill": DRILL, "ladder": LADDER,
                "evening": EVENING}
    if mode == "fixture":
        return json.loads((FIXTURES / "resilience.json").read_text())
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
    put(f"resilience lab, mode={mode}; evidence class: simulated")
    put("")
    peak = data["peak"]
    put(f"1. one capacity model: a storm peak, {peak['calls_per_min']:g} "
        f"calls a minute at the agent")
    put(f"   {'layer':<12}{'limit':<34}{'needed':>8}{'used':>8}")
    rows = binding(peak, data["limits"])
    for layer, what, limit, unit, need, use in rows:
        lim = f"{what}: {limit:g}"
        mark = "  <- binds" if use > 1 else ""
        put(f"   {layer:<12}{lim:<34}{need:>8g}{use:>7.0%}{mark}")
    over = [r for r in rows if r[5] > 1]
    block(put, "   ", f"the desk binds: {peak['asks_for_person_per_min']:g} "
          f"callers a minute ask for a person and "
          f"{peak['desk_answers_per_min']:g} are answered, so past a "
          "10-minute wait the agent offers a callback that keeps the "
          "caller's place" if over and over[0][0] == "desk" else
          "no layer binds at this peak")
    put("")
    call = data["call"]
    put(f"2. a part fails during turn {FAIL_AT + 1}: failover for the next "
        "call, or mid-call")
    put(f"   the turn: \"{call[FAIL_AT][0]}\" ({call[FAIL_AT][1]:g} s of "
        "speech)")
    for part, fn in (("recognizer", recognizer_fails), ("model", model_fails)):
        for mid in (False, True):
            r = fn(call, mid)
            put(f"   {part}, {'mid-call' if mid else 'next call only'}")
            block(put, "      hears:   ", r["hears"])
            block(put, "      outcome: ", r["outcome"])
    put("")
    put("3. four failure classes: what the caller loses")
    for c in data["classes"]:
        air = ("the call drops" if c["dead_air"] is None
               else f"{c['dead_air']:.1f} s of dead air" if c["dead_air"]
               else "no dead air")
        put(f"   {c['name']}: {air}")
        block(put, "      ", c["lost"])
    put("")
    t = data["takeover"]
    lost = t["rebookings"].count("lost")
    done = t["rebookings"].count("committed")
    put("4. one failure: a rebooking commits, its answer is lost, the region "
        "is lost")
    block(put, "   ", "the Desk's drill: the east's border controllers cut at "
          "the peak, its workers still running; the west's copies of the "
          f"case store {t['copy_behind_s']} s behind")
    block(put, "   ", f"{len(t['rebookings'])} rebookings left the east in "
          f"those {t['copy_behind_s']} s: {done} committed, and {lost} never "
          "arrived")
    block(put, "   ", f"when the west called back, {t['changed_flight']} of "
          f"those {lost} passengers chose another flight")
    designs = data["designs"]
    rs = [takeover(t, jb, fe) for _, _, jb, fe in designs]
    for k in (0, 1):
        put(" " * 35 + "".join(f"{d[k]:<13}" for d in designs))
    put(f"   {'rebookings the west knew':<32}"
        + "".join(f"{r['known']} of {len(t['rebookings'])}".ljust(13)
                  for r in rs))
    put(f"   {'passengers booked twice':<32}"
        + "".join(f"{r['twice']:<13}" for r in rs))
    put("")
    d = data["drill"]
    r = drill(d)
    put(f"5. the drill: the primary recognizer cut at {d['start']}, "
        f"{d['in_progress']} calls in progress")
    put(f"   {'minute':<8}{'errors':>8}{'timeouts':>10}{'empty finals':>14}")
    for m, (e, t, x) in enumerate(d["signals"], 1):
        put(f"   {m:<8}{e:>7.1f}%{t:>9.1f}%{x:>13.0f}%")
    put(f"   error alarm (over {d['error_alarm']:g}%): "
        f"{'minute ' + str(r['error_alarm_at']) if r['error_alarm_at'] else 'never fired'}")
    block(put, "   ", f"empty-transcript alarm (over {d['empty_alarm']:g}%): "
          f"minute {r['empty_alarm_at']}; the second recognizer takes new "
          "calls")
    block(put, "   ", f"new callers who met an agent that could not hear: "
          f"{r['deaf_with_alarm']} with the empty alarm, "
          f"{r['deaf_without']} if the line waits for someone to notice "
          f"({d['human_minutes']} minutes); the {d['in_progress']} calls in "
          "progress fail over mid-call")
    put("")
    put("6. the degradation ladder, agreed in advance")
    for n, gets, trigger in data["ladder"]:
        block(put, f"   {n}  ", f"{gets} (when: {trigger})")
    put("   a storm evening:")
    put(f"   {'time':<8}{'model p95':>10}{'desk wait':>11}{'both limited':>14}"
        f"{'empty':>7}{'rung':>6}")
    for t, p95, wait, lim, empty in data["evening"]:
        put(f"   {t:<8}{p95:>7} ms{wait:>7} min{('yes' if lim else 'no'):>14}"
            f"{empty:>6}%{rung(p95, wait, lim, empty):>6}")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("RESILIENCE_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check_frozen(mode: str) -> int:
    frozen = (OUTPUTS / f"resilience_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "resilience.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/resilience.json")
    elif "--check" in sys.argv:
        sys.exit(check_frozen(os.environ.get("RESILIENCE_LAB_MODE", "mock")))
    else:
        run_mode()
