"""The command line.

    python -m voice_eval validate [paths]
    python -m voice_eval run --url http://127.0.0.1:8080 [--runner text|audio] [--runs N]
                             [--reset] [--admin-token T] [--name NAME] [--version V]
                             [--out DIR] [paths]

Paths default to the scenarios beside this package. A run uses each scenario's own number of runs
unless --runs says otherwise; --runs 1 is a smoke test, not a rate.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from . import records, report
from .checks import Ctx, run_checks
from .scenarios import load

HERE = Path(__file__).resolve().parent
DEFAULT = HERE.parent / "scenarios"


def _validate(paths: list[Path]) -> int:
    bad = 0
    for sc in load(paths):
        if sc.problems:
            bad += 1
            print(f"{sc.id}: " + "; ".join(sc.problems))
    print(f"{'all valid' if not bad else f'{bad} invalid'}")
    return 1 if bad else 0


async def _run(args, paths: list[Path]) -> int:
    scs = [s for s in load(paths) if args.runner in s.data["runners"]]
    invalid = [s for s in scs if s.problems]
    for s in invalid:
        print(f"skipped, invalid: {s.id}: {'; '.join(s.problems)}")
    if args.runner == "text":
        from .runners import text as runner
    elif args.runner == "audio":
        from .runners import audio as runner
    else:
        sys.exit(f"the {args.runner} runner is not in this release")
    token = args.admin_token or os.environ.get("OVA_ADMIN_TOKEN", "")
    summaries = []
    for sc in [s for s in scs if not s.problems]:
        n = args.runs or sc.data["runs"]["n"]
        runs = []
        for i in range(n):
            if args.reset:
                try:
                    records.reset_ova(args.url, token)
                except Exception as e:           # noqa: BLE001
                    sys.exit(f"--reset failed: {type(e).__name__}: {e}. Start the server with "
                             "OVA_ALLOW_RESET=on, or run without --reset.")
            res = await runner.run(args.url, sc)
            rec = {"call": {"id": "", "outcome": ""}, "turns": [], "operations": [],
                   "messages": []}
            if res.call_id and not res.error:
                try:
                    rec = records.from_ova(args.url, res.call_id, token, res.say_terms)
                except Exception as e:           # noqa: BLE001
                    res.error = f"records: {type(e).__name__}: {e}"
            checks = run_checks(sc.data["expect"], Ctx(rec, args.runner, res.measures,
                                                       res.events, len(res.caller_turns)))
            runs.append({"checks": checks, "error": res.error, "measures": res.measures,
                         "call": res.call_id})
            mark = "".join("." if c["passed"] else ("x" if c["passed"] is False else
                                                     ("-" if c.get("applies") is False else "?"))
                           for c in checks)
            print(f"{sc.id} run {i + 1}/{n} {mark}{' error: ' + res.error if res.error else ''}",
                  flush=True)
        summaries.append(report.summarize(sc, runs))
    system = {"name": args.name, "version": args.version, "url": args.url}
    jpath, mpath = report.write(system, args.runner, summaries, Path(args.out))
    print(mpath.read_text())
    print(f"wrote {jpath} and {mpath}")
    return 1 if any(s["met_rule"] is False for s in summaries) else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="voice_eval")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("paths", nargs="*", type=Path)
    r = sub.add_parser("run")
    r.add_argument("paths", nargs="*", type=Path)
    r.add_argument("--url", required=True)
    r.add_argument("--runner", default="text", choices=["text", "audio", "phone"])
    r.add_argument("--runs", type=int, default=0)
    r.add_argument("--admin-token", default="")
    r.add_argument("--name", default="Open Voice Agents")
    r.add_argument("--version", default="unknown")
    r.add_argument("--out", default="eval-results")
    r.add_argument("--reset", action="store_true",
                   help="reset the companion app's records to its seeds before every run")
    a = p.parse_args(argv)
    paths = a.paths or [DEFAULT]
    if a.cmd == "validate":
        return _validate(paths)
    return asyncio.run(_run(a, paths))


if __name__ == "__main__":
    sys.exit(main())
