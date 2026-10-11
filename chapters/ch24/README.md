# 24. Metrics the business will accept: two families, one record, and numbers that last

Both metric families from one record per call; one week counted three ways; every number split with its interval; Simpson's paradox; the business case checked line by line

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch24
python3 metrics_lab.py
METRICS_LAB_MODE=fixture python3 metrics_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch24 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch24-metrics-the-business-will-accept.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
