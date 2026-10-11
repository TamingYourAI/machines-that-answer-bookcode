# 25. Testing voice agents: the pyramid, simulated callers, and rates you can trust

Unit tests on the policy layer; one booking asserted on state and tool calls; polite and realistic simulated callers; what twenty runs can prove; what runs when, and what it costs

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch25
python3 testing_lab.py
TESTING_LAB_MODE=fixture python3 testing_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch25 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch25-testing-voice-agents.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
