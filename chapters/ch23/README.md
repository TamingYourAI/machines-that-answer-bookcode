# 23. Trust on the live call: disclosure, card numbers, and threats

Where a card number lands; a marker tone that proves every fork paused; redaction that follows digits across turns; security signals from one evening

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch23
python3 trust_lab.py
TRUST_LAB_MODE=fixture python3 trust_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch23 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/agent.py`](../../full-app/src/ova/agent.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch23-trust-on-the-live-call.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
