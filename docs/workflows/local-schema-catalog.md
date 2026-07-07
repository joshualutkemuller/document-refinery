# Local Schema Catalog

DocumentRefinery has two kinds of reusable schemas/parsers.

## Semantic Schemas

These live in `src/document_refinery/semantic_schemas/` and are used by the
semantic provider path (`--semantic-provider local`, `ollama`, `openai`, or
`openai-compatible`) when a document needs semantic/classification-review routing.

Current semantic schemas:

| File | Document class | Used for |
| --- | --- | --- |
| `eligibility.py` | `collateral_eligibility_schedule` | Unknown CSA/triparty-style eligibility schedules (asset/haircut tables) |
| `valuation_margin.py` | `collateral_valuation_margin_table` | Federal Reserve collateral valuation and margins tables |
| `collateral_rule_schedule.py` | `collateral_rule_schedule` | **Fallback** rule-engine schema for rich negotiated dealer CSAs **and CCP/clearing-house schedules** (CME, ICE, LCH): issuer/country/rating bands, maturity bands, FX haircuts, valuation %, clearing-house context, account-scoped + dual regulatory/internal eligibility, priority score, CSA economics, plus a general **limit[i] sub-model** (sector/credit-quality/asset-type/issuer/country/currency caps, absolute-$ or %, market vs post-haircut basis, various aggregations, value-scoped) |
| `margin_requirement.py` | `margin_requirement` | **Demand side** (sibling): SIMM/IM/VM required amounts per counterparty/netting set — what the optimizer must satisfy |
| `margin_operations.py` | `collateral_margin_operation` | **Operational side** (sibling): margin calls, posted/eligible assets, substitutions, disputes, settlement status, inventory source |
| `base.py` | shared schema primitives | `SemanticSchemaSpec`, chunk definitions |
| `registry.py` | schema registry | Registers semantic schemas for extractor/validator use |

### CCP enhancement + margin siblings

Derived from `docs/additional-real-world-collateral-optimizer-references.md`. The
`collateral_rule_schedule` fallback was **enhanced to 0.2.0** to also cover CCP /
clearing-house eligibility schedules (clearing-house context, country/currency
limits, account-scoped eligibility) — the same `rule[i].*` shape. Two **sibling
templates** capture what an eligibility schema cannot: `margin_requirement`
(`requirement[i].*` — the margin *demand* the optimizer must satisfy) and
`collateral_margin_operation` (`call[i].*` — operational/settlement state).

**0.3.0** adds a general `limit[i].*` sub-model, because real schedules impose
limits a single per-row percentage cannot express: sector, credit-quality,
asset-type, issuer, country, and currency caps; stated as an **absolute currency
amount or a relative percent**; measured on **market value or post-haircut
value**; aggregated over posted collateral / the portfolio / per issuer; and
often **scoped to one value** ("Technology sector no more than 10%"). Each is one
`limit[i]` group: `dimension`, `scope_value`, `limit_value`, `limit_unit`,
`limit_currency`, `basis`, `aggregation`. Simple inline per-row caps may still use
`rule[i].concentration_limit_pct` etc.

All of these are `0.x` templates: SILVER-only, pending owner-verified golden sets,
named consumers, and Gate M/Gate S approval (Locked Decision 6). None write gold.

### The `collateral_rule_schedule` fallback

Derived from `docs/real-world-collateral-schedule-examples.md`, this schema
models a schedule as a **rule engine** rather than a haircut lookup. It is a
superset target: use it when a document carries constraints the narrow
`eligibility` schema cannot represent. Document-level terms (counterparty,
agreement_id, csa_type, margin_type, threshold_amount, minimum_transfer_amount,
independent_amount, rounding_convention, base_currency, valid_from/to) are
emitted once; each eligibility rule is an indexed `rule[i].*` group.

It is versioned `0.1.0` on purpose: it is a **template pending its own
owner-verified golden set, a named downstream consumer (the collateral
optimizer), and Gate M/Gate S approval** before production use (Locked Decision
6). Like every schema it produces silver only; it does not define or write gold.
Full CSA economics gold (`gold_csa_terms`) remains Milestone N5.

The Fed valuation schema also defines chunking so row-level extraction can be run
in bounded chunks with `--semantic-chunk-concurrency`.

## Fast Deterministic Local Profiles

Known public examples do not need an LLM. They route through deterministic
profile parsers in `src/document_refinery/agents/public_schedules.py`.

Current fast local profiles:

| Profile | Example | What it parses |
| --- | --- | --- |
| `portfolio_guidelines` | `Example1_ex99-k2i.pdf` | SEC-filed portfolio/investment guideline concentration and haircut rules |
| `cme` | `Example2_acceptable-collateral-futures-options-select-forwards.pdf` | CME acceptable collateral and haircut schedule |
| `ficc_gsd` | `Example3_GSD-Haircut-Schedule-Current.pdf` | FICC GSD clearing fund haircut table |
| `dtc` | `Example4_DTC-Haircut-Schedule.pdf` | DTC eligible collateral haircut table |
| `isda_vm` | `Example5_EX-10.03.pdf` | ISDA VM collateral asset valuation percentages converted to haircut fields |

The classifier signatures that route to those profiles are in
`src/document_refinery/application/classification.py`.

## How To Run Fast Local Examples

Known deterministic examples do not require `--semantic-provider`:

```bash
document-refinery run example_schedules/Example3_GSD-Haircut-Schedule-Current.pdf \
  --workspace .refinery-example3-gsd \
  --source public-example
```

For the Fed classification-review route, use the local semantic provider:

```bash
document-refinery run example_schedules/fed-discount-window-collateral-valuation.pdf \
  --workspace .refinery-fed-local \
  --source public-example \
  --semantic-provider local \
  --semantic-chunk-concurrency 2
```

## Adding The Next Fast Local Schema

1. Add a classifier signature in `application/classification.py`.
2. Add profile metadata in `_profile()` in `agents/public_schedules.py`.
3. Add profile row parsing in `_entries()` and a helper if needed.
4. Add the document to `example_schedules/manifest.json` with
   `expected_route: deterministic`.
5. Run `pytest tests/test_public_schedules.py`.

If the document is not stable enough for deterministic parsing, add a semantic
schema module under `semantic_schemas/` instead and register it in
`semantic_schemas/registry.py`.
