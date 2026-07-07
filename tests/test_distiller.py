from __future__ import annotations

from datetime import UTC, datetime

from document_refinery.application.corrections import CorrectionAction, CorrectionRecord
from document_refinery.application.distiller import Distiller, schema_of
from document_refinery.domain.models import ValidatorStatus


def _record(
    *,
    doc_id: str,
    field_path: str,
    action: CorrectionAction,
    previous_value: str = "",
    corrected_value: str | None = None,
    reviewer: str = "owner",
    note: str | None = None,
) -> CorrectionRecord:
    return CorrectionRecord(
        doc_id=doc_id,
        extraction_id=f"{doc_id}:{field_path}",
        field_path=field_path,
        action=action,
        reviewer=reviewer,
        decided_at=datetime(2026, 7, 7, tzinfo=UTC),
        previous_status=ValidatorStatus.PENDING,
        previous_value=previous_value,
        corrected_value=corrected_value,
        note=note,
    )


def test_schema_of_strips_record_index_and_field() -> None:
    assert schema_of("eligibility[0].haircut_pct") == "eligibility"
    assert schema_of("valuation_margin[3].margin_pct") == "valuation_margin"
    assert schema_of("scalar_field") == "scalar_field"


def test_repeated_identical_correction_becomes_normalization_rule() -> None:
    records = (
        _record(
            doc_id="doc-a",
            field_path="eligibility[0].rating_floor",
            action=CorrectionAction.CORRECT,
            previous_value="IG",
            corrected_value="Investment Grade",
        ),
        _record(
            doc_id="doc-b",
            field_path="eligibility[2].rating_floor",
            action=CorrectionAction.CORRECT,
            previous_value="IG",
            corrected_value="Investment Grade",
        ),
    )
    report = Distiller().distill(records)

    assert len(report.constitution_rules) == 1
    rule = report.constitution_rules[0]
    assert rule.kind == "normalization"
    assert rule.schema == "eligibility"
    assert rule.field_suffix == "rating_floor"
    assert rule.original_value == "IG"
    assert rule.corrected_value == "Investment Grade"
    assert rule.occurrences == 2
    assert rule.example_doc_ids == ("doc-a", "doc-b")
    # Every correction is also captured as a golden case so none evaporates.
    assert len(report.golden_cases) == 2
    assert {case.expected_value for case in report.golden_cases} == {"Investment Grade"}


def test_one_off_correction_is_golden_case_but_not_a_rule() -> None:
    records = (
        _record(
            doc_id="doc-a",
            field_path="eligibility[0].haircut_pct",
            action=CorrectionAction.CORRECT,
            previous_value="5",
            corrected_value="0.05",
        ),
    )
    report = Distiller().distill(records)

    assert report.constitution_rules == ()
    assert len(report.golden_cases) == 1
    assert report.golden_cases[0].expected_value == "0.05"
    assert report.golden_cases[0].source == "correction"


def test_conflicting_corrections_raise_review_flag() -> None:
    records = (
        _record(
            doc_id="doc-a",
            field_path="eligibility[0].concentration_basis",
            action=CorrectionAction.CORRECT,
            previous_value="MV",
            corrected_value="market value",
        ),
        _record(
            doc_id="doc-b",
            field_path="eligibility[0].concentration_basis",
            action=CorrectionAction.CORRECT,
            previous_value="MV",
            corrected_value="par value",
        ),
    )
    report = Distiller().distill(records)

    assert len(report.constitution_rules) == 1
    rule = report.constitution_rules[0]
    assert rule.kind == "review_flag"
    assert rule.corrected_value is None
    assert "different values" in rule.rationale


def test_dispute_becomes_unresolved_and_review_flag() -> None:
    records = (
        _record(
            doc_id="doc-a",
            field_path="eligibility[1].tenor_cap_days",
            action=CorrectionAction.DISPUTE,
            previous_value="3650",
            note="clause references business days, not calendar days",
        ),
    )
    report = Distiller().distill(records)

    assert len(report.unresolved_disputes) == 1
    assert report.unresolved_disputes[0].note is not None
    assert report.golden_cases == ()
    assert len(report.constitution_rules) == 1
    rule = report.constitution_rules[0]
    assert rule.kind == "review_flag"
    assert "clause references business days, not calendar days" in rule.notes


def test_confirm_becomes_confirmed_golden_case() -> None:
    records = (
        _record(
            doc_id="doc-a",
            field_path="eligibility[0].margin_type",
            action=CorrectionAction.CONFIRM,
            previous_value="VM",
        ),
    )
    report = Distiller().distill(records)

    assert len(report.golden_cases) == 1
    case = report.golden_cases[0]
    assert case.source == "confirmed"
    assert case.expected_value == "VM"
    assert report.constitution_rules == ()


def test_ground_truth_fragment_groups_by_document() -> None:
    records = (
        _record(
            doc_id="doc-a",
            field_path="eligibility[0].haircut_pct",
            action=CorrectionAction.CORRECT,
            previous_value="5",
            corrected_value="0.05",
        ),
        _record(
            doc_id="doc-a",
            field_path="eligibility[0].margin_type",
            action=CorrectionAction.CONFIRM,
            previous_value="VM",
        ),
    )
    fragment = Distiller().distill(records).ground_truth_fragment()

    assert set(fragment) == {"doc-a"}
    assert fragment["doc-a"]["owner_verified"] is False
    assert fragment["doc-a"]["expected"] == {
        "eligibility[0].haircut_pct": "0.05",
        "eligibility[0].margin_type": "VM",
    }
