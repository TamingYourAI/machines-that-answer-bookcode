"""The suite's own tests: run from the companion's root with ``python -m pytest evals/tests``."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
