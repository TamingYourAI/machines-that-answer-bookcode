# 12. Speaking

First audio by chunking, and the amount a careless chunker splits; a stutter as a capacity problem; a formatter per locale; the lexicon compiled three ways; the speakable filter; MOS against numbers heard

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch12
python3 speaking_lab.py
SPEAKING_LAB_MODE=fixture python3 speaking_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch12 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/providers/tts.py`](../../full-app/src/ova/providers/tts.py)
- [`ova/speech.py`](../../full-app/src/ova/speech.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch12-speaking.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
