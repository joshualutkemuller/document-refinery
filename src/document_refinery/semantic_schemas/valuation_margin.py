"""Collateral valuation margin table semantic schema."""

from __future__ import annotations

import re

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
    "rows and loan margin rows separate. The supplied document text may be a bounded "
    "chunk; extract only rows present in that chunk. Preserve original-language "
    "evidence, emit explicit not_found fields for missing schema values, use numeric "
    "indexes for repeated groups, and never emit system-controlled fields."
)


def prepare_text(text: str) -> str:
    """Return a compact securities-margin chunk for local/hosted LLM extraction.

    Browser-saved versions of the Fed page contain navigation text and loan tables
    that make local models wander. The source clauses in this chunk remain
    verbatim substrings of the full document, so downstream lineage checks still
    validate against the original extracted text.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = _header_lines(lines)
    section = _securities_section(lines)
    table_rows = [line for line in section if re.search(r"(?:\s+\d{2,3}){5}\s*$", line)]
    if not table_rows:
        return text
    limited_rows = table_rows[:10]
    return "\n".join(
        (
            "Collateral Valuation",
            "Securities Valuation and Margins Table",
            "Bounded extraction chunk: extract only the securities rows listed below.",
            *header,
            *limited_rows,
        )
    )


def _header_lines(lines: list[str]) -> list[str]:
    output: list[str] = []
    for line in lines:
        lowered = line.casefold()
        if "last updated:" in lowered or "effective date:" in lowered:
            output.append(line)
        if len(output) >= 2:
            break
    return output


def _securities_section(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    for index, line in enumerate(lines):
        if "securities valuation and margins table" in line.casefold():
            start = index
            break
    for index, line in enumerate(lines[start + 1 :], start=start + 1):
        if "loan valuation and margins tables" in line.casefold():
            end = index
            break
    return lines[start:end]


SPEC = SemanticSchemaSpec(
    doc_class=DOC_CLASS,
    schema_version="valuation-margin-1.0.0",
    constitution_version="valuation-margin-1.0.0",
    constitution=CONSTITUTION,
    schema_dictionary=SCHEMA_DICTIONARY,
    field_suffixes=FIELD_SUFFIXES,
    prepare_text=prepare_text,
)
