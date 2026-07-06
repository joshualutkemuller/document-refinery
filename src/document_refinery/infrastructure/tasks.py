"""Durable SQLite task table shared by the local orchestration flow."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class TaskStatus(StrEnum):
    LANDED = "landed"
    CLASSIFIED = "classified"
    EXTRACTED = "extracted"
    VALIDATED = "validated"
    GATE_A_PENDING = "gate_a_pending"
    GATE_A_APPROVED = "gate_a_approved"
    GOLD_LANDED = "gold_landed"
    FAILED = "failed"


_ALLOWED_TRANSITIONS = {
    TaskStatus.LANDED: {TaskStatus.CLASSIFIED, TaskStatus.FAILED},
    TaskStatus.CLASSIFIED: {TaskStatus.EXTRACTED, TaskStatus.FAILED},
    TaskStatus.EXTRACTED: {TaskStatus.VALIDATED, TaskStatus.FAILED},
    TaskStatus.VALIDATED: {TaskStatus.GATE_A_PENDING, TaskStatus.FAILED},
    TaskStatus.GATE_A_PENDING: {TaskStatus.GATE_A_APPROVED, TaskStatus.FAILED},
    TaskStatus.GATE_A_APPROVED: {TaskStatus.GOLD_LANDED, TaskStatus.FAILED},
    TaskStatus.GOLD_LANDED: set(),
    TaskStatus.FAILED: set(),
}


@dataclass(frozen=True, slots=True)
class TaskRecord:
    doc_id: str
    status: TaskStatus
    updated_at: datetime
    error: str | None = None


class TaskStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS refinery_tasks (
              doc_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              error TEXT
            )
            """
        )
        self.connection.commit()

    def create(self, doc_id: str) -> TaskRecord:
        now = datetime.now(UTC)
        self.connection.execute(
            """
            INSERT OR IGNORE INTO refinery_tasks(doc_id, status, updated_at)
            VALUES (?, ?, ?)
            """,
            (doc_id, TaskStatus.LANDED.value, now.isoformat()),
        )
        self.connection.commit()
        return self.get(doc_id)

    def transition(
        self,
        doc_id: str,
        status: TaskStatus,
        *,
        error: str | None = None,
    ) -> TaskRecord:
        current = self.get(doc_id)
        if status not in _ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(f"invalid task transition: {current.status} -> {status}")
        now = datetime.now(UTC)
        self.connection.execute(
            """
            UPDATE refinery_tasks SET status = ?, updated_at = ?, error = ?
            WHERE doc_id = ?
            """,
            (status.value, now.isoformat(), error, doc_id),
        )
        self.connection.commit()
        return self.get(doc_id)

    def get(self, doc_id: str) -> TaskRecord:
        row = self.connection.execute(
            "SELECT doc_id, status, updated_at, error FROM refinery_tasks WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        if row is None:
            raise KeyError(doc_id)
        return TaskRecord(
            doc_id=row[0],
            status=TaskStatus(row[1]),
            updated_at=datetime.fromisoformat(row[2]),
            error=row[3],
        )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> TaskStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

