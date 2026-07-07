from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from document_refinery.application.corrections import CorrectionAction, CorrectionRequest
from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.infrastructure.review_timing import (
    ReviewTiming,
    ReviewTimingLog,
    summarize_timings,
)

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


def _timing(doc_id: str, seconds: float) -> ReviewTiming:
    return ReviewTiming(
        doc_id=doc_id,
        reviewer="joshua",
        seconds=seconds,
        action_count=1,
        decided_at=datetime(2026, 7, 7, tzinfo=UTC),
    )


def test_summarize_empty_is_not_meeting_target() -> None:
    summary = summarize_timings(())
    assert summary.count == 0
    assert summary.meets_target is False


def test_summarize_flags_over_target_document() -> None:
    summary = summarize_timings(
        (_timing("a", 5 * 60), _timing("b", 10 * 60), _timing("c", 20 * 60))
    )
    assert summary.count == 3
    assert summary.median_minutes == 10.0
    assert summary.max_minutes == 20.0
    assert summary.within_target_count == 2  # the 20-minute review misses
    assert summary.meets_target is False


def test_summarize_meets_target_when_all_within() -> None:
    summary = summarize_timings((_timing("a", 5 * 60), _timing("b", 14 * 60)))
    assert summary.meets_target is True


def test_review_timing_log_roundtrip(tmp_path: Path) -> None:
    log = ReviewTimingLog(tmp_path / "timings.jsonl")
    log.append(_timing("a", 61.5))
    log.append(_timing("b", 120.0))
    stored = log.read_all()
    assert [t.doc_id for t in stored] == ["a", "b"]
    assert stored[0].seconds == 61.5


def test_pipeline_records_review_time(tmp_path: Path) -> None:
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
                CorrectionRequest(extraction_id=target, action=CorrectionAction.CONFIRM),
            ),
            reviewer="joshua",
            review_seconds=420.0,
        )
        timings, summary = pipeline.review_timings()
        assert len(timings) == 1
        assert timings[0].doc_id == doc_id
        assert timings[0].seconds == 420.0
        assert summary.meets_target is True  # 7 minutes ≤ 15
    finally:
        pipeline.close()


def test_pipeline_skips_timing_when_not_supplied(tmp_path: Path) -> None:
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
                CorrectionRequest(extraction_id=target, action=CorrectionAction.CONFIRM),
            ),
            reviewer="joshua",
        )
        timings, _ = pipeline.review_timings()
        assert timings == ()
    finally:
        pipeline.close()
