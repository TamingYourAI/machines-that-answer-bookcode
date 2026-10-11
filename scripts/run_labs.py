"""Run one independent chapter, or verify every chapter without external services."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter", nargs="?", default="all")
    parser.add_argument("--mode", choices=["mock", "fixture"], default="mock")
    parser.add_argument("--check", action="store_true", help="Check both frozen outputs and tests")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "chapters/manifest.json").read_text())
    selected = [x for x in manifest if args.chapter in ("all", x["id"])]
    if not selected:
        parser.error("Unknown lab; use an id from chapters/manifest.json, such as ch17")
    report = []
    for chapter in selected:
        directory = ROOT / "chapters" / chapter["id"]
        results = []
        for mode in (["mock", "fixture"] if args.check else [args.mode]):
            env = dict(os.environ, **{chapter["mode_env"]: mode})
            cmd = [sys.executable, chapter["entrypoint"]] + (["--check"] if args.check else [])
            r = subprocess.run(cmd, cwd=directory, env=env, text=True, capture_output=args.check,
                               timeout=120)
            results.append({"name": mode, "ok": r.returncode == 0})
            if args.check and r.returncode:
                print(r.stdout, r.stderr, file=sys.stderr)
        if args.check:
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-p", "test_*.py"],
                               cwd=directory, text=True, capture_output=True, timeout=120)
            results.append({"name": "tests", "ok": r.returncode == 0, "output": r.stderr.strip()})
            if r.returncode:
                print(r.stdout, r.stderr, file=sys.stderr)
        ok = all(x["ok"] for x in results)
        print(f"{chapter['id']}: {'PASS' if ok else 'FAIL'}", flush=True)
        report.append({"chapter": chapter["id"], "ok": ok, "checks": results})
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"evidence_class": "simulated", "chapters": report}, indent=2) + "\n")
    return 0 if all(x["ok"] for x in report) else 1


if __name__ == "__main__":
    sys.exit(main())
