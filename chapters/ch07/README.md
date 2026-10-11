# 7. Transport and telephony

The invite and one-way audio; what narrowband removes; the jitter buffer's knee; touch-tones kept as events, not audio; the outbound gate on the trunk

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch07
python3 telephony_lab.py
TELEPHONY_LAB_MODE=fixture python3 telephony_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch07 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/audio.py`](../../full-app/src/ova/audio.py)
- [`ova/transports/twilio.py`](../../full-app/src/ova/transports/twilio.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch07-transport-and-telephony.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
