"""Authenticated owner corrections and disputes on silver extractions.

This is the review action layer that sits between the read-only Gate A packet
and the Gate A sign-off. An identified reviewer confirms, corrects, or disputes
individual silver rows; trusted application code (never the model or the UI)
applies those actions. Raw and normalized values are preserved so clause-level
lineage (Locked Decision 1) survives every correction — a correction records the
owner's intended value in ``corrected_value`` without erasing what the extractor
originally read.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

from document_refinery.domain.models import SilverExtraction, ValidatorStatus


class CorrectionAction(StrEnum):
    CONFIRM = "confirm"
    CORRECT = "correct"
    DISPUTE = "dispute"


@dataclass(frozen=True, slots=True)
class CorrectionRequest:
    """A single reviewer action against one silver row, keyed by extraction_id."""

    extraction_id: str
    action: CorrectionAction
    corrected_value: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.extraction_id.strip():
            raise ValueError("correction requires an extraction_id")
        if self.action is CorrectionAction.CORRECT and not (self.corrected_value or "").strip():
            raise ValueError("a correction requires a non-empty corrected_value")
        if self.action is CorrectionAction.DISPUTE and not (self.note or "").strip():
            raise ValueError("a dispute requires an explanatory note")


@dataclass(frozen=True, slots=True)
class CorrectionRecord:
    """Immutable audit of an applied reviewer action.

    Captures the before/after so the distiller can later replay corrections into
    constitution rules or golden cases (handoff instruction 5) without needing
    the mutated silver row.
    """

    doc_id: str
    extraction_id: str
    field_path: str
    action: CorrectionAction
    reviewer: str
    decided_at: datetime
    previous_status: ValidatorStatus
    previous_value: str
    corrected_value: str | None
    note: str | None

    def to_json(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "extraction_id": self.extraction_id,
            "field_path": self.field_path,
            "action": self.action.value,
            "reviewer": self.reviewer,
            "decided_at": self.decided_at.isoformat(),
            "previous_status": self.previous_status.value,
            "previous_value": self.previous_value,
            "corrected_value": self.corrected_value,
            "note": self.note,
        }

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> CorrectionRecord:
        return cls(
            doc_id=str(payload["doc_id"]),
            extraction_id=str(payload["extraction_id"]),
            field_path=str(payload["field_path"]),
            action=CorrectionAction(str(payload["action"])),
            reviewer=str(payload["reviewer"]),
            decided_at=datetime.fromisoformat(str(payload["decided_at"])),
            previous_status=ValidatorStatus(str(payload["previous_status"])),
            previous_value=str(payload["previous_value"]),
            corrected_value=(
                None if payload.get("corrected_value") is None
                else str(payload["corrected_value"])
            ),
            note=None if payload.get("note") is None else str(payload["note"]),
        )


@dataclass(frozen=True, slots=True)
class CorrectionOutcome:
    rows: tuple[SilverExtraction, ...]
    records: tuple[CorrectionRecord, ...]


class CorrectionService:
    """Applies reviewer actions to silver rows, preserving lineage."""

    def apply(
        self,
        *,
        extractions: tuple[SilverExtraction, ...],
        requests: tuple[CorrectionRequest, ...],
        reviewer: str,
    ) -> CorrectionOutcome:
        if not reviewer.strip():
            raise ValueError("corrections require an identified reviewer")
        if not requests:
            raise ValueError("no corrections supplied")
        by_id = {row.extraction_id: row for row in extractions}
        duplicates = _duplicate_ids(requests)
        if duplicates:
            raise ValueError(f"duplicate corrections for: {', '.join(sorted(duplicates))}")
        unknown = [req.extraction_id for req in requests if req.extraction_id not in by_id]
        if unknown:
            raise ValueError(f"unknown extraction ids: {', '.join(sorted(unknown))}")

        decided_at = datetime.now(UTC)
        updated = dict(by_id)
        records: list[CorrectionRecord] = []
        for request in requests:
            original = by_id[request.extraction_id]
            revised = _apply_one(original, request, reviewer)
            updated[request.extraction_id] = revised
            records.append(
                CorrectionRecord(
                    doc_id=original.doc_id,
                    extraction_id=original.extraction_id,
                    field_path=original.field_path,
                    action=request.action,
                    reviewer=reviewer,
                    decided_at=decided_at,
                    previous_status=original.validator_status,
                    previous_value=original.effective_value,
                    corrected_value=request.corrected_value,
                    note=request.note,
                )
            )
        # Preserve original ordering of the packet.
        rows = tuple(updated[row.extraction_id] for row in extractions)
        return CorrectionOutcome(rows=rows, records=tuple(records))


def _apply_one(
    row: SilverExtraction,
    request: CorrectionRequest,
    reviewer: str,
) -> SilverExtraction:
    if request.action is CorrectionAction.CONFIRM:
        return replace(
            row,
            validator_status=ValidatorStatus.CONFIRMED,
            corrected_value=None,
            corrected_by=None,
        )
    if request.action is CorrectionAction.CORRECT:
        assert request.corrected_value is not None  # guarded by CorrectionRequest
        return replace(
            row,
            validator_status=ValidatorStatus.CORRECTED,
            corrected_value=request.corrected_value,
            corrected_by=reviewer,
        )
    # DISPUTE: flag for follow-up; the note is retained in the correction log.
    return replace(
        row,
        validator_status=ValidatorStatus.DISPUTED,
        corrected_value=None,
        corrected_by=None,
    )


def _duplicate_ids(requests: tuple[CorrectionRequest, ...]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for request in requests:
        if request.extraction_id in seen:
            duplicates.add(request.extraction_id)
        seen.add(request.extraction_id)
    return duplicates
