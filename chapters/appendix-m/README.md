# Appendix M. The scenario format, and a starter catalogue

The scenario format, a validator and five broken scenarios, the starter catalogue for the three businesses, and the four acceptance scenarios of Appendix Q with the piece that guards each

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/appendix-m
python3 scenario_lab.py
SCENARIO_LAB_MODE=fixture python3 scenario_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py appendix-m --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

This mechanism is simulated in this lab. A live adapter is not shipped in the integrated app.

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/appendix-m-scenario-format.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
