"""Registry for semantic extraction schemas."""

from __future__ import annotations

from document_refinery.semantic_schemas import (
    collateral_rule_schedule,
    eligibility,
    valuation_margin,
)
from document_refinery.semantic_schemas.base import SemanticSchemaSpec

_SCHEMAS = {
    eligibility.SPEC.doc_class: eligibility.SPEC,
    valuation_margin.SPEC.doc_class: valuation_margin.SPEC,
    collateral_rule_schedule.SPEC.doc_class: collateral_rule_schedule.SPEC,
}

DEFAULT_SCHEMA = eligibility.SPEC


def get_schema(doc_class: str) -> SemanticSchemaSpec:
    return _SCHEMAS.get(doc_class, DEFAULT_SCHEMA)


def schemas() -> tuple[SemanticSchemaSpec, ...]:
    return tuple(_SCHEMAS.values())
