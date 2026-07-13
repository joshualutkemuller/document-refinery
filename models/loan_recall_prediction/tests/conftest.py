"""Test path setup for the standalone loan recall prediction model."""

from __future__ import annotations

import sys
from pathlib import Path

MODEL_SRC = Path(__file__).resolve().parents[1] / "src"
if str(MODEL_SRC) not in sys.path:
    sys.path.insert(0, str(MODEL_SRC))
