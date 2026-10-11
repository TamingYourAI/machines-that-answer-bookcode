# 16. Instructions and knowledge: what the agent is told and what it knows

A procedure compiled into steps with preconditions; access filters before ranking; precedence and lineage settle a conflict; the answer rendered with its exception; an ended item never spoken; abstaining; a long call's context

## Run independently

Requires Python 3.12 or later. No installation, account, key or network.

```sh
cd chapters/ch16
python3 knowledge_lab.py
KNOWLEDGE_LAB_MODE=fixture python3 knowledge_lab.py
python3 -m unittest discover -p "test_*.py"
```

Or from the repository root: `python3 scripts/run_labs.py ch16 --check`.
Fixtures and frozen outputs stay inside this chapter directory.

## Follow the mechanism into the application

- [`ova/knowledge.py`](../../full-app/src/ova/knowledge.py)
- [`ova/brain.py`](../../full-app/src/ova/brain.py)

Evidence: simulated. Passing the lab establishes its stated invariant under its fixture assumptions. It does not measure a speech provider or establish production readiness.

Source: manuscript builders/ch16-instructions-and-knowledge.md; source hashes are in [the export snapshot](../../docs/source-snapshot.json).
