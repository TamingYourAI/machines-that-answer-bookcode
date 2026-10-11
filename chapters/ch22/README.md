# 22. Agents on the line: machine callers, delegation, and agent protocols

Callers treated by what they say and prove; a delegation checked like a verification level; a hold flood capped per principal and per platform; a partner's task tracked as a promise, kept either way

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch22
python3 agents_lab.py
AGENTS_LAB_MODE=fixture python3 agents_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch22 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch22-agents-on-the-line.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
