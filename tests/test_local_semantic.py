from __future__ import annotations

from pathlib import Path

import pytest

from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.cli import _build_semantic_components
from document_refinery.domain.models import ValidatorStatus, ValueType
from document_refinery.infrastructure.tasks import TaskStatus

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "example_schedules"
    / "Example6_synthetic-triparty-eligibility-profile.txt"
)
FED_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "example_schedules"
    / "fed-discount-window-collateral-valuation.pdf"
)


def _components():
    return _build_semantic_components(
        provider="local",
        extractor_model=None,
        validator_model=None,
        schema_version="eligibility-1.0.0",
        constitution_version="eligibility-1.1.0",
        timeout_seconds=5.0,
        max_retries=0,
    )


def test_local_provider_uses_separate_sessions() -> None:
    extractor, validator = _components()
    assert extractor is not None and validator is not None
    assert extractor.model.provider == "local"
    assert extractor.model.session_id != validator.model.session_id


def test_local_extraction_produces_verbatim_silver() -> None:
    extractor, _ = _components()
    assert extractor is not None
    text = FIXTURE.read_text(encoding="utf-8")
    result = extractor.extract(
        doc_id="doc-x", doc_class="collateral_eligibility_schedule", text=text
    )
    assert result.rows
    haircut = next(r for r in result.rows if r.field_path == "eligibility[0].haircut_pct")
    assert haircut.value_type is ValueType.PERCENTAGE
    assert haircut.normalized_value == "1.5"
    # Every found value's clause is verbatim document text (lineage integrity).
    for row in result.rows:
        if row.value_type is not ValueType.NOT_FOUND:
            assert row.source_clause in text


def test_local_validation_confirms_every_row() -> None:
    extractor, validator = _components()
    assert extractor is not None and validator is not None
    text = FIXTURE.read_text(encoding="utf-8")
    extracted = extractor.extract(
        doc_id="doc-x", doc_class="collateral_eligibility_schedule", text=text
    )
    validation = validator.validate(
        doc_id="doc-x",
        text=text,
        extractions=extracted.rows,
        extractor_session_id=extractor.model.session_id,
    )
    assert len(validation.rows) == len(extracted.rows)
    assert all(r.validator_status is ValidatorStatus.CONFIRMED for r in validation.rows)


def test_pipeline_runs_unknown_layout_to_gate_a_with_local_provider(tmp_path: Path) -> None:
    extractor, validator = _components()
    pipeline = RefineryPipeline(
        tmp_path / "ws",
        semantic_extractor=extractor,
        semantic_validator=validator,
    )
    try:
        result = pipeline.run(FIXTURE, source="demo")
        assert result.silver_rows
        assert pipeline.tasks.get(result.document.doc_id).status is TaskStatus.GATE_A_PENDING
        # Two independent semantic sessions were recorded in the audit trail.
        calls = list((tmp_path / "ws" / "model_calls").glob("*.jsonl"))
        assert calls, "semantic call audit should be written"
    finally:
        pipeline.close()


def test_failed_promotion_leaves_task_recoverable(tmp_path: Path) -> None:
    # The synthetic doc has no margin_type/schedule_version, so gold promotion
    # is blocked. The task must stay at gate_a_pending (recoverable) rather than
    # getting stuck in gate_a_approved.
    from document_refinery.application.promotion import PromotionError

    extractor, validator = _components()
    pipeline = RefineryPipeline(
        tmp_path / "ws",
        semantic_extractor=extractor,
        semantic_validator=validator,
    )
    try:
        result = pipeline.run(FIXTURE, source="demo")
        doc_id = result.document.doc_id
        with pytest.raises(PromotionError, match="missing required fields"):
            pipeline.approve(doc_id, approved_by="Joshua")
        assert pipeline.tasks.get(doc_id).status is TaskStatus.GATE_A_PENDING
    finally:
        pipeline.close()


def test_local_provider_rejects_unrecognizable_text() -> None:
    extractor, _ = _components()
    assert extractor is not None
    with pytest.raises(ValueError, match="no recognizable schedule structure"):
        extractor.extract(
            doc_id="doc-x",
            doc_class="collateral_eligibility_schedule",
            text="This document has no schedule structure at all.",
        )


def test_fed_margin_pdf_routes_to_gate_a_with_local_provider(tmp_path: Path) -> None:
    pytest.importorskip("pypdf")
    extractor, validator = _components()
    pipeline = RefineryPipeline(
        tmp_path / "ws-fed",
        semantic_extractor=extractor,
        semantic_validator=validator,
    )
    try:
        result = pipeline.run(FED_FIXTURE, source="public-example")
        assert result.silver_rows
        assert result.silver_rows[0].doc_class == "collateral_valuation_margin_table"
        assert any(
            row.field_path.endswith(".collateral_value_pct")
            for row in result.silver_rows
        )
        assert all(
            row.validator_status is ValidatorStatus.CONFIRMED
            for row in result.silver_rows
        )
        assert pipeline.tasks.get(result.document.doc_id).status is TaskStatus.GATE_A_PENDING
    finally:
        pipeline.close()
