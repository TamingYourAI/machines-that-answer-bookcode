# 13. Speech-to-speech, in depth

Instructed lines drift and fixed paths do not; the policy gate outside the model; who hears the card; a check on the transcript trails the sound; one dialogue object on two roads; one call, end to end, across the speech stack (Part III)

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch13
python3 s2s_lab.py
S2S_LAB_MODE=fixture python3 s2s_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch13 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch13-speech-to-speech.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
