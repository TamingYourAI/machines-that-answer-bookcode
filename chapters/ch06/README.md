# 6. The stack: reference architecture and the first fork

Four rules an adapter must keep to stand behind a layer; the call clock against vendor clocks; the event timeline after a barge-in; pipeline against speech-to-speech; the ecosystem map

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch06
python3 stack_lab.py
STACK_LAB_MODE=fixture python3 stack_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch06 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/providers/__init__.py`](../../full-app/src/ova/providers/__init__.py)
- [`ova/voice.py`](../../full-app/src/ova/voice.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch06-the-stack.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
