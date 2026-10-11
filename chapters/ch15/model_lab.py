"""Builders' Chapter 15 lab: choosing and running the model.

Six steps:

  1. time to first token  two stand-in models on the Service Line's prompt,
                          at three loads, with and without a cached prefix
  2. placement            voice to voice with each model on the caller's
                          turn, and the larger one behind it
  3. tool calls           pass^1 and pass^8 on twenty scenarios, and what
                          the policy layer and the read-back catch
  4. the canary           a model change against gates written first
  5. the fallback ladder  what callers hear in a storm hour when the model
                          is late, rate-limited, or refuses
  6. cost per call        a six-turn billing call, with and without a
                          cached prefix

Modes (select with MODEL_LAB_MODE or run_mode(mode=...)):
  mock     inputs built in this file (default)
  fixture  the same inputs loaded from fixtures/ (committed; same schema)
  live     step 1 on your own endpoint, any chat completions URL that
           streams: set MODEL_LAB_URL, MODEL_LAB_KEY, and MODEL_LAB_MODEL,
           and MODEL_LAB_PROMPT to a JSON file of your own messages. It
           times the first answer token (evidence class: live laboratory).

  python3 model_lab.py                  run and print the report
  python3 model_lab.py --write-fixture  regenerate fixtures/ from the data
  python3 model_lab.py --check          compare with the frozen output

Evidence class of every number printed in mock and fixture modes:
simulated. The two models, their timings, rates, and prices are stand-ins;
they describe no product.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import textwrap
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
OUTPUTS = HERE / "outputs"

OTHER_SPANS_MS = 440       # Chapter 6's turn, less the model's first token
WALL_MS = 800              # the p95 wall at the caller (Chapter 1)


def pct(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1)]


# ------------------------------------------- 1. time to first token


def ttft(m: dict, prompt: dict, cached: bool, queue_ms: float,
         rng: random.Random) -> float:
    """One request's time to its first answer token, in ms."""
    tokens = prompt["dynamic"] + (0 if cached else prompt["static"])
    work = m["base_ms"] + 1000 * tokens / m["prefill_tps"]
    wait = rng.expovariate(1 / queue_ms) if queue_ms else 0.0
    return work * rng.lognormvariate(0, m["sigma"]) + wait


def ttft_table(data: dict, seed: int = 15) -> dict:
    rng = random.Random(seed)
    out = {}
    for name, m in data["models"].items():
        for cached in (False, True):
            for load in data["loads"]:
                xs = [ttft(m, data["prompt"], cached, m["queue_ms"][load],
                           rng) for _ in range(data["requests"])]
                out[(name, cached, load)] = xs
    return out


def probe(url: str, key: str, model: str, messages: list[dict],
          n: int = 20, concurrency: int = 4) -> list[float]:
    """Time to the first answer token on your endpoint, in ms: stream the
    reply, and stop the clock at the first chunk of answer text."""
    body = json.dumps({"model": model, "stream": True,
                       "messages": messages}).encode()

    def one(_: int) -> float:
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=30) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:") or line.endswith("[DONE]"):
                    continue
                choices = json.loads(line[5:]).get("choices") or [{}]
                if choices[0].get("delta", {}).get("content"):
                    return (time.perf_counter() - t0) * 1000
        return float("nan")

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        return list(pool.map(one, range(n)))


# ------------------------------------------------------ 2. placement


def voice_to_voice(data: dict, model: str, load: str, seed: int) -> list:
    rng = random.Random(seed)
    m = data["models"][model]
    return [OTHER_SPANS_MS * rng.lognormvariate(0, 0.08)
            + ttft(m, data["prompt"], True, m["queue_ms"][load], rng)
            for _ in range(data["requests"])]


def summary_ready_s(data: dict) -> float:
    """The larger model writes the desk's summary after the hang-up."""
    m = data["models"]["large"]
    work = m["base_ms"] + 1000 * data["summary"]["in"] / m["prefill_tps"]
    return (work + 1000 * data["summary"]["out"] / m["out_tps"]) / 1000


# ------------------------------------------------------ 3. tool calls


def pass_k(data: dict, model: str, k: int = 8, seed: int = 8) -> dict:
    """pass^1 is the share of runs that succeed; pass^k is the share of
    scenarios that succeed in all k runs."""
    rng = random.Random(f"{seed}:{model}")
    runs, all_k, slipped = 0, 0, []
    for sc in data["scenarios"]:
        ok = [rng.random() < sc[model] for _ in range(k)]
        runs += sum(ok)
        all_k += all(ok)
        if not all(ok):
            slipped.append(sc)
    n = len(data["scenarios"])
    expected = sum(sc[model] ** k for sc in data["scenarios"]) / n
    return {"pass1": runs / (n * k), "passk": all_k / n,
            "expected": expected, "slipped": slipped}


# --------------------------------------------------------- 4. the canary


def canary(data: dict, pinned: dict, candidate: dict) -> list[tuple]:
    """Every gate is written before the canary starts; one failure stops
    it at its first share of calls."""
    g = data["gates"]
    rows = [("time to first token, p95", f"{pinned['ttft95']:.0f} ms",
             f"{candidate['ttft95']:.0f} ms",
             candidate["ttft95"] <= g["ttft95_ms"],
             f"over {g['ttft95_ms']}")]
    rows.append(("voice to voice, p95", f"{pinned['v2v95']:.0f} ms",
                 f"{candidate['v2v95']:.0f} ms",
                 candidate["v2v95"] <= WALL_MS, f"over {WALL_MS}"))
    rows.append(("tool calls, pass^8", f"{pinned['pass8']:.2f}",
                 f"{candidate['pass8']:.2f}",
                 candidate["pass8"] >= pinned["pass8"], "below pinned"))
    for lang in ("first", "second"):
        rows.append((f"billing answers, {lang} language",
                     f"{pinned['right'][lang]:.0%}",
                     f"{candidate['right'][lang]:.0%}",
                     candidate["right"][lang] >= pinned["right"][lang],
                     "below pinned"))
    rows.append(("legitimate requests refused",
                 f"{pinned['refused']:.1%}", f"{candidate['refused']:.1%}",
                 candidate["refused"] <= pinned["refused"], "above pinned"))
    return rows


# -------------------------------------------------- 5. the fallback ladder


def ladder(data: dict, seed: int = 5) -> dict:
    """A storm hour of turns, each through the ladder in order."""
    rng = random.Random(seed)
    lad, m = data["ladder"], data["models"]["small"]
    limited = lad["rate_limited_min"] / 60
    counts = {"answered": 0, "fallback": 0, "refused": 0, "person": 0}
    for _ in range(lad["turns"]):
        first = ttft(m, data["prompt"], True, m["queue_ms"]["storm"], rng)
        if rng.random() < lad["refusal_rate"]:
            counts["refused"] += 1
        elif rng.random() >= limited and first <= lad["hold_ms"]:
            counts["answered"] += 1
        elif lad["hold_ms"] + rng.expovariate(1 / lad["fallback_ms"]) \
                <= lad["person_ms"]:
            counts["fallback"] += 1
        else:
            counts["person"] += 1
    return counts


# ------------------------------------------------------ 6. cost per call


def call_cost(data: dict, model: str, cached: bool) -> dict:
    """A billing call's model cost: the context is sent again each turn."""
    c, p = data["call"], data["prices"][model]
    fresh = written = read = out = 0
    static = data["prompt"]["static"]
    for turn in range(c["turns"]):
        fresh += data["prompt"]["dynamic"] + c["history_per_turn"] * turn
        if not cached:
            fresh += static
        elif turn == 0:
            written += static      # the first call writes the cache
        else:
            read += static         # later turns read it
        out += c["out_per_turn"]
    dollars = (p["in"] * (fresh + written * c["write_factor"]
                          + read * c["read_factor"]) + out * p["out"]) / 1e6
    return {"input": fresh + written + read, "output": out,
            "dollars": dollars}


def summary_cost(data: dict) -> float:
    p = data["prices"]["large"]
    return (data["summary"]["in"] * p["in"]
            + data["summary"]["out"] * p["out"]) / 1e6


# ------------------------------------------------------------ inputs

MODELS = {  # stand-ins: a small fast model and a larger, slower one
    "small": {"base_ms": 150, "prefill_tps": 40000, "sigma": 0.2,
              "out_tps": 180,
              "queue_ms": {"quiet": 0, "evening": 40, "storm": 110}},
    "large": {"base_ms": 380, "prefill_tps": 12000, "sigma": 0.25,
              "out_tps": 70,
              "queue_ms": {"quiet": 0, "evening": 260, "storm": 700}}}
PROMPT = {"static": 3000, "dynamic": 400}   # tokens: prefix and the rest
LOADS = ["quiet", "evening", "storm"]
SCENARIOS = [  # success per run, stand-ins; who catches a slip
    {"name": "book on a yes that covers the terms", "small": 0.99,
     "large": 1.0, "caught": "the policy layer"},
    {"name": "no booking before the read-back", "small": 0.99,
     "large": 1.0, "caught": "the policy layer"},
    {"name": "read the bill after verifying", "small": 0.99, "large": 1.0,
     "caught": "the policy layer"},
    {"name": "a relative date, \"next Tuesday\"", "small": 0.9,
     "large": 0.97, "caught": "the read-back"},
    {"name": "two requests in one breath", "small": 0.93, "large": 0.96,
     "caught": "reaches the caller"},
    {"name": "an account read in two halves", "small": 0.96,
     "large": 0.99, "caught": "the read-back"},
    {"name": "the storm waiver, in the area", "small": 0.99,
     "large": 1.0, "caught": "the policy layer"},
    {"name": "the storm waiver, outside it", "small": 0.99, "large": 1.0,
     "caught": "the policy layer"},
    {"name": "an address change needs the code", "small": 0.99,
     "large": 1.0, "caught": "the policy layer"},
    {"name": "a change of mind after the yes", "small": 0.95,
     "large": 0.99, "caught": "the policy layer"},
    {"name": "an outage question first", "small": 0.99, "large": 1.0,
     "caught": "reaches the caller"},
    {"name": "a meter reading given unasked", "small": 0.97,
     "large": 0.99, "caught": "the read-back"},
    {"name": "\"agent\" said twice", "small": 0.99, "large": 1.0,
     "caught": "the policy layer"},
    {"name": "a fee question during booking", "small": 0.97,
     "large": 0.99, "caught": "reaches the caller"},
    {"name": "a slot that is no longer open", "small": 0.99,
     "large": 1.0, "caught": "the policy layer"},
    {"name": "a payment request", "small": 0.99, "large": 1.0,
     "caught": "the policy layer"},
    {"name": "a caller on the medical list", "small": 0.99,
     "large": 1.0, "caught": "the policy layer"},
    {"name": "Tuesday at one, not nine", "small": 0.96, "large": 0.99,
     "caught": "the read-back"},
    {"name": "a second-language caller", "small": 0.94, "large": 0.97,
     "caught": "the read-back"},
    {"name": "a caller who hangs up mid-booking", "small": 0.99,
     "large": 1.0, "caught": "the policy layer"}]
QUALITY = {  # billing answers right on 200 questions per language
    "small": {"right": {"first": 0.91, "second": 0.84}, "refused": 0.002},
    "large": {"right": {"first": 0.96, "second": 0.93}, "refused": 0.001}}
GATES = {"ttft95_ms": 400}
LADDER = {"turns": 6000, "rate_limited_min": 6, "hold_ms": 700,
          "fallback_ms": 400, "person_ms": 2000, "refusal_rate": 0.002}
PRICES = {  # stand-in dollars per million tokens
    "small": {"in": 0.40, "out": 1.60}, "large": {"in": 3.00, "out": 12.00}}
CALL = {"turns": 6, "history_per_turn": 120, "out_per_turn": 60,
        "write_factor": 1.25, "read_factor": 0.1}
SUMMARY = {"in": 2400, "out": 250}


def inputs(mode: str) -> dict:
    if mode in ("mock", "live"):
        return {"models": MODELS, "prompt": PROMPT, "loads": LOADS,
                "requests": 400, "scenarios": SCENARIOS, "quality": QUALITY,
                "gates": GATES, "ladder": LADDER, "prices": PRICES,
                "call": CALL, "summary": SUMMARY, "case_per_call": 0.90}
    if mode == "fixture":
        return json.loads((FIXTURES / "model.json").read_text())
    raise SystemExit(f"mode {mode!r} is not available in this lab")


# ------------------------------------------------------------ report


def block(put, lead: str, text: str, width: int = 78) -> None:
    lines = textwrap.wrap(text, width - len(lead))
    put(lead + lines[0])
    for ln in lines[1:]:
        put(" " * len(lead) + ln)


def live_step(put) -> None:
    url, key = os.environ["MODEL_LAB_URL"], os.environ["MODEL_LAB_KEY"]
    model = os.environ["MODEL_LAB_MODEL"]
    messages = json.loads(Path(os.environ["MODEL_LAB_PROMPT"]).read_text())
    xs = [x for x in probe(url, key, model, messages) if x == x]
    put(f"1. time to first answer token on {model}: {len(xs)} requests, "
        "4 at a time")
    put(f"   p50 {pct(xs, 50):.0f} ms   p95 {pct(xs, 95):.0f} ms   "
        "evidence class: live laboratory")


def report(mode: str) -> str:
    data = inputs(mode)
    out: list[str] = []
    put = out.append
    evidence = "live laboratory (step 1)" if mode == "live" else "simulated"
    put(f"model lab, mode={mode}; evidence class: {evidence}")
    put("")
    t = ttft_table(data)
    if mode == "live":
        live_step(put)
    else:
        pr = data["prompt"]
        block(put, "1. ", "time to first token on the Service Line's prompt "
              f"({pr['static'] + pr['dynamic']} tokens, {pr['static']} of "
              f"them the static prefix), {data['requests']} requests at "
              "each load")
        put(f"   {'model':<8}{'cache':<8}" + "".join(
            f"{ld:>15}" for ld in data["loads"]))
        put(f"   {'':<16}" + "".join(f"{'p50':>8}{'p95':>7}"
                                     for _ in data["loads"]))
        for name in data["models"]:
            for cached in (False, True):
                cells = "".join(
                    f"{pct(t[(name, cached, ld)], 50):>8.0f}"
                    f"{pct(t[(name, cached, ld)], 95):>7.0f}"
                    for ld in data["loads"])
                put(f"   {name:<8}{'yes' if cached else 'no':<8}{cells}")
        figs = ", ".join(f"{n} {m['base_ms']} ms"
                         for n, m in data["models"].items())
        block(put, "   ", f"a published figure (one request, a short prompt, "
              f"no load): {figs}")
    put("")
    put("2. which model sits on the caller's turn (evening load, prefix "
        "cached)")
    put(f"   {'placement':<36}{'p50':>6}{'p95':>7}   summary ready")
    rows = [("the small model on the turn", "small", "none"),
            ("the large model on the turn", "large", "none"),
            ("small on the turn, large behind", "small",
             f"{summary_ready_s(data):.1f} s after hang-up")]
    v2v = {}
    for label, model, summary in rows:
        xs = voice_to_voice(data, model, "evening", seed=2)
        v2v[model] = xs
        put(f"   {label:<36}{pct(xs, 50):>6.0f}{pct(xs, 95):>7.0f}   "
            f"{summary}")
    put(f"   the wall: {WALL_MS} ms at p95 (Chapter 1)")
    put("")
    k = {m: pass_k(data, m) for m in data["models"]}
    put(f"3. tool calls: {len(data['scenarios'])} Service Line scenarios, "
        "8 runs each (stand-in rates)")
    put(f"   {'model':<10}{'pass^1':>8}{'pass^8':>9}{'expected':>10}   "
        "failed at least once")
    for m, r in k.items():
        put(f"   {m:<10}{r['pass1']:>8.2f}{r['passk']:>9.2f}"
            f"{r['expected']:>10.2f}   "
            f"{len(r['slipped'])} of {len(data['scenarios'])}")
    caught: dict[str, int] = {}
    for sc in k["small"]["slipped"]:
        caught[sc["caught"]] = caught.get(sc["caught"], 0) + 1
    block(put, "   ", "the small model's slips, by what catches them: " +
          "; ".join(f"{w} {n}" for w, n in sorted(caught.items(),
                                                   key=lambda kv: -kv[1])))
    put("")
    stats = {}
    for m in data["models"]:
        stats[m] = {"ttft95": pct(t[(m, True, "evening")], 95),
                    "v2v95": pct(v2v[m], 95), "pass8": k[m]["passk"],
                    "right": data["quality"][m]["right"],
                    "refused": data["quality"][m]["refused"]}
    put("4. the canary: the large model as a candidate for the turn")
    put("   (5 percent of evening calls; the gates written before it "
        "started)")
    put(f"   {'gate':<36}{'pinned':>9}{'candidate':>12}   verdict")
    stop = False
    for gate, a, b, ok, why in canary(data, stats["small"],
                                      stats["large"]):
        stop = stop or not ok
        put(f"   {gate:<36}{a:>9}{b:>12}   "
            f"{'passes' if ok else 'fails: ' + why}")
    put("   decision: " + ("stop at 5 percent; the large model moves behind "
                          "the turn" if stop else "widen to 25 percent"))
    put("")
    lad = data["ladder"]
    c = ladder(data)
    block(put, "5. ", f"the fallback ladder in a storm hour ({lad['turns']} "
          f"stand-in turns; the rate limit is reached for "
          f"{lad['rate_limited_min']} minutes of it)")
    put(f"   {'what happened':<40}{'turns':>6}   the caller hears")
    first = f"the pinned model answered by {lad['hold_ms']} ms"
    put(f"   {first:<40}{c['answered']:>6}   the answer")
    put(f"   {'late or rate-limited: a holding line,':<40}"
        f"{c['fallback']:>6}   \"One moment.\" then")
    put(f"   {'  then the fallback model answers':<40}{'':>6}   the answer")
    put(f"   {'a legitimate request refused':<40}{c['refused']:>6}   "
        "a fixed line; a person")
    last = f"nothing by {lad['person_ms']} ms"
    put(f"   {last:<40}{c['person']:>6}   a person, with context")
    put("")
    pr = data["prices"]
    turns = data["call"]["turns"]
    block(put, "6. ", f"cost per call: a {turns}-turn billing call "
          "(stand-in prices per million tokens: small "
          f"${pr['small']['in']:.2f} in, ${pr['small']['out']:.2f} out; "
          f"large ${pr['large']['in']:.2f} in, ${pr['large']['out']:.2f} "
          "out; a cached read at a tenth of the input price)")
    put(f"   {'model on the turn':<20}{'cache':<8}{'input tokens':>13}"
        f"{'output':>9}{'model cost':>13}")
    for m in data["models"]:
        for cached in (False, True):
            cc = call_cost(data, m, cached)
            put(f"   {m:<20}{'yes' if cached else 'no':<8}"
                f"{cc['input']:>13,}{cc['output']:>9}"
                f"{'$' + format(cc['dollars'], '.4f'):>13}")
    put(f"   the large model's summary behind the turn adds "
        f"${summary_cost(data):.4f} a call")
    put(f"   the business case assumes ${data['case_per_call']:.2f} a call "
        "for everything (leaders' 4)")
    return "\n".join(x.rstrip() for x in out) + "\n"


def run_mode(mode: str | None = None) -> str:
    mode = mode or os.environ.get("MODEL_LAB_MODE", "mock")
    text = report(mode)
    print(text, end="")
    return text


def check(mode: str) -> int:
    frozen = (OUTPUTS / f"model_lab.{mode}.out.txt").read_text()
    if report(mode) == frozen:
        print(f"check {mode}: identical to the frozen output")
        return 0
    print(f"check {mode}: differs from the frozen output; inspect before "
          "re-freezing")
    return 1


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        FIXTURES.mkdir(parents=True, exist_ok=True)
        (FIXTURES / "model.json").write_text(
            json.dumps(inputs("mock"), indent=1))
        print("wrote fixtures/model.json")
    elif "--check" in sys.argv:
        sys.exit(check(os.environ.get("MODEL_LAB_MODE", "mock")))
    else:
        run_mode()
