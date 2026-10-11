"""The report: both families side by side, never one score (Chapter 24), as rates with Wilson
intervals (Chapter 25), with the conditions and evidence class of every number."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import __version__
from .checks import family_verdict
from .stats import median, percentile, rate

EVIDENCE = {"text": "simulated", "audio": "live laboratory (synthetic caller)",
            "phone": "live laboratory (synthetic caller, real phone network)"}


def summarize(sc, runs: list[dict]) -> dict:
    """One scenario's runs: each family's pass rate, whether the scenario met its own rule, and
    the measurements pooled over every turn of every run."""
    fam = {}
    for f in ("task", "experience"):
        verdicts = [family_verdict(r["checks"], f) for r in runs]
        made = [v for v in verdicts if v is not None]
        fam[f] = None if not made else {**rate(sum(made), len(made)),
                                         "not_checked": len(verdicts) - len(made)}
    rule = sc.data["runs"]["pass"]
    need = len(runs) if rule == "all" else int(rule.split()[-1])
    both = [all(family_verdict(r["checks"], f) is not False for f in ("task", "experience"))
            and not r["error"] for r in runs]
    gaps = [g for r in runs for g in r.get("measures", {}).get("gaps_ms", [])]
    return {
        "scenario": sc.id, "title": sc.data["title"], "line": sc.data["line"],
        "conditions": sc.data["conditions"], "runs": len(runs), "rule": rule,
        "met_rule": (sum(both) >= need) if len(runs) >= sc.data["runs"]["n"] else None,
        "required_runs": sc.data["runs"]["n"],
        "families": fam,
        "gap_ms": {"median": median(gaps), "p95": percentile(gaps, 95), "turns": len(gaps)}
        if gaps else None,
        "errors": [r["error"] for r in runs if r["error"]],
        "failures": sorted({f"{c['key']}: {c['detail']}" for r in runs for c in r["checks"]
                            if c["passed"] is False}),
    }


def _pct(f: dict | None) -> str:
    if not f:
        return "not checked"
    lo, hi = f["interval"]
    extra = f", {f['not_checked']} not checked" if f.get("not_checked") else ""
    return f"{f['passed']} of {f['runs']} ({lo:.0%} to {hi:.0%}){extra}"


def _rule(s: dict) -> str:
    if s["met_rule"] is None:
        return f"not judged: {s['runs']} of {s['required_runs']} runs"
    return f"{'yes' if s['met_rule'] else 'no'} ({s['rule']} of {s['required_runs']})"


def write(system: dict, runner: str, summaries: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    head = {"suite": f"voice_eval {__version__}", "date": stamp, "system": system,
            "runner": runner, "evidence_class": EVIDENCE.get(runner, runner)}
    jpath = out_dir / f"report-{runner}.json"
    jpath.write_text(json.dumps({**head, "scenarios": summaries}, indent=1) + "\n")
    rows = [f"# Test report: {system.get('name', 'system')}", "",
            f"Suite voice_eval {__version__}, {stamp}. Runner: {runner}. Evidence class: "
            f"{head['evidence_class']}. System: {system.get('name')}, version "
            f"{system.get('version', 'unknown')}, at {system.get('url', 'unknown')}.", "",
            "The task family asks whether the work was done, and done honestly; the experience "
            "family asks how the call went. They are reported apart and never added together. "
            "Each rate is a count of runs with its Wilson 95 percent interval.", "",
            "| Scenario | Task family | Experience family | Met its rule | Response gap |",
            "| --- | --- | --- | --- | --- |"]
    for s in summaries:
        gap = (f"median {s['gap_ms']['median']:.0f} ms, p95 {s['gap_ms']['p95']:.0f} ms"
               if s["gap_ms"] else "not measured")
        rows.append(f"| {s['scenario']}: {s['title']} | {_pct(s['families']['task'])} | "
                    f"{_pct(s['families']['experience'])} | "
                    f"{_rule(s)} | {gap} |")
    fails = [(s["scenario"], f) for s in summaries for f in s["failures"]]
    errs = [(s["scenario"], e) for s in summaries for e in s["errors"]]
    if fails or errs:
        rows += ["", "## What failed", ""]
        rows += [f"- {sid}: {f}" for sid, f in fails] + [f"- {sid}: error: {e}" for sid, e in errs]
    mpath = out_dir / f"report-{runner}.md"
    mpath.write_text("\n".join(rows) + "\n")
    return jpath, mpath
