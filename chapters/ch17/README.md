# 17. Tools and actions

Operation ids prevent duplicates; reconciliation prevents false statements; a yes binds to one operation's heard terms; conditional writes and holds prevent double booking; tracked promises never break silently

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch17
python3 tools_lab.py
TOOLS_LAB_MODE=fixture python3 tools_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch17 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/operations.py`](../../full-app/src/ova/operations.py)
- [`ova/store.py`](../../full-app/src/ova/store.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch17-tools-and-actions.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
