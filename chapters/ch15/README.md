# 15. Choosing and running the model

Time to first token by load, with and without a cached prefix; the small model on the turn and the large behind it; pass^k on tool calls; a canary stopped by its latency gate; the fallback ladder in a storm hour; cost per call. Live mode times the first answer token on your own endpoint

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch15
python3 model_lab.py
MODEL_LAB_MODE=fixture python3 model_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch15 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/providers/llm.py`](../../full-app/src/ova/providers/llm.py)
- [`ova/brain.py`](../../full-app/src/ova/brain.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch15-choosing-the-model.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
