# 9. Where the voice lives: web, mobile, workplace apps, and devices

Short-lived tokens that lock the agent; one agent-state stream for the voice and the screen; a tap and a yes through one confirmation; old app versions handled; voice to voice by device

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch09
python3 surface_lab.py
SURFACE_LAB_MODE=fixture python3 surface_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch09 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova_server/web/static/voice.js`](../../full-app/src/ova_server/web/static/voice.js)
- [`ova_server/app.py`](../../full-app/src/ova_server/app.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch09-where-the-voice-lives.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
