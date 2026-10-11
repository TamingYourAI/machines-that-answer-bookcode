# 5. Which calls first, then SOP to spoken flow

Ranking by calls the agent could finish, gated by risk; a procedure compiled against the desk's practice with every touch marked and drift flagged; an outbound gate on consent, opt-out, and the local hour; one call, end to end, block by block (Part II)

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch05
python3 sop_lab.py
SOP_LAB_MODE=fixture python3 sop_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch05 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/dialogue.py`](../../full-app/src/ova/dialogue.py)
- [`ova_apps/river_plumbing/pack.py`](../../full-app/src/ova_apps/river_plumbing/pack.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch05-which-calls-first.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
