# 19. Orchestration, and the swap

An interruption in its own lane stops audio within a frame; marks counted against clears prove what played; the race suite's invariants hold where a naive orchestrator breaks them; speculation saves the first token's time and plays nothing early; a hidden span found on your own clock; the latency playbook; one call, end to end

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch19
python3 orch_lab.py
ORCH_LAB_MODE=fixture python3 orch_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch19 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/voice.py`](../../full-app/src/ova/voice.py)
- [`ova/transports/webrtc.py`](../../full-app/src/ova/transports/webrtc.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch19-orchestration-and-the-swap.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
