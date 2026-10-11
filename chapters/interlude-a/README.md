# Interlude A. Run it first: the Appointment Line

A whole Appointment Line with stand-in layers: holds, one operation per yes, read back before speaking, a whisper on transfer, and four failure checks (recognizer down, last slot twice, out of scope, kill switch)

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/interlude-a
python3 appointment_line.py
APPT_LAB_MODE=fixture python3 appointment_line.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py interlude-a --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova_apps/river_plumbing/pack.py`](../../full-app/src/ova_apps/river_plumbing/pack.py)
- [`ova/agent.py`](../../full-app/src/ova/agent.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/interlude-a-run-it-first.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
