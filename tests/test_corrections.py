from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from document_refinery.application.corrections import (
    CorrectionAction,
    CorrectionRequest,
    CorrectionService,
)
from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.domain.models import (
    SilverExtraction,
    ValidatorStatus,
    ValueType,
)
from document_refinery.infrastructure.correction_log import CorrectionLog
from document_refinery.infrastructure.tasks import TaskStatus

TEXT = """Collateral Eligibility Schedule
Eligible Collateral
Counterparty: Atlas Bank
Agreement ID: AGR-001
Schedule Version: 2026-01
Margin Type: VM
Valid From: 2026-01-01
""" + (
    "Asset: GOVT_US | Eligible: yes | Haircut: 2% | Concentration Limit: 100% "
    "| Concentration Basis: market value | Currencies: USD, EUR | Rating Floor: AA- "
    "| Tenor Cap Days: 3650\n"
)


def test_request_validation_requires_value_and_note() -> None:
    with pytest.raises(ValueError, match="corrected_value"):
        CorrectionRequest(extraction_id="ext-1", action=CorrectionAction.CORRECT)
    with pytest.raises(ValueError, match="note"):
        CorrectionRequest(extraction_id="ext-1", action=CorrectionAction.DISPUTE)


def test_apply_requires_identified_reviewer(
    extraction: Callable[..., SilverExtraction],
) -> None:
    service = CorrectionService()
    with pytest.raises(ValueError, match="identified reviewer"):
        service.apply(
            extractions=(extraction(),),
            requests=(CorrectionRequest(extraction_id="ext-1", action=CorrectionAction.CONFIRM),),
            reviewer="   ",
        )


def test_correction_preserves_raw_lineage(
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(raw_value="US Treasuries", normalized_value="GOVT_US")
    outcome = CorrectionService().apply(
        extractions=(row,),
        requests=(
            CorrectionRequest(
                extraction_id="ext-1",
                action=CorrectionAction.CORRECT,
                corrected_value="GOVT_US_TIPS",
                note="issuer clarified TIPS",
            ),
        ),
        reviewer="joshua",
    )
    revised = outcome.rows[0]
    assert revised.validator_status is ValidatorStatus.CORRECTED
    assert revised.corrected_value == "GOVT_US_TIPS"
    assert revised.corrected_by == "joshua"
    # Original extractor evidence is preserved, not overwritten.
    assert revised.raw_value == "US Treasuries"
    assert revised.normalized_value == "GOVT_US"
    assert revised.effective_value == "GOVT_US_TIPS"
    record = outcome.records[0]
    assert record.previous_value == "GOVT_US"
    assert record.action is CorrectionAction.CORRECT


def test_dispute_and_unknown_and_duplicate_ids(
    extraction: Callable[..., SilverExtraction],
) -> None:
    service = CorrectionService()
    row = extraction()
    disputed = service.apply(
        extractions=(row,),
        requests=(
            CorrectionRequest(
                extraction_id="ext-1",
                action=CorrectionAction.DISPUTE,
                note="haircut conflicts with rating band",
            ),
        ),
        reviewer="joshua",
    ).rows[0]
    assert disputed.validator_status is ValidatorStatus.DISPUTED
    assert disputed.corrected_value is None

    with pytest.raises(ValueError, match="unknown extraction ids"):
        service.apply(
            extractions=(row,),
            requests=(CorrectionRequest(extraction_id="ext-9", action=CorrectionAction.CONFIRM),),
            reviewer="joshua",
        )
    with pytest.raises(ValueError, match="duplicate corrections"):
        service.apply(
            extractions=(row,),
            requests=(
                CorrectionRequest(extraction_id="ext-1", action=CorrectionAction.CONFIRM),
                CorrectionRequest(extraction_id="ext-1", action=CorrectionAction.CONFIRM),
            ),
            reviewer="joshua",
        )


def test_correction_log_round_trips(
    tmp_path: Path,
    extraction: Callable[..., SilverExtraction],
) -> None:
    outcome = CorrectionService().apply(
        extractions=(extraction(),),
        requests=(
            CorrectionRequest(
                extraction_id="ext-1",
                action=CorrectionAction.DISPUTE,
                note="needs owner review",
            ),
        ),
        reviewer="joshua",
    )
    log = CorrectionLog(tmp_path / "corrections")
    log.append("doc-1", outcome.records)
    # Appends accumulate rather than overwrite.
    log.append("doc-1", outcome.records)
    stored = log.read("doc-1")
    assert len(stored) == 2
    assert stored[0].note == "needs owner review"
    assert stored[0].reviewer == "joshua"
    assert log.read("missing") == ()


def test_pipeline_dispute_blocks_then_correction_unblocks_gate_a(tmp_path: Path) -> None:
    source = tmp_path / "schedule.txt"
    source.write_text(TEXT, encoding="utf-8")
    pipeline = RefineryPipeline(tmp_path / "workspace")
    try:
        result = pipeline.run(source, source="test")
        doc_id = result.document.doc_id
        target = result.silver_rows[0].extraction_id

        pipeline.apply_corrections(
            doc_id,
            requests=(
                CorrectionRequest(
                    extraction_id=target,
                    action=CorrectionAction.DISPUTE,
                    note="value contradicts the clause",
                ),
            ),
            reviewer="joshua",
        )
        assert pipeline.tasks.get(doc_id).status is TaskStatus.GATE_A_PENDING
        with pytest.raises(ValueError, match="disputed"):
            pipeline.approve(doc_id, approved_by="joshua")

        # Resolving the dispute (confirm) re-opens approval; reviewed stage wins.
        pipeline.apply_corrections(
            doc_id,
            requests=(
                CorrectionRequest(extraction_id=target, action=CorrectionAction.CONFIRM),
            ),
            reviewer="joshua",
        )
        gold_rows = pipeline.approve(doc_id, approved_by="joshua")
        assert gold_rows
        assert pipeline.tasks.get(doc_id).status is TaskStatus.GOLD_LANDED
        # Both actions are durably recorded.
        assert len(pipeline.correction_log.read(doc_id)) == 2
    finally:
        pipeline.close()


def test_apply_corrections_requires_gate_a_pending(tmp_path: Path) -> None:
    source = tmp_path / "schedule.txt"
    source.write_text(TEXT, encoding="utf-8")
    pipeline = RefineryPipeline(tmp_path / "workspace")
    try:
        result = pipeline.run(source, source="test", approved_by="joshua")
        with pytest.raises(ValueError, match="not awaiting Gate A"):
            pipeline.apply_corrections(
                result.document.doc_id,
                requests=(
                    CorrectionRequest(
                        extraction_id=result.silver_rows[0].extraction_id,
                        action=CorrectionAction.CONFIRM,
                    ),
                ),
                reviewer="joshua",
            )
    finally:
        pipeline.close()


def test_interactive_review_packet_exposes_controls(tmp_path: Path) -> None:
    source = tmp_path / "schedule.txt"
    source.write_text(TEXT, encoding="utf-8")
    pipeline = RefineryPipeline(tmp_path / "workspace")
    try:
        result = pipeline.run(source, source="test")
        markup = result.review_html.read_text(encoding="utf-8")
        assert 'class="action"' in markup
        assert "collectCorrections" in markup
        assert "data-extraction-id" in markup
        # doc_id is embedded as a JSON literal for the exporter.
        assert json.dumps(result.document.doc_id) in markup
    finally:
        pipeline.close()


def test_not_found_row_can_be_corrected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    row = extraction(
        value_type=ValueType.NOT_FOUND,
        normalized_value="not_found",
        raw_value="not_found",
        validator_status=ValidatorStatus.CONFIRMED,
    )
    outcome = CorrectionService().apply(
        extractions=(row,),
        requests=(
            CorrectionRequest(
                extraction_id="ext-1",
                action=CorrectionAction.CORRECT,
                corrected_value="AA-",
            ),
        ),
        reviewer="joshua",
    )
    revised = outcome.rows[0]
    assert revised.effective_value == "AA-"
    assert revised.value_type is ValueType.NOT_FOUND
