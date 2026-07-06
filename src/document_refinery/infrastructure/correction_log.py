"""Append-only JSONL audit of owner corrections and disputes.

Mirrors the hash-only local audit pattern used by ``SemanticCallStore``: every
reviewer action is durable and replayable so no correction can evaporate — the
failure mode the distiller learning loop exists to prevent (handoff instruction
5). One file per document; new actions append rather than overwrite.
"""

from __future__ import annotations

import json
from pathlib import Path

from document_refinery.application.corrections import CorrectionRecord


class CorrectionLog:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, doc_id: str) -> Path:
        return self.root / f"{doc_id}.jsonl"

    def append(self, doc_id: str, records: tuple[CorrectionRecord, ...]) -> Path:
        path = self._path(doc_id)
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.to_json(), sort_keys=True) + "\n")
        return path

    def read(self, doc_id: str) -> tuple[CorrectionRecord, ...]:
        path = self._path(doc_id)
        if not path.exists():
            return ()
        return tuple(
            CorrectionRecord.from_json(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
