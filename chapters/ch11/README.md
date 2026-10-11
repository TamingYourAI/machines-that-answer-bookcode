# 11. Turn-taking

One silence timer against two thresholds chosen by the words; pause on voice, decide on words; the model's history cut to what was heard; silence clocks started when a line has played

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch11
python3 turn_lab.py
TURN_LAB_MODE=fixture python3 turn_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch11 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/turn.py`](../../full-app/src/ova/turn.py)
- [`ova/voice.py`](../../full-app/src/ova/voice.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch11-turn-taking.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
