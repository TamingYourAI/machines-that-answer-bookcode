# 27. Deploy it: environments, the control plane, and release

The release manifest; shadow mode with writes refused at the tool layer; the evidence gate; a canary with stop rules; drain before swap; the emergency stop

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch27
python3 deploy_lab.py
DEPLOY_LAB_MODE=fixture python3 deploy_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch27 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/runtime.py`](../../full-app/src/ova/runtime.py)
- [`ova_server/app.py`](../../full-app/src/ova_server/app.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch27-deploy-it.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
