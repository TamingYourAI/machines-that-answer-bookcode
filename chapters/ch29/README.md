# 29. Keeping it good: maintenance over the years

The care calendar as data; a release diff and the runs it triggers; knowledge that expires loudly; drift against a trailing baseline and fixed limits; cost drift by who billed it

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch29
python3 care_lab.py
CARE_LAB_MODE=fixture python3 care_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch29 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch29-keeping-it-good.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
