from __future__ import annotations

from collections.abc import Callable

import pytest

from document_refinery.application.limit_consistency import (
    LimitConsistencyError,
    LimitConsistencyValidator,
)
from document_refinery.domain.models import SilverExtraction


def _limit(
    extraction: Callable[..., SilverExtraction],
    index: int,
    fields: dict[str, str],
    *,
    currency: str | None = None,
) -> list[SilverExtraction]:
    rows: list[SilverExtraction] = []
    for suffix, value in fields.items():
        path = f"limit[{index}].{suffix}"
        rows.append(
            extraction(
                extraction_id=path,
                field_path=path,
                normalized_value=value,
                currency=currency if suffix == "limit_value" else None,
            )
        )
    return rows


def test_consistent_percent_limit_has_no_violations(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "sector", "scope_value": "Technology", "limit_value": "10",
         "limit_unit": "percent", "basis": "post_haircut_value"},
    )
    assert LimitConsistencyValidator().check(rows) == ()


def test_percent_without_basis_flagged(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "sector", "limit_value": "10", "limit_unit": "percent"},
    )
    codes = {v.code for v in LimitConsistencyValidator().check(rows)}
    assert "missing_basis" in codes


def test_absolute_without_currency_flagged(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "issuer", "limit_value": "50000000", "limit_unit": "absolute"},
    )
    codes = {v.code for v in LimitConsistencyValidator().check(rows)}
    assert "missing_currency" in codes


def test_absolute_with_currency_on_value_row_is_ok(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "issuer", "limit_value": "50000000", "limit_unit": "absolute"},
        currency="USD",
    )
    assert LimitConsistencyValidator().check(rows) == ()


def test_percent_out_of_range_flagged(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "sector", "limit_value": "150", "limit_unit": "percent",
         "basis": "market_value"},
    )
    codes = {v.code for v in LimitConsistencyValidator().check(rows)}
    assert "percent_out_of_range" in codes


def test_scoped_cap_exceeding_blanket_is_flagged(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "sector", "limit_value": "5", "limit_unit": "percent",
         "basis": "market_value"},  # blanket sector cap 5%
    )
    rows += _limit(
        extraction,
        1,
        {"dimension": "sector", "scope_value": "Technology", "limit_value": "10",
         "limit_unit": "percent", "basis": "market_value"},  # tech 10% > 5%
    )
    violations = LimitConsistencyValidator().check(rows)
    assert any(v.code == "scoped_exceeds_blanket" for v in violations)


def test_scoped_cap_within_blanket_is_ok(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "sector", "limit_value": "30", "limit_unit": "percent",
         "basis": "market_value"},
    )
    rows += _limit(
        extraction,
        1,
        {"dimension": "sector", "scope_value": "Technology", "limit_value": "10",
         "limit_unit": "percent", "basis": "market_value"},
    )
    assert LimitConsistencyValidator().check(rows) == ()


def test_assert_consistent_raises_on_violation(
    extraction: Callable[..., SilverExtraction],
) -> None:
    rows = _limit(
        extraction,
        0,
        {"dimension": "issuer", "limit_value": "50000000", "limit_unit": "absolute"},
    )
    with pytest.raises(LimitConsistencyError, match="missing_currency"):
        LimitConsistencyValidator().assert_consistent(rows)
