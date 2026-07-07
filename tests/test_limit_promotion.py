from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from document_refinery.application.limit_promotion import LimitPromotion
from document_refinery.application.promotion import PromotionError
from document_refinery.domain.models import (
    LimitUnit,
    SilverExtraction,
    ValidatorStatus,
    ValueType,
)

_KNOWLEDGE = datetime(2026, 7, 7, tzinfo=UTC)


def _rows(
    extraction: Callable[..., SilverExtraction],
    fields: dict[str, str],
    *,
    index: int = 0,
    currency: str | None = None,
    doc_id: str = "doc-1",
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


def test_promote_scoped_percent_limit(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {
            "dimension": "sector",
            "scope_value": "Technology",
            "limit_value": "10",
            "limit_unit": "percent",
            "basis": "post_haircut_value",
            "aggregation": "posted_collateral",
        },
    )
    (limit,) = LimitPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
    assert limit.dimension == "sector"
    assert limit.scope_value == "Technology"
    assert limit.limit_value == 10.0
    assert limit.limit_unit is LimitUnit.PERCENT
    assert limit.basis == "post_haircut_value"
    assert limit.aggregation == "posted_collateral"
    assert limit.silver_extraction_ids  # lineage preserved


def test_promote_absolute_limit_takes_currency_from_value_row(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"dimension": "issuer", "limit_value": "50000000", "limit_unit": "absolute"},
        currency="USD",
    )
    (limit,) = LimitPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
    assert limit.limit_unit is LimitUnit.ABSOLUTE
    assert limit.limit_value == 50000000.0
    assert limit.limit_currency == "USD"


def test_promote_multiple_limits_sorted_by_index_with_shared_identity(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"dimension": "sector", "scope_value": "Technology", "limit_value": "10",
         "limit_unit": "percent"},
        index=0,
    )
    rows += _rows(
        extraction,
        {"dimension": "credit_quality", "scope_value": "BBB", "limit_value": "20",
         "limit_unit": "percent"},
        index=1,
    )
    rows.append(
        extraction(
            extraction_id="doc-1:counterparty",
            field_path="counterparty",
            normalized_value="Atlas Bank",
        )
    )
    limits = LimitPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
    assert [limit.dimension for limit in limits] == ["sector", "credit_quality"]
    assert all(limit.counterparty == "Atlas Bank" for limit in limits)
    # Shared identity row is folded into each limit's lineage.
    assert all("doc-1:counterparty" in limit.silver_extraction_ids for limit in limits)


def test_absolute_limit_without_currency_is_rejected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"dimension": "issuer", "limit_value": "50000000", "limit_unit": "absolute"},
    )
    with pytest.raises(ValueError, match="absolute limits require a limit_currency"):
        LimitPromotion().promote(rows, knowledge_from=_KNOWLEDGE)


def test_percent_limit_over_100_is_rejected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"dimension": "sector", "limit_value": "150", "limit_unit": "percent"},
    )
    with pytest.raises(ValueError, match="percent limit_value must be between 0 and 100"):
        LimitPromotion().promote(rows, knowledge_from=_KNOWLEDGE)


def test_missing_dimension_is_rejected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(extraction, {"limit_value": "10", "limit_unit": "percent"})
    with pytest.raises(PromotionError, match="requires a dimension"):
        LimitPromotion().promote(rows, knowledge_from=_KNOWLEDGE)


def test_unconfirmed_rows_are_rejected(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"dimension": "sector", "limit_value": "10", "limit_unit": "percent"},
    )
    pending = [
        SilverExtraction(
            **{
                **{f.name: getattr(row, f.name) for f in row.__dataclass_fields__.values()},
                "validator_status": ValidatorStatus.PENDING,
            }
        )
        for row in rows
    ]
    with pytest.raises(PromotionError, match="must be confirmed"):
        LimitPromotion().promote(pending, knowledge_from=_KNOWLEDGE)


def test_not_found_limit_rows_are_skipped(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _rows(
        extraction,
        {"dimension": "sector", "limit_value": "10", "limit_unit": "percent"},
    )
    rows.append(
        extraction(
            extraction_id="doc-1:limit[0].basis",
            field_path="limit[0].basis",
            normalized_value="not_found",
            value_type=ValueType.NOT_FOUND,
        )
    )
    (limit,) = LimitPromotion().promote(rows, knowledge_from=_KNOWLEDGE)
    assert limit.basis is None
