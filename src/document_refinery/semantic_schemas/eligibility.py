"""Collateral eligibility semantic schema."""

from __future__ import annotations

from document_refinery.semantic_schemas.base import SemanticSchemaSpec

DOC_CLASS = "collateral_eligibility_schedule"

FIELD_SUFFIXES = frozenset(
    {
        "counterparty",
        "agreement_id",
        "schedule_version",
        "margin_type",
        "asset_criterion",
        "eligible",
        "haircut_pct",
        "concentration_limit_pct",
        "concentration_basis",
        "currency_scope",
        "rating_floor",
        "tenor_cap_days",
        "valid_from",
        "valid_to",
    }
)

SCHEMA_DICTIONARY = (
    "Use indexed eligibility rows: eligibility[0].asset_criterion, "
    "eligibility[0].eligible, eligibility[0].haircut_pct, "
    "eligibility[0].concentration_limit_pct, eligibility[0].concentration_basis, "
    "eligibility[0].currency_scope, eligibility[0].rating_floor, "
    "eligibility[0].tenor_cap_days, eligibility[0].valid_from, "
    "eligibility[0].valid_to. Use document-level or repeated eligibility paths "
    "for counterparty, agreement_id, schedule_version, and margin_type when the "
    "document states them. Never output eligibility[].field literally."
)

CONSTITUTION = (
    "Extract collateral eligibility schedule terms only. Preserve original-language "
    "evidence, emit explicit not_found fields, and never emit system-controlled fields. "
    "For valuation percentages in CSA tables, preserve the raw valuation percentage "
    "and normalize haircut_pct as the economic haircut when explicit or directly "
    "derivable."
)

SPEC = SemanticSchemaSpec(
    doc_class=DOC_CLASS,
    schema_version="eligibility-1.0.0",
    constitution_version="eligibility-1.1.0",
    constitution=CONSTITUTION,
    schema_dictionary=SCHEMA_DICTIONARY,
    field_suffixes=FIELD_SUFFIXES,
)
