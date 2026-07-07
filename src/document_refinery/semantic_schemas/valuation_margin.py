"""Collateral valuation margin table semantic schema."""

from __future__ import annotations

from document_refinery.semantic_schemas.base import SemanticSchemaSpec

DOC_CLASS = "collateral_valuation_margin_table"

FIELD_SUFFIXES = frozenset(
    {
        "publisher",
        "page_title",
        "last_updated",
        "effective_date",
        "program_context",
        "collateral_family",
        "asset_category",
        "instrument_type",
        "rating_condition",
        "currency_condition",
        "duration_bucket",
        "duration_min_years",
        "duration_max_years",
        "collateral_value_pct",
        "implied_haircut_pct",
        "secondary_credit_additional_margin_applies",
        "institution_scope",
        "loan_category",
        "coupon_type",
        "risk_rating",
        "repayment_type",
        "time_to_maturity_years",
        "margin_min_pct",
        "margin_weighted_avg_pct",
        "margin_max_pct",
        "displayed_margin_pct",
        "notes",
    }
)

SCHEMA_DICTIONARY = (
    "Use document metadata paths: document.publisher, document.page_title, "
    "document.last_updated, document.effective_date, document.program_context. "
    "For securities valuation tables, use indexed valuation rows: "
    "valuation_margin[0].collateral_family, valuation_margin[0].asset_category, "
    "valuation_margin[0].instrument_type, valuation_margin[0].rating_condition, "
    "valuation_margin[0].currency_condition, valuation_margin[0].duration_bucket, "
    "valuation_margin[0].duration_min_years, valuation_margin[0].duration_max_years, "
    "valuation_margin[0].collateral_value_pct, valuation_margin[0].implied_haircut_pct, "
    "valuation_margin[0].secondary_credit_additional_margin_applies, "
    "valuation_margin[0].notes. For loan valuation tables, use loan_margin[0]."
    "institution_scope, loan_margin[0].loan_category, loan_margin[0].coupon_type, "
    "loan_margin[0].risk_rating, loan_margin[0].repayment_type, "
    "loan_margin[0].time_to_maturity_years, loan_margin[0].margin_min_pct, "
    "loan_margin[0].margin_weighted_avg_pct, loan_margin[0].margin_max_pct, "
    "loan_margin[0].displayed_margin_pct, loan_margin[0].notes."
)

CONSTITUTION = (
    "Extract collateral valuation and margin tables. Do not force valuation margin "
    "tables into eligibility rows. Preserve collateral value percentages as "
    "collateral_value_pct when the table is stated as percent of market value; "
    "implied_haircut_pct may be extracted only when directly computed as "
    "100 - collateral_value_pct from the same source row. Keep securities valuation "
    "rows and loan margin rows separate. Preserve original-language evidence, emit "
    "explicit not_found fields for missing schema values, use numeric indexes for "
    "repeated groups, and never emit system-controlled fields."
)

SPEC = SemanticSchemaSpec(
    doc_class=DOC_CLASS,
    schema_version="valuation-margin-1.0.0",
    constitution_version="valuation-margin-1.0.0",
    constitution=CONSTITUTION,
    schema_dictionary=SCHEMA_DICTIONARY,
    field_suffixes=FIELD_SUFFIXES,
)
