# 10. Hearing

Word error rate against entity accuracy; partials and the stable prefix; boosting names; numbers validated and read back; accuracy by cohort with intervals; transcripts redacted

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch10
python3 hearing_lab.py
HEARING_LAB_MODE=fixture python3 hearing_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch10 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/providers/stt.py`](../../full-app/src/ova/providers/stt.py)
- [`ova/nlu.py`](../../full-app/src/ova/nlu.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch10-hearing.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
