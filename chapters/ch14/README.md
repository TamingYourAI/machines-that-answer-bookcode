# 14. Agent architecture: the turn loop, control, state, and policy

Guided control ends as designed where scripted and free-form do not; the policy layer's five checks; a stale result from a canceled response is kept in the state and never spoken; a resume reconciles before it speaks; an approval outlives the call; model calls on the turn; an adapter for an existing text agent

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch14
python3 core_lab.py
CORE_LAB_MODE=fixture python3 core_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch14 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/agent.py`](../../full-app/src/ova/agent.py)
- [`ova/runtime.py`](../../full-app/src/ova/runtime.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch14-agent-architecture.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
