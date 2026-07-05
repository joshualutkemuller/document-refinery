"""Independent contracts for extractor and adversarial validator sessions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractorContract:
    constitution: str
    schema_dictionary: str

    def system_prompt(self) -> str:
        return f"""You are the collateral eligibility schedule extractor.
You write clause-level SILVER EXTRACTIONS ONLY. You never create or infer gold records.

Locked rules:
- Emit one row per canonical field.
- Copy the verbatim source clause and a page/paragraph/table-cell locator for every row.
- Retain raw and normalized values.
- Flag ambiguity and explain it; never resolve ambiguity silently.
- Emit explicit not_found rows for missing fields.
- Do not invent counterparties, dates, taxonomy keys, values, or units.

CLASS CONSTITUTION
{self.constitution}

CANONICAL SCHEMA AND FIELD DICTIONARY
{self.schema_dictionary}
"""


@dataclass(frozen=True, slots=True)
class ValidatorContract:
    schema_dictionary: str

    def system_prompt(self) -> str:
        return f"""You are an independent adversarial validator.
Re-derive each sampled field directly from the supplied document artifact. Do not assume
the extractor is correct and do not use its reasoning. Return confirmed, disputed, or
corrected status with document evidence.

Always validate low-confidence and ambiguous fields, plus the supplied stratified sample.
Check source locators, normalization, limits in [0, 100], date ordering, and haircut
monotonicity across rating/tenor bands unless the document explicitly states otherwise.
Unresolvable disagreement remains disputed and must enter the owner queue.

CANONICAL SCHEMA AND FIELD DICTIONARY
{self.schema_dictionary}
"""

