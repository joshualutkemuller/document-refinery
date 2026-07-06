from __future__ import annotations

from pathlib import Path

from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.infrastructure.tasks import TaskStatus
from document_refinery.quality.regression import run_packaged_regression
from document_refinery.quality.reporting import QualityReporter

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


def test_pipeline_stops_at_gate_a_without_owner_approval(tmp_path: Path) -> None:
    source = tmp_path / "schedule.txt"
    source.write_text(TEXT, encoding="utf-8")
    pipeline = RefineryPipeline(tmp_path / "workspace")
    try:
        result = pipeline.run(source, source="test")
        assert result.gate_decision is None
        assert not result.gold_rows
        assert result.review_html.exists()
        assert pipeline.tasks.get(result.document.doc_id).status is TaskStatus.GATE_A_PENDING
        gold_rows = pipeline.approve(result.document.doc_id, approved_by="owner")
        assert len(gold_rows) == 1
        assert pipeline.tasks.get(result.document.doc_id).status is TaskStatus.GOLD_LANDED
    finally:
        pipeline.close()


def test_pipeline_lands_traceable_gold_after_gate_a(tmp_path: Path) -> None:
    source = tmp_path / "schedule.txt"
    source.write_text(TEXT, encoding="utf-8")
    pipeline = RefineryPipeline(tmp_path / "workspace")
    try:
        result = pipeline.run(source, source="test", approved_by="owner")
        assert result.gate_decision and result.gate_decision.approved
        assert len(result.gold_rows) == 1
        assert result.gold_rows[0].silver_extraction_ids
        assert pipeline.tasks.get(result.document.doc_id).status is TaskStatus.GOLD_LANDED
    finally:
        pipeline.close()


def test_packaged_regression_is_technically_ready_but_not_owner_verified() -> None:
    result = run_packaged_regression()
    assert result.report.field_accuracy == 1.0
    assert result.report.technical_regression_ready()
    assert not result.report.phase_one_release_ready()
    assert result.disputed_fields == 0


def test_quality_report_has_all_three_altitudes(extraction) -> None:
    report = QualityReporter().build((extraction(),))
    assert "Processed 1 document" in report.executive_briefing
    assert report.dashboard_payload["field_count"] == 1
    assert report.audit_appendix[0]["source_locator"]
