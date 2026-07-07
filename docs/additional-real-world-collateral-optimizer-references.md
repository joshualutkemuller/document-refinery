# Additional Real-World References for Building a Collateral Optimizer

## Purpose

This document contains five additional references that complement traditional ISDA Credit Support Annexes. These sources focus on production collateral management, repo eligibility, CCP collateral schedules, optimization, and regulatory requirements.

Together with the first document, these references provide an excellent foundation for designing a modern collateral optimization engine.

---

## Example 6 — CME Clearing Eligible Collateral Schedule

### Description

CME publishes one of the most comprehensive public collateral eligibility schedules used by a major Central Counterparty (CCP).

Unlike bilateral CSAs, the schedule defines exactly which collateral is acceptable for clearing members.

The documentation includes:

- Eligible asset classes
- Eligible sovereign issuers
- Eligible currencies
- Haircuts
- Concentration limits
- Wrong-way risk restrictions
- Valuation percentages
- Operational eligibility

This is an excellent reference for implementing rule-based collateral validation.

### Link

https://www.cmegroup.com/clearing/risk-management/acceptable-collateral-for-cme-clearing.html

### Typical Schedule

| Asset | Example |
|---------|---------|
| Cash | USD, EUR, GBP, JPY |
| US Treasury Bills | Eligible |
| US Treasury Notes | Eligible |
| German Bunds | Eligible |
| UK Gilts | Eligible |
| Canadian Government Bonds | Eligible |
| Gold | Eligible for some accounts |
| Corporate Bonds | Limited eligibility |

---

## Example 7 — ICE Clear Europe Eligible Collateral

### Description

ICE Clear Europe publishes detailed collateral eligibility schedules for clearing members.

Useful fields include:

- Issuer restrictions
- Currency restrictions
- Credit ratings
- Haircuts
- Wrong-way risk exclusions
- Valuation percentages
- Settlement restrictions

Many production collateral engines closely resemble this structure.

### Link

https://www.theice.com/clear-europe/risk-management

### Example Eligibility Rule

| Field | Example |
|--------|---------|
| Asset Class | Sovereign Bond |
| Rating | AA or Better |
| Currency | GBP |
| Haircut | 2% |
| Eligible | Yes |

---

## Example 8 — LCH Collateral Eligibility Framework

### Description

LCH (London Clearing House) maintains one of the largest collateral management frameworks globally.

Its eligibility schedules include:

- Government securities
- Cash
- Corporate debt
- Supranational debt
- Equities
- Concentration limits
- Wrong-way risk
- Country limits
- Currency limits

This is an excellent example of enterprise-scale collateral eligibility management.

### Link

https://www.lch.com/services/clearing-services/risk-management

### Typical Rule

| Field | Example |
|--------|---------|
| Asset Type | Government Bond |
| Issuer Country | Germany |
| Currency | EUR |
| Rating | AA+ |
| Haircut | 1.5% |
| Concentration Limit | 20% |

---

## Example 9 — ISDA Standard Initial Margin Model (SIMM)

### Description

Although SIMM is not itself a collateral schedule, every modern collateral optimizer must integrate with SIMM-generated Initial Margin requirements.

SIMM determines:

- Required Initial Margin
- Margin sensitivities
- Risk classes
- Netting effects
- Regulatory IM calculations

The optimizer's job is to determine the lowest-cost collateral inventory capable of satisfying these margin requirements while respecting CSA constraints.

### Link

https://www.isda.org/isda-solutions-infohub/isda-simm/

### Inputs Used by an Optimizer

| Field | Example |
|--------|---------|
| Initial Margin Requirement | $24,500,000 |
| Currency | USD |
| Counterparty | Bank A |
| Margin Type | IM |
| CSA Schedule | CSA_001 |

---

## Example 10 — Acadia Margin Manager Documentation

### Description

Acadia (formerly AcadiaSoft) is the industry standard platform for collateral and margin processing.

While its documentation does not publish complete legal schedules, it provides valuable insight into how collateral data is operationalized.

Topics include:

- Margin calls
- Eligible collateral
- Substitutions
- Dispute management
- Inventory management
- Settlement workflows
- Margin optimization

Many global banks build internal optimization engines that interact directly with Acadia.

### Link

https://www.acadia.inc/

### Typical Operational Fields

| Field | Example |
|--------|---------|
| Counterparty | Goldman Sachs |
| Margin Type | VM |
| Required Amount | $12,500,000 |
| Eligible Assets | Treasury, Cash |
| Haircut Applied | Yes |
| Settlement Status | Pending |

---

## Design Lessons from These Sources

Collectively, these references show that production collateral optimization is not just a haircut calculation problem. Instead, it is a constrained optimization problem involving legal, operational, funding, and regulatory considerations.

A modern optimizer should evaluate:

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
- Country limits
- Wrong-way risk
- Settlement restrictions
- Custodian restrictions
- Liquidity costs
- Funding costs
- Inventory availability
- Settlement timing
- Collateral substitutions
- Operational costs
- Regulatory eligibility

---

## Recommended Reading Order

If building a collateral optimizer from scratch, review these references in the following order:

1. ISDA Credit Support Annex (legal rules)
2. ISDA Template Collateral Schedules (standardized eligibility)
3. CME Eligible Collateral Schedule (real production rules)
4. LCH Collateral Framework (enterprise collateral management)
5. ICE Clear Europe Eligibility Rules (operational implementation)
6. Acadia Margin Manager (workflow and operations)
7. ISDA SIMM Documentation (margin generation)
8. ISDA Operational Guidance (data model and rule engine)

Together, these documents provide a strong foundation for implementing a production-grade collateral optimization engine capable of supporting bilateral CSAs, regulatory initial margin, variation margin, central clearing, inventory optimization, and funding-aware collateral allocation.
