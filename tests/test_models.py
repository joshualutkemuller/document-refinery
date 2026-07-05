from __future__ import annotations

import pytest

from document_refinery.domain.models import ValidatorStatus, ValueType


def test_silver_requires_clause_lineage(extraction) -> None:
    with pytest.raises(ValueError, match="source_locator"):
        extraction(source_locator="")


def test_ambiguity_requires_note(extraction) -> None:
    with pytest.raises(ValueError, match="ambiguity_note"):
        extraction(ambiguity_flag=True)


def test_missing_value_is_explicit(extraction) -> None:
    row = extraction(
        value_type=ValueType.NOT_FOUND,
        raw_value="",
        normalized_value="not_found",
        source_clause="[FIELD NOT FOUND]",
    )
    assert not row.is_promotable


def test_owner_correction_becomes_effective_value(extraction) -> None:
    row = extraction(
        validator_status=ValidatorStatus.CORRECTED,
        corrected_value="7.5",
        corrected_by="owner",
    )
    assert row.effective_value == "7.5"

