"""Durable JSONL persistence for the correction memory.

The memory outlives any single run: it is loaded at startup and saved after every
learning event, so lessons accumulate across documents and sessions. One entry
per learned ``(doc_class, field_suffix, original_value)``.
"""

from __future__ import annotations

import json
from pathlib import Path

from document_refinery.application.correction_memory import CorrectionMemory, LearnedCorrection


class CorrectionMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> CorrectionMemory:
        if not self.path.exists():
            return CorrectionMemory()
        entries = tuple(
            LearnedCorrection.from_json(json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        return CorrectionMemory(entries)

    def save(self, memory: CorrectionMemory) -> Path:
        content = "\n".join(
            json.dumps(entry.to_json(), sort_keys=True) for entry in memory.entries()
        )
        self.path.write_text(content + "\n" if content else "", encoding="utf-8")
        return self.path
