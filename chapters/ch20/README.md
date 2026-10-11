# 20. Systems of record, identity, and memory

A number finds candidates, never a caller; the proof ladder with a step-up; a signed verification statement every system checks (another account, a system not named, an edited level, and an old statement refused); five memory tests, 0 of 5 naive and 5 of 5 designed

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch20
python3 identity_lab.py
IDENTITY_LAB_MODE=fixture python3 identity_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch20 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/links.py`](../../full-app/src/ova/links.py)
- [`ova_apps/claims/domain.py`](../../full-app/src/ova_apps/claims/domain.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch20-systems-of-record-identity-and-memory.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
