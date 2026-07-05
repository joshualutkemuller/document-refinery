from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pytest

from document_refinery.domain.models import SilverExtraction, ValidatorStatus, ValueType


@pytest.fixture
def extraction() -> Callable[..., SilverExtraction]:
    def make(**overrides: object) -> SilverExtraction:
        values: dict[str, object] = {
            "extraction_id": "ext-1",
            "doc_id": "doc-1",
            "doc_class": "collateral_eligibility_schedule",
            "extractor_version": "1.0.0",
            "constitution_version": "1.0.0",
            "field_path": "eligibility[0].asset_criterion",
            "raw_value": "US Treasuries",
            "normalized_value": "GOVT_US",
            "value_type": ValueType.STRING,
            "source_clause": "U.S. Treasury securities shall be eligible.",
            "source_locator": "page=3;table=1;row=2;column=1",
            "confidence": 0.99,
            "validator_status": ValidatorStatus.CONFIRMED,
            "created_at": datetime(2026, 7, 5),
        }
        values.update(overrides)
        return SilverExtraction(**values)  # type: ignore[arg-type]

    return make

