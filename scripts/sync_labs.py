"""Copy the book's labs into chapters/, with their READMEs, manifest and source hashes.

Run beside the authoring project (the book's repository holds this folder); a published
clone has no labs to copy from. Each lab keeps its book folder name, so labs that read a
sibling (Appendix M reads Chapter 26 and Interlude B) still find it.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT.parent
LABS = BOOK / "code-labs" / "builders"
CHAPTERS = ROOT / "chapters"
OMIT = {"__pycache__", ".pytest_cache", ".DS_Store"}

SOURCES = {  # lab folder -> the manuscript file it serves
    "interlude-a": "interlude-a-run-it-first.md",
    "interlude-b": "interlude-b-assemble-the-service-line-slice.md",
    "appendix-m": "appendix-m-scenario-format.md",
}
ORDER = [f"ch{n:02d}" for n in range(1, 30)] + ["interlude-a", "interlude-b", "appendix-m"]

# What each lab shows, in one line; kept from 0.2.0 for the labs it already had.
NEW_SUMMARIES = {
    "ch23": "Where a card number lands; a marker tone that proves every fork paused; "
            "redaction that follows digits across turns; security signals from one evening",
    "ch24": "Both metric families from one record per call; one week counted three ways; "
            "every number split with its interval; Simpson's paradox; the business case "
            "checked line by line",
    "ch25": "Unit tests on the policy layer; one booking asserted on state and tool calls; "
            "polite and realistic simulated callers; what twenty runs can prove; what runs "
            "when, and what it costs",
    "ch26": "One bad call from its trace to a permanent scenario: the taxonomy names the "
            "layer, the call becomes a scenario, the suite catches it, and the week's review",
    "ch27": "The release manifest; shadow mode with writes refused at the tool layer; the "
            "evidence gate; a canary with stop rules; drain before swap; the emergency stop",
    "ch28": "One capacity model with the desk in it; mid-call failover; four failure "
            "classes; nothing done twice through a lost region; the drill; the degradation "
            "ladder",
    "ch29": "The care calendar as data; a release diff and the runs it triggers; knowledge "
            "that expires loudly; drift against a trailing baseline and fixed limits; cost "
            "drift by who billed it",
    "interlude-b": "The Service Line slice from Parts III to V: identity, one operation per "
                   "yes, heard state, payment, transfer, and the four cross-chapter "
                   "scenarios accepted",
    "appendix-m": "The scenario format, a validator and five broken scenarios, the starter "
                  "catalogue for the three businesses, and the four acceptance scenarios of "
                  "Appendix Q with the piece that guards each",
}
NEW_INTEGRATED = {  # application files that carry part of a new lab's mechanism
    "ch23": ["ova/agent.py"],
    "ch26": ["ova/store.py", "ova_server/app.py"],
    "ch27": ["ova/runtime.py", "ova_server/app.py"],
}
EVIDENCE = ("Evidence: simulated. Passing the lab establishes its stated invariant under its "
            "fixture assumptions. It does not measure a speech provider or establish "
            "production readiness.")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lab_files(folder: Path):
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if path.is_file() and not OMIT.intersection(rel.parts) and path.suffix != ".pyc":
            yield rel


def manuscript(lab: str) -> Path:
    name = SOURCES.get(lab)
    if name is None:
        name = next(p.name for p in (BOOK / "manuscript/builders").glob(f"{lab}-*.md"))
    return BOOK / "manuscript" / "builders" / name


def readme(entry: dict, summary: str) -> str:
    lab, run, env = entry["id"], entry["entrypoint"], entry["mode_env"]
    follow = ("\n".join(f"- [`{f}`](../../full-app/src/{f})" for f in entry["integrated_files"])
              or "This mechanism is simulated in this lab. A live adapter is not shipped in "
                 "the integrated app.")
    return f"""# {entry['title']}

{summary}

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/{lab}
python3 {run}
{env}=fixture python3 {run}
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py {lab} --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

{follow}

{EVIDENCE}

Source: manuscript {entry['source'].removeprefix('manuscript/')}; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
"""


def main() -> None:
    old = {e["id"]: e for e in json.loads((CHAPTERS / "manifest.json").read_text())}
    manifest, rows = [], []
    for lab in ORDER:
        src = LABS / lab
        dst = CHAPTERS / lab
        run = next(p.name for p in sorted(src.glob("*.py")) if not p.name.startswith("test_"))
        env = re.search(r"\b([A-Z][A-Z0-9_]*_MODE)\b", (src / run).read_text()).group(1)
        doc = manuscript(lab)
        title = doc.read_text().splitlines()[0].lstrip("# ").strip()
        before = old.get(lab, {})
        entry = {"id": lab, "title": title, "entrypoint": run, "mode_env": env,
                 "source": str(doc.relative_to(BOOK)),
                 "integrated_files": before.get("integrated_files", NEW_INTEGRATED.get(lab, [])),
                 "evidence_class": "simulated"}
        summary = NEW_SUMMARIES.get(lab)
        if summary is None:
            summary = (dst / "README.md").read_text().split("\n\n")[1].strip()
        if dst.exists():
            shutil.rmtree(dst)
        for rel in lab_files(src):
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src / rel, dst / rel)
            rows.append({"source": str((src / rel).relative_to(BOOK)),
                         "destination": str((dst / rel).relative_to(ROOT)),
                         "sha256": sha256(src / rel)})
        (dst / "README.md").write_text(readme(entry, summary))
        manifest.append(entry)
    (CHAPTERS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    table = "\n".join(f"| [{e['title']}]({e['id']}/README.md) | `{e['entrypoint']}` |"
                      for e in manifest)
    index = CHAPTERS / "README.md"
    text = index.read_text()
    start, end = text.index("| Chapter | Lab |"), text.index("\n\nRun `python scripts/run_labs.py")
    index.write_text(text[:start] + "| Chapter | Lab |\n| --- | --- |\n" + table + text[end:])
    snap_path = ROOT / "docs" / "source-snapshot.json"
    snap = json.loads(snap_path.read_text())
    commit = subprocess.run(["git", "-C", str(BOOK), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    snap["files"] = [r for r in snap["files"] if not r["destination"].startswith("chapters/")]
    snap["files"] += rows
    snap["labs"] = {"date": __import__("datetime").date.today().isoformat(),
                    "source_commit": commit, "labs": len(manifest)}
    snap_path.write_text(json.dumps(snap, indent=2) + "\n")
    print(f"Synced {len(manifest)} labs, {len(rows)} files, from {commit[:7]}")


if __name__ == "__main__":
    main()
