"""Builders' Chapter 1 lab: a call is a system, not a chat with a microphone.

Two small experiments:

  1. the voice-to-voice budget   a demo loop, a call-shaped loop, and a tuned call loop,
                                 each turn measured at three boundaries
  2. the ruler                   a stand-in log of twenty calls, scored on the voice family
                                 and the business family, never mixed

Modes (select with CALL_LAB_MODE or run(mode=...)):
  mock     stage timings generated from seeded random numbers (default; runs anywhere)
  fixture  stage timings and the call log loaded from fixtures/ (committed; same schema)
  live     not in this lab. The companion's Knowledge Line app writes the same stage
           timestamps for each turn of a real call; export them in the fixture schema and
           run in fixture mode to put your own calls on the same ruler.

Other entry points:
  python3 call_budget_lab.py                  run in the selected mode and print the report
  python3 call_budget_lab.py --write-fixture  regenerate fixtures/ from the mock seeds
  python3 call_budget_lab.py --check          compare with the frozen output in outputs/

Evidence class of every number printed: simulated. The stage timings are stand-in values chosen
to show the shape of a voice-to-voice budget; they are not measurements of any product, network,
or model. The call log is twenty invented calls. Chapter 24 measures your own.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_TURNS = HERE / "fixtures" / "turns.json"
FIXTURE_CALLS = HERE / "fixtures" / "call_log.json"
OUTPUTS = HERE / "outputs"

N_TURNS = 1000       # turns simulated per loop
TARGET_MS = 500      # the voice-to-voice target (a dated working value)
WALL_MS = 800        # the wall: past it, callers start to talk over the agent
TROUBLE_MS = 1000    # about one second of silence reads as trouble (Jefferson, 1989)

STAGES = ("net_in", "endpoint", "stt", "model", "tool", "tts", "net_out")
STAGE_NAMES = {
    "net_in": "network and carrier, in",
    "endpoint": "waiting to be sure the turn ended",
    "stt": "final transcript after the turn ends",
    "model": "model, to its first token",
    "tool": "a tool on the path",
    "tts": "synthesizer, to its first audio",
    "net_out": "network, carrier, and jitter buffer, out",
}
SIGMA = {"net_in": 0.3, "endpoint": 0.35, "stt": 0.3, "model": 0.45, "tool": 0.5,
         "tts": 0.3, "net_out": 0.3}


@dataclass(frozen=True)
class Loop:
    """Median time of each stage (ms), and how often a turn calls a tool."""
    name: str
    seed: int
    medians: dict[str, float]
    p_tool: float
    filler: bool        # says a short line while a tool runs (Chapter 17)


LOOPS = (
    # a laptop on office Wi-Fi, a headset, a handpicked question, no tools
    Loop("demo loop", 11, dict(net_in=15, endpoint=200, stt=50, model=170, tool=0,
                               tts=80, net_out=25), 0.0, False),
    # a phone call through a carrier, 8 kHz audio, a full prompt, a tool on one turn in five
    Loop("call-shaped loop", 12, dict(net_in=50, endpoint=320, stt=90, model=300, tool=700,
                                      tts=130, net_out=80), 0.2, False),
    # the same call after the levers later chapters build (assumed values, not measured)
    Loop("tuned call loop", 13, dict(net_in=35, endpoint=160, stt=40, model=150, tool=700,
                                     tts=80, net_out=55), 0.2, True),
)
LEVERS = (
    ("end of turn", "semantic end-of-turn detection", 11),
    ("model", "a fast model on the turn, prompt caching", 15),
    ("model", "generation started before the turn is sure", 19),
    ("tool", "one short line while a tool runs", 17),
    ("network", "compute placed near the carrier", 19),
)


# ---------------------------------------------------------------- 1. the budget

@dataclass(frozen=True)
class Turn:
    net_in: float
    endpoint: float
    stt: float
    model: float
    tool: float
    tts: float
    net_out: float
    tool_hit: bool
    filler: bool

    @property
    def tool_on_path(self) -> float:
        """A tool delays the first audio unless the agent speaks while it runs."""
        return self.tool if self.tool_hit and not self.filler else 0.0


def boundaries(t: Turn) -> tuple[float, float, float]:
    """The same turn, measured three ways (ms)."""
    dashboard = t.model + t.tool_on_path + t.tts  # transcript to audio
    server = t.endpoint + t.stt + dashboard       # speech ended to audio sent
    caller = t.net_in + server + t.net_out        # at the caller's handset
    return dashboard, server, caller


def generate_turns(loop: Loop) -> list[list[float]]:
    rng = random.Random(loop.seed)
    rows = []
    for _ in range(N_TURNS):
        row = []
        for s in STAGES:
            med = loop.medians[s]
            row.append(round(rng.lognormvariate(math.log(med), SIGMA[s])) if med else 0)
        row.append(1 if rng.random() < loop.p_tool else 0)
        rows.append(row)
    return rows


def load_turns(mode: str) -> dict[str, list[Turn]]:
    if mode == "mock":
        raw = {lp.name: generate_turns(lp) for lp in LOOPS}
    elif mode == "fixture":
        raw = json.loads(FIXTURE_TURNS.read_text())
    else:
        raise SystemExit(f"mode {mode!r} is not available in this lab (see the header)")
    filler = {lp.name: lp.filler for lp in LOOPS}
    return {name: [Turn(*r[:7], tool_hit=bool(r[7]), filler=filler[name]) for r in rows]
            for name, rows in raw.items()}


def pct(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the value at or below which p percent of turns fall."""
    xs = sorted(values)
    k = max(1, math.ceil(p / 100 * len(xs)))
    return xs[k - 1]


def summarize(values: list[float]) -> dict[str, float]:
    return {"mean": sum(values) / len(values), "p50": pct(values, 50), "p95": pct(values, 95),
            "over wall": 100 * sum(v > WALL_MS for v in values) / len(values)}


def experiment_budget(turns: dict[str, list[Turn]]) -> dict[str, dict[str, dict]]:
    out = {}
    for name, ts in turns.items():
        b = [boundaries(t) for t in ts]
        out[name] = {"the dashboard": summarize([x[0] for x in b]),
                     "the server": summarize([x[1] for x in b]),
                     "the caller": summarize([x[2] for x in b])}
    return out


# ---------------------------------------------------------------- 2. the ruler

def build_call_log() -> list[dict]:
    """Twenty invented calls to the Service Line, written out one by one."""
    log = []

    def add(n, handled, verified, spoken_done, repeat, survey, turns, cutoffs, silence):
        log.append({"call": f"c{n:02d}", "handled": handled, "verified": verified,
                    "spoken_done": spoken_done, "repeat_7d": repeat, "survey": survey,
                    "turns": turns, "false_cutoffs": cutoffs, "longest_silence_ms": silence})

    # the agent finished the task, the booking is in the system, nobody called back
    for n, survey, turns in ((1, 5, 9), (2, None, 11), (3, 4, 8), (4, None, 12),
                             (5, 5, 10), (6, None, 9), (7, 4, 14), (8, None, 10),
                             (9, 5, 7)):
        add(n, "agent", True, True, False, survey, turns, 0, 900)
    # done, but reversed: the caller phoned again within a week to change it back
    add(10, "agent", True, True, True, None, 13, 1, 1100)
    # the caller gave up in a repair loop and hung up: counted as contained
    add(11, "agent", False, False, True, None, 17, 3, 2600)
    add(12, "agent", False, False, True, None, 15, 2, 2200)
    add(13, "agent", False, False, False, None, 12, 1, 1900)
    # the agent said "you're booked"; the scheduler never recorded it
    add(14, "agent", False, True, True, None, 10, 0, 1400)
    # transferred to a person, who finished the task
    for n, survey in ((15, 4), (16, None), (17, 5), (18, None)):
        add(n, "person", True, False, False, survey, 9, 1, 1200)
    # transferred, then abandoned in the queue
    add(19, "abandoned", False, False, True, None, 8, 2, 2400)
    add(20, "abandoned", False, False, False, None, 6, 0, 1500)
    return log


def load_calls(mode: str) -> list[dict]:
    if mode == "mock":
        return build_call_log()
    return json.loads(FIXTURE_CALLS.read_text())


def voice_family(calls: list[dict]) -> dict[str, float]:
    turns = sum(c["turns"] for c in calls)
    return {"turns": turns,
            "false cut-offs per 100 turns": 100 * sum(c["false_cutoffs"] for c in calls) / turns,
            "calls with a silence over 2 s": sum(c["longest_silence_ms"] > 2000 for c in calls)}


def business_family(calls: list[dict]) -> dict[str, float]:
    n = len(calls)
    agent = [c for c in calls if c["handled"] == "agent"]
    done = [c for c in agent if c["verified"]]
    surveyed = [c for c in calls if c["survey"] is not None]
    unresolved = [c for c in calls if not c["verified"]]
    return {
        "containment": 100 * len(agent) / n,
        "task completion by the agent": 100 * len(done) / n,
        "resolution that lasts": 100 * sum(not c["repeat_7d"] for c in done) / n,
        "contained, task not done": 100 * (len(agent) - len(done)) / n,
        "said done, not done": sum(c["spoken_done"] and not c["verified"] for c in calls),
        "survey response rate": 100 * len(surveyed) / n,
        "survey mean (1 to 5)": sum(c["survey"] for c in surveyed) / len(surveyed),
        "surveys from unresolved calls": sum(c["survey"] is not None for c in unresolved),
    }


# ---------------------------------------------------------------- report

def report(mode: str) -> str:
    lines: list[str] = []
    say = lines.append
    turns = load_turns(mode)
    calls = load_calls(mode)
    say(f"call budget lab, mode={mode}; evidence class of every number: simulated")
    say("")
    say(f"1. the voice-to-voice budget ({N_TURNS:,} turns per loop; stand-in stage timings)")
    say(f"   {'loop':<18}{'measured at':<16}{'mean':>6}{'p50':>7}{'p95':>7}"
        f"{'over ' + str(WALL_MS) + ' ms':>14}")
    res = experiment_budget(turns)
    for name, by in res.items():
        for i, (where, m) in enumerate(by.items()):
            say(f"   {name if i == 0 else '':<18}{where:<16}{m['mean']:>6.0f}{m['p50']:>7.0f}"
                f"{m['p95']:>7.0f}{m['over wall']:>12.1f} %")
    say(f"   all times in ms; target {TARGET_MS}, wall {WALL_MS}, "
        f"trouble at about {TROUBLE_MS}")
    say("")
    call = next(lp for lp in LOOPS if lp.name == "call-shaped loop")
    say("   where the time goes: call-shaped loop, median of each stage (ms)")
    for s in STAGES:
        note = " (on 1 turn in 5)" if s == "tool" else ""
        say(f"   {STAGE_NAMES[s] + note:<46}{call.medians[s]:>6.0f}")
    say("")
    say("   levers in the tuned loop (assumed, not measured)")
    for part, lever, ch in LEVERS:
        say(f"   {part:<14}{lever:<46}Ch. {ch}")
    say("")
    say(f"2. the ruler: twenty stand-in calls to the Service Line")
    say("   voice family (how it sounds)")
    for k, v in voice_family(calls).items():
        cell = f"{v:.1f}" if isinstance(v, float) else f"{v}"
        say(f"   {k:<40}{cell:>10}")
    say("   business family (what it achieves)")
    for k, v in business_family(calls).items():
        if k in ("said done, not done", "surveys from unresolved calls"):
            cell = f"{v} call" + ("s" if v != 1 else "")
        elif k.startswith("survey mean"):
            cell = f"{v:.1f}"
        else:
            cell = f"{v:.1f} %"
        say(f"   {k:<40}{cell:>10}")
    say("")
    say("invariants (must hold on every run):")
    nested = all(d <= s <= c for ts in turns.values() for d, s, c in map(boundaries, ts))
    b = business_family(calls)
    inv = {
        "dashboard <= server <= caller, every turn": nested,
        "containment >= task completion by the agent":
            b["containment"] >= b["task completion by the agent"],
    }
    for k, ok in inv.items():
        say(f"   {k:<50}{'PASS' if ok else 'FAIL'}")
    say("regression band: invariants hold; other numbers identical to the frozen")
    say("output in fixture mode")
    return "\n".join(lines) + "\n"


def run(mode: str | None = None) -> str:
    mode = mode or os.environ.get("CALL_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"call_budget_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before re-freezing")
    return 1


def write_fixtures() -> None:
    FIXTURE_TURNS.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_TURNS.write_text(json.dumps({lp.name: generate_turns(lp) for lp in LOOPS},
                                        separators=(",", ":")))
    FIXTURE_CALLS.write_text(json.dumps(build_call_log(), indent=1))
    print(f"wrote {FIXTURE_TURNS.relative_to(HERE)} and {FIXTURE_CALLS.relative_to(HERE)}")


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        write_fixtures()
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("CALL_LAB_MODE", "mock")))
    else:
        run()
