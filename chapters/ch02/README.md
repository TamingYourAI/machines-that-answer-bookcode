# 2. Where the agent sits: contact centers, service desks, and the systems that were there first

Only front of the ACD meets the Service Line's six requirements; a mixed seat breaks six contracts; one call, end to end, as the business sees it (Part I)

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch02
python3 seat_lab.py
SEAT_LAB_MODE=fixture python3 seat_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch02 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/runtime.py`](../../full-app/src/ova/runtime.py)
- [`ova/transports/twilio.py`](../../full-app/src/ova/transports/twilio.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch02-where-the-agent-sits.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
