# Real-World Collateral Schedule Examples for Building a Collateral Optimizer

## Purpose

This document provides five real-world examples of collateral schedules used in the OTC derivatives market. These examples are useful references when designing a production-grade collateral optimization engine capable of handling ISDA Credit Support Annex (CSA) rules, eligibility criteria, haircuts, concentration limits, funding costs, and optimization constraints.

Rather than representing a collateral schedule as a simple haircut lookup table, modern optimizers typically implement schedules as flexible rules engines capable of evaluating numerous legal and operational constraints simultaneously.

---

## Example 1 — SEC Filed ISDA Credit Support Annex (1994 New York Law)

### Description

This is one of the best publicly available negotiated Credit Support Annexes (CSA).

It contains real negotiated collateral terms including:

- Eligible collateral definitions
- Thresholds
- Independent Amounts
- Minimum Transfer Amounts
- Delivery Amount calculations
- Return Amount calculations
- Valuation mechanics
- Substitution rules

This document is ideal for understanding the legal mechanics behind collateral movements rather than just haircut tables.

### Link

https://www.sec.gov/Archives/edgar/data/1083199/000119312507210724/dex996.htm

### Typical Eligible Collateral Schedule

| Asset | Eligible | Haircut |
| --- | --- | ---: |
| USD Cash | Yes | 0% |
| EUR Cash | Yes | 1% |
| GBP Cash | Yes | 1% |
| US Treasury (<1 year) | Yes | 0.5% |
| US Treasury (1–5 years) | Yes | 2% |
| US Treasury (>10 years) | Yes | 6% |
| Agency Bonds | Yes | 4% |
| AA Corporate Bonds | Yes | 8% |
| A Corporate Bonds | Yes | 12% |
| S&P 500 Equities | Yes | 15% |

---

## Example 2 — ISDA Template Collateral Schedules

### Description

Following the Uncleared Margin Rules (UMR), ISDA developed standardized template collateral schedules that institutions can negotiate instead of creating schedules from scratch.

These schedules include:

- Government securities
- Cash
- Corporate bonds
- Supranational debt
- Covered bonds
- Multiple credit quality buckets
- Jurisdiction-specific schedules

These templates represent current market practice for Initial Margin documentation.

### Link

https://www.isda.org/book/isda-template-collateral-schedules/

### Typical Schedule

| Collateral | Rating | Haircut |
| --- | --- | ---: |
| Cash | Any | 0% |
| AAA Government Bonds | AAA | 0.5% |
| AA Government Bonds | AA | 2% |
| A Government Bonds | A | 4% |
| AA Corporate Bonds | AA | 6% |
| A Corporate Bonds | A | 10% |
| BBB Corporate Bonds | BBB | 15% |
| Listed Equity | Major Index | 15% |

---

## Example 3 — Modern Variation Margin CSA (2016)

### Description

The 2016 ISDA Variation Margin CSA was developed to comply with post-financial-crisis regulations.

Unlike older CSAs, these schedules focus heavily on:

- Variation Margin
- Regulatory compliance
- Eligible currencies
- Government securities
- Wrong-way risk restrictions
- Operational eligibility requirements

The 2016 VM CSA remains one of the most common collateral agreements used between regulated financial institutions.

### Reference

https://uk.practicallaw.thomsonreuters.com/w-001-8921

### Typical Eligibility Table

| Asset | Rating Requirement | Haircut |
| --- | --- | ---: |
| USD Cash | None | 0% |
| EUR Cash | None | 1% |
| GBP Cash | None | 1% |
| US Treasury | AA+ | 1–3% |
| German Bund | AA+ | 1–3% |
| UK Gilt | AA | 2–5% |

---

## Example 4 — ISDA Operational Collateral Eligibility Guidance

### Description

One of the best references for designing the data model behind a collateral optimizer.

Rather than focusing only on legal documentation, this paper explains how collateral schedules become operational eligibility engines inside banks.

Topics include:

- Eligible collateral
- Documentation
- Operations
- Settlement
- Concentration limits
- Custodian restrictions
- Wrong-way risk
- Inventory management
- Valuation percentages

This is arguably the closest public document to how production collateral optimization systems are structured.

### Link

https://www.isda.org/a/GbugE/Mitigating-Eligible-Collateral-Risks-From-Documentation-to-Operations.pdf

### Typical Operational Schedule

| Field | Example |
| --- | --- |
| Asset Type | Government Bond |
| Currency | USD |
| Country | United States |
| Issuer | US Treasury |
| Rating | AA+ |
| Minimum Issue Size | $500MM |
| Remaining Maturity | 0–5 Years |
| Haircut | 2% |
| FX Haircut | 8% |
| Concentration Limit | 25% |
| Custodian | BNY Mellon |
| Settlement System | Fedwire |
| Eligible | Yes |

---

## Example 5 — Typical Dealer CSA Schedule

### Description

Large dealer banks typically encode CSA schedules as rule-based eligibility engines rather than static spreadsheets.

Typical rules include:

- Asset class
- Currency
- Issuer
- Credit rating
- Remaining maturity
- Concentration limits
- Wrong-way risk exclusions
- Settlement location
- Custodian
- Haircuts
- Eligibility flags

This structure closely mirrors the schemas used by many production collateral management platforms.

A representative public example can be found in major-bank CSAs and SEC-filed documentation.

### Example Rule

| Field | Example |
| --- | --- |
| Asset Class | Government Bond |
| Country | United States |
| Currency | USD |
| Issuer | US Treasury |
| Rating | AA or Better |
| Remaining Maturity | 0–1 Year |
| Haircut | 0.5% |
| Concentration Limit | 100% |
| Wrong-Way Risk | False |
| Settlement Location | Fedwire |
| Eligible | True |
| Priority Score | 1 |

---

## Recommended Data Model for a Production Collateral Optimizer

Rather than implementing collateral schedules as simple haircut tables, model each schedule as a rule set.

Suggested schema:

| Field | Example |
| --- | --- |
| Schedule ID | CSA_001 |
| Asset Type | Government Bond |
| Asset Class | Sovereign |
| Currency | USD |
| Country | United States |
| Issuer | US Treasury |
| Rating Minimum | AA- |
| Rating Maximum | AAA |
| Remaining Maturity Minimum | 0 |
| Remaining Maturity Maximum | 5 Years |
| Haircut | 2% |
| FX Haircut | 8% |
| Valuation Percentage | 98% |
| Concentration Limit | 25% |
| Issuer Limit | 10% |
| Asset Class Limit | 40% |
| Wrong-Way Risk Allowed | No |
| Minimum Issue Size | $500MM |
| Settlement Location | Fedwire |
| Custodian | BNY Mellon |
| Regulatory Eligible | Yes |
| Internal Eligible | Yes |
| Priority Score | 1 |
| Effective Date | 2026-01-01 |
| Expiration Date | Null |

---

## Key Takeaways

A modern collateral optimizer should support far more than simple haircut calculations. A robust engine should evaluate:

- Eligible collateral rules
- Haircuts
- FX haircuts
- Thresholds
- Minimum Transfer Amounts (MTA)
- Rounding conventions
- Independent Amounts (IA)
- Initial Margin (IM)
- Variation Margin (VM)
- Concentration limits
- Issuer limits
- Asset class limits
- Wrong-way risk
- Settlement restrictions
- Custodian restrictions
- Inventory availability
- Funding costs
- Liquidity costs
- Substitution costs
- Movement costs
- Operational constraints

Designing schedules as configurable rule engines rather than static lookup tables enables the optimizer to scale across counterparties, jurisdictions, and regulatory regimes while remaining flexible enough for future enhancements.
