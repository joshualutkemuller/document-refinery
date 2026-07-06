from __future__ import annotations

from datetime import datetime

import pytest

from document_refinery.application.promotion import (
    EligibilityPromotion,
    InMemoryBitemporalHistory,
    PromotionError,
)


def rows(extraction):
    values = {
        "counterparty": "Counterparty A",
        "agreement_id": "AGR-1",
        "schedule_version": "2026-01",
        "margin_type": "VM",
        "asset_criterion": "GOVT_US",
        "eligible": "true",
        "haircut_pct": "2.0",
        "currency_scope": "USD, EUR",
        "valid_from": "2026-01-01",
    }
    return [
        extraction(
            extraction_id=f"ext-{index}",
            field_path=f"eligibility[0].{field}",
            normalized_value=value,
        )
        for index, (field, value) in enumerate(values.items())
    ]


def test_promotes_only_validated_silver_with_complete_lineage(extraction) -> None:
    gold = EligibilityPromotion().promote(
        rows(extraction), knowledge_from=datetime(2026, 7, 5, 12)
    )
    assert gold.asset_criterion == "GOVT_US"
    assert gold.currency_scope == ("USD", "EUR")
    assert len(gold.silver_extraction_ids) == 9


def test_ambiguous_row_blocks_promotion(extraction) -> None:
    silver = rows(extraction)
    silver[0] = extraction(
        extraction_id="ambiguous",
        field_path="eligibility[0].counterparty",
        normalized_value="Counterparty A",
        ambiguity_flag=True,
        ambiguity_note="Header could apply to either entity.",
    )
    with pytest.raises(PromotionError, match="confirmed and unambiguous"):
        EligibilityPromotion().promote(silver, knowledge_from=datetime(2026, 7, 5))


def test_bitemporal_upsert_closes_prior_knowledge_version(extraction) -> None:
    promotion = EligibilityPromotion()
    first = promotion.promote(rows(extraction), knowledge_from=datetime(2026, 7, 1))
    second = promotion.promote(rows(extraction), knowledge_from=datetime(2026, 7, 5))
    history = InMemoryBitemporalHistory()
    history.upsert(first)
    history.upsert(second)
    assert history.records[0].knowledge_to == datetime(2026, 7, 5)
    assert history.records[1].knowledge_to is None
