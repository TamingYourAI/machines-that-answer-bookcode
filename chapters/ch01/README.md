# 1. A call is a system, not a chat with a microphone

The three measuring boundaries nest; the dashboard hides most of the caller's wait; containment is not task completion

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch01
python3 call_budget_lab.py
CALL_LAB_MODE=fixture python3 call_budget_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch01 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/voice.py`](../../full-app/src/ova/voice.py)
- [`ova/runtime.py`](../../full-app/src/ova/runtime.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch01-a-call-is-a-system.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
