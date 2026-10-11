# 3. Voice design

A brief kept as data can be checked; lines written for the eye fail the ear check; identifiers are read in groups; the most natural voice can fail the listening test on numbers

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch03
python3 voice_lab.py
VOICE_LAB_MODE=fixture python3 voice_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch03 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/runtime.py`](../../full-app/src/ova/runtime.py)
- [`ova/speech.py`](../../full-app/src/ova/speech.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch03-voice-design.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
