from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from document_refinery.application.margin_promotion import MarginRequirementPromotion
from document_refinery.application.promotion import PromotionError
from document_refinery.domain.models import MarginType, SilverExtraction

_KNOWLEDGE = datetime(2026, 7, 7, tzinfo=UTC)


def _rows(
    extraction: Callable[..., SilverExtraction],
    fields: dict[str, str],
    *,
    index: int = 0,
    amount_currency: str | None = None,
    doc_id: str = "doc-1",
) -> list[SilverExtraction]:
    rows: list[SilverExtraction] = []
    for suffix, value in fields.items():
        path = f"requirement[{index}].{suffix}"
        rows.append(
            extraction(
                extraction_id=f"{doc_id}:{path}",
                doc_id=doc_id,
                doc_class="margin_requirement",
                field_path=path,
                normalized_value=value,
                currency=amount_currency if suffix == "required_amount" else None,
            )
        )
    return rows


def test_promote_margin_requirement(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {
            "counterparty": "Bank A",
            "margin_type": "IM",
            "required_amount": "24500000",
            "currency": "USD",
            "netting_set_id": "NS-1",
        },
    )
    (req,) = MarginRequirementPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
    assert req.counterparty == "Bank A"
    assert req.margin_type is MarginType.IM
    assert req.required_amount == 24500000.0
    assert req.currency == "USD"
    assert req.netting_set_id == "NS-1"
    assert req.silver_extraction_ids


def test_currency_falls_back_to_amount_row_currency(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"counterparty": "Bank A", "margin_type": "VM", "required_amount": "1000000"},
        amount_currency="EUR",
    )
    (req,) = MarginRequirementPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
    assert req.currency == "EUR"


def test_document_level_model_context_folded_into_each_requirement(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"counterparty": "Bank A", "margin_type": "IM", "required_amount": "5",
         "currency": "USD"},
        index=0,
    )
    rows += _rows(
        extraction,
        {"counterparty": "Bank B", "margin_type": "IM", "required_amount": "7",
         "currency": "USD"},
        index=1,
    )
    rows.append(
        extraction(
            extraction_id="doc-1:model",
            doc_id="doc-1",
            doc_class="margin_requirement",
            field_path="model",
            normalized_value="ISDA SIMM",
        )
    )
    reqs = MarginRequirementPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
    assert [r.counterparty for r in reqs] == ["Bank A", "Bank B"]
    assert all(r.model == "ISDA SIMM" for r in reqs)
    assert all("doc-1:model" in r.silver_extraction_ids for r in reqs)


def test_missing_required_field_rejected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"counterparty": "Bank A", "required_amount": "5", "currency": "USD"},  # no margin_type
    )
    with pytest.raises(PromotionError, match="missing required fields"):
        MarginRequirementPromotion().promote(rows, knowledge_from=_KNOWLEDGE)


def test_missing_currency_rejected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"counterparty": "Bank A", "margin_type": "IM", "required_amount": "5"},
    )
    with pytest.raises(PromotionError, match="missing a currency"):
        MarginRequirementPromotion().promote(rows, knowledge_from=_KNOWLEDGE)


def test_invalid_margin_type_rejected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"counterparty": "Bank A", "margin_type": "Bogus", "required_amount": "5",
         "currency": "USD"},
    )
    with pytest.raises(PromotionError, match="invalid margin_type"):
        MarginRequirementPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
