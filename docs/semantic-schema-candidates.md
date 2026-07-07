# Semantic Schema Candidates

These candidate schemas are based on the public examples in `example_schedules/`
and the normalized examples in `examples/golden_corpus/`. They are intended as
semantic extraction targets: each model response should still produce silver
rows with source clauses, locators, confidence, ambiguity, and explicit
`not_found` values.

The current production schema is `collateral_eligibility_schedule`. It works for
CSA-like and eligibility-style rows, but it is too narrow for central-bank
valuation tables such as the Federal Reserve Discount Window collateral margins
page.

## Shared Silver Envelope

Every schema should use the same row envelope so Gate A, correction memory, and
audit storage stay consistent:

```text
field_path
raw_value
normalized_value
value_type
unit
currency
source_clause
source_locator
confidence
ambiguity_flag
ambiguity_note
```

Rules:

- `source_clause` must be verbatim text from the document for found values.
- Missing values must use `value_type=not_found` and
  `normalized_value=not_found`.
- Repeated groups must use indexed paths: `eligibility[0].asset_criterion`, not
  `eligibility[].asset_criterion`.
- The model never emits system IDs, validator status, gold IDs, task state, or
  approval decisions.

## 1. Collateral Eligibility Schedule

Use for negotiated CSAs, triparty collateral profiles, CCP acceptable collateral
lists, and the normalized golden corpus.

Example sources:

- `examples/golden_corpus/*.txt`
- `example_schedules/Example6_synthetic-triparty-eligibility-profile.txt`
- `example_schedules/Example2_acceptable-collateral-futures-options-select-forwards.pdf`
- `example_schedules/Example5_EX-10.03.pdf`

Candidate paths:

```text
document.counterparty
document.agreement_id
document.schedule_version
document.margin_type
document.valid_from
document.valid_to

eligibility[0].asset_criterion
eligibility[0].eligible
eligibility[0].haircut_pct
eligibility[0].valuation_percentage
eligibility[0].concentration_limit_pct
eligibility[0].concentration_basis
eligibility[0].currency_scope
eligibility[0].rating_floor
eligibility[0].tenor_cap_days
eligibility[0].issuer_limit_pct
eligibility[0].wrong_way_risk_exclusion
eligibility[0].notes
```

Normalization notes:

- `eligible` normalizes to `true` or `false`.
- `haircut_pct` is the economic haircut.
- If a CSA gives a valuation percentage, preserve it as
  `valuation_percentage` and compute `haircut_pct = 100 - valuation_percentage`
  in trusted application code.
- `currency_scope` should normalize to comma-separated ISO currency codes when
  possible.

## 2. Collateral Haircut Matrix

Use for published tables where the key fact is a haircut by asset type, rating,
and tenor/maturity bucket.

Example sources:

- `example_schedules/Example3_GSD-Haircut-Schedule-Current.pdf`
- `example_schedules/Example4_DTC-Haircut-Schedule.pdf`
- Parts of `example_schedules/Example2_acceptable-collateral-futures-options-select-forwards.pdf`

Candidate paths:

```text
document.publisher
document.schedule_name
document.effective_date
document.margin_type

haircut_rule[0].asset_category
haircut_rule[0].security_type
haircut_rule[0].rating_condition
haircut_rule[0].currency_condition
haircut_rule[0].maturity_bucket
haircut_rule[0].maturity_min_days
haircut_rule[0].maturity_max_days
haircut_rule[0].haircut_pct
haircut_rule[0].eligible
haircut_rule[0].footnote_refs
haircut_rule[0].notes
```

Normalization notes:

- Convert maturity buckets to days when possible.
- Keep the displayed bucket label in `maturity_bucket` even when normalized
  bounds are also emitted.
- For tables where values are collateral value percentages, do not force them
  into `haircut_pct`; use the valuation-margin schema below.

## 3. Collateral Valuation Margin Table

Use for the Federal Reserve Discount Window collateral valuation page. This is
not a CSA eligibility schedule; it is a valuation/margin table.

Example source:

- `example_schedules/fed-discount-window-collateral-valuation.pdf`

Candidate paths:

```text
document.publisher
document.page_title
document.last_updated
document.effective_date
document.program_context

valuation_margin[0].collateral_family
valuation_margin[0].asset_category
valuation_margin[0].instrument_type
valuation_margin[0].rating_condition
valuation_margin[0].currency_condition
valuation_margin[0].duration_bucket
valuation_margin[0].duration_min_years
valuation_margin[0].duration_max_years
valuation_margin[0].collateral_value_pct
valuation_margin[0].implied_haircut_pct
valuation_margin[0].secondary_credit_additional_margin_applies
valuation_margin[0].notes

loan_margin[0].institution_scope
loan_margin[0].loan_category
loan_margin[0].coupon_type
loan_margin[0].risk_rating
loan_margin[0].repayment_type
loan_margin[0].time_to_maturity_years
loan_margin[0].margin_min_pct
loan_margin[0].margin_weighted_avg_pct
loan_margin[0].margin_max_pct
loan_margin[0].displayed_margin_pct
loan_margin[0].notes
```

Normalization notes:

- The Fed securities table displays `% of market value`, not haircut. Preserve
  that value as `collateral_value_pct`.
- `implied_haircut_pct = 100 - collateral_value_pct` can be derived by trusted
  code when useful.
- Loan margin ranges such as `81 - 82 - 83` should preserve min, weighted
  average, and max when present.
- The same document contains two table families: securities valuation margins
  and loan valuation margins. Keep them separate.

## 4. CSA Economic Terms

Use for negotiated ISDA CSA / Paragraph 13 documents where the business goal is
not only eligible collateral, but also margin mechanics.

Example sources:

- `example_schedules/Example5_EX-10.03.pdf`
- Real SEC EDGAR CSA exhibits added later

Candidate paths:

```text
document.party_a
document.party_b
document.agreement_date
document.governing_agreement

csa.margin_type
csa.base_currency
csa.credit_support_provider
csa.credit_support_receiver
csa.threshold_party_a
csa.threshold_party_b
csa.minimum_transfer_amount_party_a
csa.minimum_transfer_amount_party_b
csa.independent_amount_party_a
csa.independent_amount_party_b
csa.rounding_amount
csa.valuation_agent
csa.valuation_time
csa.notification_time
csa.transfer_timing
csa.dispute_resolution_timing
csa.interest_rate
csa.custodian
csa.seg_change_terms
csa.eligible_credit_support_clause
```

Normalization notes:

- Keep raw legal formulations in `raw_value`; normalize numeric values,
  currencies, and dates only when explicit.
- Many values are party-specific. Use party-qualified field names instead of
  collapsing both sides into one value.
- Ambiguous cross-references should be flagged, not resolved silently.

## 5. Portfolio Concentration And Liquidation Rules

Use for investment guidelines, credit-agreement collateral baskets, and asset
coverage tests.

Example source:

- `example_schedules/Example1_ex99-k2i.pdf`

Candidate paths:

```text
document.borrower
document.lender
document.agreement_id
document.amendment_date
document.facility_type

portfolio_rule[0].rule_name
portfolio_rule[0].asset_scope
portfolio_rule[0].limit_pct
portfolio_rule[0].limit_basis
portfolio_rule[0].lookthrough_required
portfolio_rule[0].issuer_scope
portfolio_rule[0].industry_scope
portfolio_rule[0].liquidation_period_bucket
portfolio_rule[0].haircut_pct
portfolio_rule[0].measurement_method
portfolio_rule[0].exception_text
portfolio_rule[0].notes
```

Normalization notes:

- Concentration limits and liquidation haircuts should be separate rules even
  when they appear in the same exhibit.
- Preserve rule names such as `Single Issuer Concentration Limit`.
- `limit_basis` should retain phrases such as `aggregate Value of Eligible
  Assets` because they matter for downstream calculations.

## 6. Agreement Amendment Metadata

Use as a companion schema for SEC-filed agreements and amendments. This should
not replace eligibility or CSA term extraction; it helps link amendments to base
agreements.

Example sources:

- `example_schedules/Example1_ex99-k2i.pdf`
- `example_schedules/Example5_EX-10.03.pdf`

Candidate paths:

```text
agreement_document.document_type
agreement_document.exhibit_number
agreement_document.effective_date
agreement_document.parties
agreement_document.base_agreement_name
agreement_document.base_agreement_date
agreement_document.amendment_number
agreement_document.amended_sections
agreement_document.maturity_date
agreement_document.commitment_amount
agreement_document.defined_terms
agreement_document.signature_parties
```

Normalization notes:

- This schema is useful for lineage and amendment reconciliation.
- It should feed document linking and supersession logic, not eligibility gold
  directly.

## Recommended Implementation Order

1. Keep the existing `collateral_eligibility_schedule` schema for CSA/triparty
   and normalized golden-corpus documents.
2. Add `collateral_haircut_matrix` for FICC, DTC, CME, and similar CCP tables.
3. Add `collateral_valuation_margin_table` for the Fed Discount Window page.
4. Add `csa_economic_terms` once owner-reviewed CSA examples are available.
5. Add `portfolio_concentration_rules` for credit-agreement investment guideline
   exhibits.
6. Add `agreement_amendment_metadata` as a linking/support schema.

The key design decision is to route by document class before semantic
extraction. A Fed valuation table should not be forced into eligibility rows,
and a CSA should not be forced into a CCP haircut matrix.
