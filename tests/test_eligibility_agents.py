from __future__ import annotations

from document_refinery.agents.eligibility import (
    EligibilityAdversarialValidator,
    EligibilityScheduleExtractor,
)
from document_refinery.domain.models import ValidatorStatus, ValueType

TEXT = """Collateral Eligibility Schedule
Eligible Collateral
Counterparty: Atlas Bank
Agreement ID: AGR-001
Schedule Version: 2026-01
Margin Type: VM
Valid From: 2026-01-01
Asset: GOVT_US | Eligible: yes | Haircut: 2% | Currencies: USD, EUR
"""


def test_extractor_emits_every_field_with_lineage_and_explicit_missing() -> None:
    rows = EligibilityScheduleExtractor().extract(doc_id="doc-1", text=TEXT)
    assert all(row.source_clause and row.source_locator for row in rows)
    rating = next(row for row in rows if row.field_path.endswith("rating_floor"))
    assert rating.value_type is ValueType.NOT_FOUND
    assert rating.normalized_value == "not_found"


def test_independent_validator_confirms_reference_extraction() -> None:
    extractor = EligibilityScheduleExtractor()
    rows = extractor.extract(doc_id="doc-1", text=TEXT)
    validated = EligibilityAdversarialValidator().validate(text=TEXT, extractions=rows)
    assert {row.validator_status for row in validated} == {ValidatorStatus.CONFIRMED}


def test_consistency_rule_disputes_out_of_range_haircut() -> None:
    text = TEXT.replace("Haircut: 2%", "Haircut: 120%")
    extractor = EligibilityScheduleExtractor()
    rows = extractor.extract(doc_id="doc-1", text=text)
    validated = EligibilityAdversarialValidator().validate(text=text, extractions=rows)
    haircut = next(row for row in validated if row.field_path.endswith("haircut_pct"))
    assert haircut.validator_status is ValidatorStatus.DISPUTED

