"""Persistent correction memory — the system learns from owner corrections.

Every owner correction is folded into a durable, queryable memory keyed by
``(doc_class, field_suffix, original_value)``. When a later extraction produces a
value that was previously corrected for the same field of the same document
class, the memory *suggests* the learned fix during review — so the same mistake
is caught again instead of re-reviewed from scratch. This is the distiller's core
promise (handoff §5.7): a correction must become reusable knowledge, never
evaporate.

The memory only *suggests*; it never mutates silver or writes gold. The owner
still gates every value (locked decisions 1–4). A `correct` action teaches a fix;
a `dispute` records a "review carefully" flag with no automatic value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from document_refinery.application.corrections import CorrectionAction, CorrectionRecord
from document_refinery.domain.models import SilverExtraction


@dataclass(frozen=True, slots=True)
class LearnedCorrection:
    doc_class: str
    field_suffix: str
    original_value: str
    corrected_value: str | None  # None => previously disputed (warn only)
    occurrences: int
    last_reviewer: str
    last_seen: datetime
    note: str | None = None

    @property
    def is_fix(self) -> bool:
        return self.corrected_value is not None

    def to_json(self) -> dict[str, object]:
        return {
            "doc_class": self.doc_class,
            "field_suffix": self.field_suffix,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "occurrences": self.occurrences,
            "last_reviewer": self.last_reviewer,
            "last_seen": self.last_seen.isoformat(),
            "note": self.note,
        }

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> LearnedCorrection:
        corrected = payload.get("corrected_value")
        note = payload.get("note")
        return cls(
            doc_class=str(payload["doc_class"]),
            field_suffix=str(payload["field_suffix"]),
            original_value=str(payload["original_value"]),
            corrected_value=None if corrected is None else str(corrected),
            occurrences=int(str(payload["occurrences"])),
            last_reviewer=str(payload["last_reviewer"]),
            last_seen=datetime.fromisoformat(str(payload["last_seen"])),
            note=None if note is None else str(note),
        )


_Key = tuple[str, str, str]


def _field_suffix(field_path: str) -> str:
    # Drop the record index (eligibility[0].haircut_pct -> haircut_pct) so a
    # lesson generalizes across records and documents.
    return field_path.rsplit(".", 1)[-1]


class CorrectionMemory:
    """Durable, in-memory index of learned corrections (persisted by a store)."""

    def __init__(self, entries: tuple[LearnedCorrection, ...] = ()) -> None:
        self._by_key: dict[_Key, LearnedCorrection] = {
            (e.doc_class, e.field_suffix, e.original_value): e for e in entries
        }

    def learn(
        self,
        rows: tuple[SilverExtraction, ...],
        records: tuple[CorrectionRecord, ...],
    ) -> tuple[LearnedCorrection, ...]:
        """Fold correction records into the memory, returning what was learned."""
        doc_class_by_id = {row.extraction_id: row.doc_class for row in rows}
        learned: list[LearnedCorrection] = []
        for record in records:
            if record.action not in {CorrectionAction.CORRECT, CorrectionAction.DISPUTE}:
                continue
            doc_class = doc_class_by_id.get(record.extraction_id, "unknown")
            key = (doc_class, _field_suffix(record.field_path), record.previous_value)
            previous = self._by_key.get(key)
            occurrences = (previous.occurrences if previous else 0) + 1
            corrected = (
                record.corrected_value if record.action is CorrectionAction.CORRECT else None
            )
            entry = LearnedCorrection(
                doc_class=doc_class,
                field_suffix=key[1],
                original_value=record.previous_value,
                corrected_value=corrected,
                occurrences=occurrences,
                last_reviewer=record.reviewer,
                last_seen=record.decided_at,
                note=record.note,
            )
            self._by_key[key] = entry
            learned.append(entry)
        return tuple(learned)

    def suggest(
        self, doc_class: str, field_path: str, value: str
    ) -> LearnedCorrection | None:
        return self._by_key.get((doc_class, _field_suffix(field_path), value))

    def suggestions_for(
        self, rows: tuple[SilverExtraction, ...]
    ) -> dict[str, LearnedCorrection]:
        """Map extraction_id -> a learned correction that applies to that row."""
        out: dict[str, LearnedCorrection] = {}
        for row in rows:
            hit = self.suggest(row.doc_class, row.field_path, row.effective_value)
            if hit is not None:
                out[row.extraction_id] = hit
        return out

    def entries(self) -> tuple[LearnedCorrection, ...]:
        return tuple(
            sorted(
                self._by_key.values(),
                key=lambda e: (e.doc_class, e.field_suffix, e.original_value),
            )
        )
