# Interlude B. Assemble the Service Line slice

The Service Line slice from Parts III to V: identity, one operation per yes, heard state, payment, transfer, and the four cross-chapter scenarios accepted

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/interlude-b
python3 service_slice.py
SLICE_LAB_MODE=fixture python3 service_slice.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py interlude-b --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/interlude-b-assemble-the-service-line-slice.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
