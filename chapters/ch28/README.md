# 28. Keep it up: capacity, failure, and recovery

One capacity model with the desk in it; mid-call failover; four failure classes; nothing done twice through a lost region; the drill; the degradation ladder

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch28
python3 resilience_lab.py
RESILIENCE_LAB_MODE=fixture python3 resilience_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch28 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch28-keep-it-up.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
