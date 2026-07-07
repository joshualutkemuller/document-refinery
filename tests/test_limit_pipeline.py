from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from document_refinery.application.limit_consistency import LimitConsistencyError
from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.domain.models import SilverExtraction
from document_refinery.infrastructure.records import (
    GoldLimitStore,
    GoldMarginRequirementStore,
)
from document_refinery.infrastructure.tasks import TaskStatus


def _seed_gate_a(
    pipeline: RefineryPipeline, doc_id: str, rows: tuple[SilverExtraction, ...]
) -> None:
    pipeline.silver.write(rows, stage="validated")
    pipeline.tasks.create(doc_id)
    for status in (
        TaskStatus.CLASSIFIED,
        TaskStatus.EXTRACTED,
        TaskStatus.VALIDATED,
        TaskStatus.GATE_A_PENDING,
    ):
        pipeline.tasks.transition(doc_id, status)


def _limit_rows(
    extraction: Callable[..., SilverExtraction],
    index: int,
    fields: dict[str, str],
    *,
    doc_id: str,
    currency: str | None = None,
) -> list[SilverExtraction]:
    rows: list[SilverExtraction] = []
    for suffix, value in fields.items():
        path = f"limit[{index}].{suffix}"
        rows.append(
            extraction(
                extraction_id=f"{doc_id}:{path}",
                doc_id=doc_id,
                doc_class="collateral_rule_schedule",
                field_path=path,
                normalized_value=value,
                currency=currency if suffix == "limit_value" else None,
            )
        )
    return rows


def test_approve_lands_limits_when_limit_store_configured(
    tmp_path: Path, extraction: Callable[..., SilverExtraction]
) -> None:
    doc_id = "doc-limit-1"
    limit_path = tmp_path / "gold" / "collateral_limits.jsonl"
    pipeline = RefineryPipeline(tmp_path / "ws", limit_store=GoldLimitStore(limit_path))
    try:
        rows = tuple(
            _limit_rows(
                extraction,
                0,
                {"dimension": "sector", "scope_value": "Technology", "limit_value": "10",
                 "limit_unit": "percent", "basis": "post_haircut_value"},
                doc_id=doc_id,
            )
        )
        _seed_gate_a(pipeline, doc_id, rows)

        gold_rows = pipeline.approve(doc_id, approved_by="joshua")
        assert gold_rows == ()  # no eligibility rows in a pure limit doc
        assert len(pipeline.last_landed_limits) == 1
        assert pipeline.last_landed_limits[0].dimension == "sector"
        assert pipeline.tasks.get(doc_id).status is TaskStatus.GOLD_LANDED
        # Landed durably in the limit store.
        reloaded = GoldLimitStore(limit_path)
        assert len(reloaded.history.records) == 1
    finally:
        pipeline.close()


def test_approve_without_limit_store_ignores_limit_rows(
    tmp_path: Path, extraction: Callable[..., SilverExtraction]
) -> None:
    doc_id = "doc-limit-2"
    pipeline = RefineryPipeline(tmp_path / "ws")  # no limit_store
    try:
        rows = tuple(
            _limit_rows(
                extraction,
                0,
                {"dimension": "sector", "limit_value": "10", "limit_unit": "percent",
                 "basis": "market_value"},
                doc_id=doc_id,
            )
        )
        _seed_gate_a(pipeline, doc_id, rows)
        pipeline.approve(doc_id, approved_by="joshua")
        assert pipeline.last_landed_limits == ()
        assert pipeline.tasks.get(doc_id).status is TaskStatus.GOLD_LANDED
    finally:
        pipeline.close()


def test_approve_lands_margin_when_margin_store_configured(
    tmp_path: Path, extraction: Callable[..., SilverExtraction]
) -> None:
    doc_id = "doc-margin-1"
    margin_path = tmp_path / "gold" / "margin_requirements.jsonl"
    pipeline = RefineryPipeline(
        tmp_path / "ws", margin_store=GoldMarginRequirementStore(margin_path)
    )
    try:
        rows = tuple(
            extraction(
                extraction_id=f"{doc_id}:requirement[0].{suffix}",
                doc_id=doc_id,
                doc_class="margin_requirement",
                field_path=f"requirement[0].{suffix}",
                normalized_value=value,
            )
            for suffix, value in {
                "counterparty": "Bank A",
                "margin_type": "IM",
                "required_amount": "24500000",
                "currency": "USD",
            }.items()
        )
        _seed_gate_a(pipeline, doc_id, rows)
        pipeline.approve(doc_id, approved_by="joshua")
        assert len(pipeline.last_landed_margin) == 1
        assert pipeline.last_landed_margin[0].counterparty == "Bank A"
        assert pipeline.tasks.get(doc_id).status is TaskStatus.GOLD_LANDED
        assert len(GoldMarginRequirementStore(margin_path).history.records) == 1
    finally:
        pipeline.close()


def test_inconsistent_limit_blocks_approval_and_stays_recoverable(
    tmp_path: Path, extraction: Callable[..., SilverExtraction]
) -> None:
    doc_id = "doc-limit-3"
    pipeline = RefineryPipeline(
        tmp_path / "ws", limit_store=GoldLimitStore(tmp_path / "gold" / "limits.jsonl")
    )
    try:
        rows = tuple(
            _limit_rows(
                extraction,
                0,
                {"dimension": "issuer", "limit_value": "50000000", "limit_unit": "absolute"},
                doc_id=doc_id,  # absolute with no currency -> inconsistent
            )
        )
        _seed_gate_a(pipeline, doc_id, rows)
        with pytest.raises(LimitConsistencyError, match="missing_currency"):
            pipeline.approve(doc_id, approved_by="joshua")
        # Fails closed: document remains recoverable at Gate A.
        assert pipeline.tasks.get(doc_id).status is TaskStatus.GATE_A_PENDING
    finally:
        pipeline.close()
