# 8. Connecting to the business: every way in

One internal contract behind SIP, a WebSocket stream, and WebRTC; the adapter matrix with untested claims marked; loss on UDP against TCP; clear and marks at a barge-in; context across two transfers

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch08
python3 entry_lab.py
ENTRY_LAB_MODE=fixture python3 entry_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch08 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/transports/twilio.py`](../../full-app/src/ova/transports/twilio.py)
- [`ova/transports/webrtc.py`](../../full-app/src/ova/transports/webrtc.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch08-connecting-to-the-business.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
