# 26. Observability, and the week you improve: traces, the failure taxonomy, and the review

One bad call from its trace to a permanent scenario: the taxonomy names the layer, the call becomes a scenario, the suite catches it, and the week's review

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch26
python3 observe_lab.py
OBSERVE_LAB_MODE=fixture python3 observe_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch26 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/store.py`](../../full-app/src/ova/store.py)
- [`ova_server/app.py`](../../full-app/src/ova_server/app.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch26-observability-and-the-week-you-improve.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
