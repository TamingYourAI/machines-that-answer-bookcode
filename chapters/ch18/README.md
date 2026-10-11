# 18. Guardrails and agent reliability

The commitment check blocks unbacked claims and replaces money in the model's own words; paraphrases leak past patterns but not fixed lines; loop detection ends a persistence attack at the second refusal; an obedient model changes no decision; drift by turn window; shadow replay finds one regression and writes nothing; an explanation record answers a complaint

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch18
python3 guard_lab.py
GUARD_LAB_MODE=fixture python3 guard_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch18 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/policy.py`](../../full-app/src/ova/policy.py)
- [`ova/operations.py`](../../full-app/src/ova/operations.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch18-guardrails-and-reliability.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
