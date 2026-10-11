# 21. Handoff to people: contact-center queues, the service desk, and on-call staff

The handoff record checked; a loop search over the routing rules; a storm evening with the old overflow rule against the truthful queue (131 looped against none; 279 callbacks kept); verification carried across while fresh and in scope

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch21
python3 handoff_lab.py
HANDOFF_LAB_MODE=fixture python3 handoff_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch21 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/agent.py`](../../full-app/src/ova/agent.py)
- [`ova/operations.py`](../../full-app/src/ova/operations.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch21-handoff-to-people.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
