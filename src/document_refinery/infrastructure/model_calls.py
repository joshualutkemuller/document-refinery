"""Audit storage for semantic model call metadata and artifact hashes."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from document_refinery.agents.semantic import SemanticCallRecord


class SemanticCallStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, doc_id: str, calls: tuple[SemanticCallRecord, ...]) -> Path:
        path = self.root / f"{doc_id}.jsonl"
        content = "\n".join(
            json.dumps(
                {
                    **asdict(call),
                    "created_at": call.created_at.isoformat(),
                },
                sort_keys=True,
            )
            for call in calls
        )
        path.write_text(content + "\n", encoding="utf-8")
        return path

