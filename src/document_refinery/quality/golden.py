"""Golden-set scoring and Phase 1 release gates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoldenField:
    doc_id: str
    field_path: str
    expected_value: str


@dataclass(frozen=True, slots=True)
class GoldenSetReport:
    total_fields: int
    correct_fields: int
    document_count: int

    @property
    def field_accuracy(self) -> float:
        return self.correct_fields / self.total_fields if self.total_fields else 0.0

    def phase_one_release_ready(self) -> bool:
        return self.document_count >= 10 and self.field_accuracy >= 0.95


def evaluate_golden_set(
    expected: Iterable[GoldenField],
    actual: Mapping[tuple[str, str], str],
) -> GoldenSetReport:
    fields = tuple(expected)
    correct = sum(
        actual.get((field.doc_id, field.field_path)) == field.expected_value for field in fields
    )
    return GoldenSetReport(
        total_fields=len(fields),
        correct_fields=correct,
        document_count=len({field.doc_id for field in fields}),
    )
