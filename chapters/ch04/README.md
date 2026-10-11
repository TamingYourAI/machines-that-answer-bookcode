# 4. Conversation design

A flow as a dialogue object; confirmation by risk; one repair line loops on the same callers that a repair catalog books or hands over; the read-aloud test

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch04
python3 dialogue_lab.py
DIALOGUE_LAB_MODE=fixture python3 dialogue_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch04 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/dialogue.py`](../../full-app/src/ova/dialogue.py)
- [`ova/agent.py`](../../full-app/src/ova/agent.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch04-conversation-design.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
