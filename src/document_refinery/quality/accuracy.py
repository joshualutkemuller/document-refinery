"""Accuracy measurement against a golden corpus of documents + human ground truth.

This is the N4 evidence harness: it runs a corpus of collateral schedules through
the deterministic extractor/validator and scores the normalized output against
*independently authored* ground truth, so the number reflects real extractor
quality — not the extractor grading itself. It reports field-level accuracy,
found-value accuracy, locator coverage, per-field and per-document breakdowns, a
list of concrete mismatches, and the Phase-1 release gate.

The same harness measures owner-verified real documents once supplied: drop the
files and their verified ground truth into the corpus directory and re-run.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from document_refinery.agents.eligibility import (
    EligibilityAdversarialValidator,
    EligibilityScheduleExtractor,
)
from document_refinery.agents.semantic import SemanticExtractor, SemanticValidator
from document_refinery.domain.models import SilverExtraction

DEFAULT_DOC_CLASS = "collateral_eligibility_schedule"

# A row provider turns one golden case into the silver rows to be scored, so the
# scoring math is identical whether rows come from the deterministic eligibility
# route or the semantic route.
RowProvider = Callable[["GoldenCase"], "tuple[SilverExtraction, ...]"]


@dataclass(frozen=True, slots=True)
class GoldenCase:
    case_id: str
    text: str
    expected: dict[str, str]  # field_path -> human-correct normalized value
    owner_verified: bool = False
    title: str = ""
    doc_class: str = DEFAULT_DOC_CLASS


@dataclass(frozen=True, slots=True)
class Mismatch:
    case_id: str
    field_path: str
    expected: str
    actual: str


@dataclass(frozen=True, slots=True)
class AccuracyReport:
    document_count: int
    owner_verified_document_count: int
    total_fields: int
    correct_fields: int
    found_fields: int
    correct_found_fields: int
    fields_with_locator: int
    dispute_count: int
    per_field: dict[str, tuple[int, int]] = field(default_factory=dict)
    per_document: dict[str, tuple[int, int]] = field(default_factory=dict)
    mismatches: tuple[Mismatch, ...] = ()

    @property
    def field_accuracy(self) -> float:
        return self.correct_fields / self.total_fields if self.total_fields else 0.0

    @property
    def found_accuracy(self) -> float:
        return self.correct_found_fields / self.found_fields if self.found_fields else 0.0

    @property
    def locator_coverage(self) -> float:
        return self.fields_with_locator / self.found_fields if self.found_fields else 0.0

    def release_ready(self) -> bool:
        return (
            self.document_count >= 10
            and self.owner_verified_document_count >= 10
            and self.field_accuracy >= 0.95
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "document_count": self.document_count,
            "owner_verified_document_count": self.owner_verified_document_count,
            "total_fields": self.total_fields,
            "correct_fields": self.correct_fields,
            "field_accuracy": round(self.field_accuracy, 4),
            "found_accuracy": round(self.found_accuracy, 4),
            "locator_coverage": round(self.locator_coverage, 4),
            "dispute_count": self.dispute_count,
            "per_field_accuracy": {
                name: round(correct / total, 4) if total else 0.0
                for name, (correct, total) in sorted(self.per_field.items())
            },
            "per_document_accuracy": {
                doc: round(correct / total, 4) if total else 0.0
                for doc, (correct, total) in sorted(self.per_document.items())
            },
            "mismatches": [
                {
                    "case_id": m.case_id,
                    "field_path": m.field_path,
                    "expected": m.expected,
                    "actual": m.actual,
                }
                for m in self.mismatches
            ],
            "release_ready": self.release_ready(),
        }


def deterministic_row_provider() -> RowProvider:
    """Score with the deterministic eligibility extractor/validator (the default)."""
    extractor = EligibilityScheduleExtractor()
    validator = EligibilityAdversarialValidator()

    def provide(case: GoldenCase) -> tuple[SilverExtraction, ...]:
        return validator.validate(
            text=case.text,
            extractions=extractor.extract(doc_id=case.case_id, text=case.text),
        )

    return provide


def semantic_row_provider(
    extractor: SemanticExtractor,
    validator: SemanticValidator,
    *,
    language: str = "und",
) -> RowProvider:
    """Score the semantic route: routes each case by its doc_class through the
    configured extractor and an independent validator (same split as production).
    """

    def provide(case: GoldenCase) -> tuple[SilverExtraction, ...]:
        extraction = extractor.extract(
            doc_id=case.case_id,
            doc_class=case.doc_class,
            text=case.text,
            language=language,
        )
        validation = validator.validate(
            doc_id=case.case_id,
            text=case.text,
            extractions=extraction.rows,
            extractor_session_id=extractor.model.session_id,
            language=language,
        )
        return validation.rows

    return provide


def score_corpus(
    cases: tuple[GoldenCase, ...], *, row_provider: RowProvider | None = None
) -> AccuracyReport:
    provide = row_provider or deterministic_row_provider()

    total = correct = found = correct_found = with_locator = disputes = 0
    per_field: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    per_document: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    mismatches: list[Mismatch] = []
    verified_docs: set[str] = set()

    for case in cases:
        if case.owner_verified:
            verified_docs.add(case.case_id)
        rows = provide(case)
        actual = {row.field_path: row.normalized_value for row in rows}
        located = {
            row.field_path
            for row in rows
            if row.source_locator and "unresolved" not in row.source_locator
        }
        disputes += sum(row.validator_status.value == "disputed" for row in rows)

        for field_path, expected_value in case.expected.items():
            suffix = field_path.rsplit(".", 1)[-1]
            actual_value = actual.get(field_path, "<missing>")
            is_correct = actual_value == expected_value
            total += 1
            per_field[suffix][1] += 1
            per_document[case.case_id][1] += 1
            if is_correct:
                correct += 1
                per_field[suffix][0] += 1
                per_document[case.case_id][0] += 1
            else:
                mismatches.append(
                    Mismatch(case.case_id, field_path, expected_value, actual_value)
                )
            if expected_value != "not_found":
                found += 1
                if is_correct:
                    correct_found += 1
                if field_path in located:
                    with_locator += 1

    return AccuracyReport(
        document_count=len(cases),
        owner_verified_document_count=len(verified_docs),
        total_fields=total,
        correct_fields=correct,
        found_fields=found,
        correct_found_fields=correct_found,
        fields_with_locator=with_locator,
        dispute_count=disputes,
        per_field={k: (v[0], v[1]) for k, v in per_field.items()},
        per_document={k: (v[0], v[1]) for k, v in per_document.items()},
        mismatches=tuple(mismatches),
    )


def load_corpus(directory: Path) -> tuple[GoldenCase, ...]:
    """Load a corpus of ``*.txt`` schedules described by ``ground_truth.json``."""
    ground_truth = json.loads((directory / "ground_truth.json").read_text(encoding="utf-8"))
    cases: list[GoldenCase] = []
    for case_id, meta in sorted(ground_truth.items()):
        text = (directory / f"{case_id}.txt").read_text(encoding="utf-8")
        cases.append(
            GoldenCase(
                case_id=case_id,
                text=text,
                expected={str(k): str(v) for k, v in meta["expected"].items()},
                owner_verified=bool(meta.get("owner_verified", False)),
                title=str(meta.get("title", "")),
                doc_class=str(meta.get("doc_class", DEFAULT_DOC_CLASS)),
            )
        )
    return tuple(cases)
