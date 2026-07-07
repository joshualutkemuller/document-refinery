# Document Refinery — Build Plan & LLM Handoff Document

**Version:** 1.6 (chunked semantic extraction and local schema catalog checkpoint)
**Checkpoint date:** 2026-07-07
**Owner/CEO:** Joshua (quantitative researcher, securities finance / collateral / ML systems)
**Purpose of this document:** Complete context transfer to any LLM or engineer continuing development. Read fully before writing code. Locked decisions are binding unless the owner explicitly reverses them.
**Sibling projects:** Model Foundry (model lifecycle factory) and Collateral Desk Autopilot (desk operations copilot). Document Refinery is the third leg: it is the *ingestion and structuring layer* that turns unstructured financial documents into bitemporal, quant-ready Delta tables consumed by both siblings. It shares their chassis (task table, gates, presenter altitudes, distiller learning loop, sandbox TTL).

---

## 0. Current Repository Checkpoint

The repository is no longer an initial scaffold. Phase 0/1 engineering, the
hybrid semantic foundation, N3 production-provider adapter wiring, local/Ollama
semantic experimentation support, and chunked semantic extraction are implemented
on `main`.

### 0.1 Completed capabilities

| Capability | Status | Evidence |
|---|---|---|
| Professional packaged-Python repository and CI | Complete | `pyproject.toml`, GitHub Actions, Ruff, strict mypy, pytest |
| Immutable bronze ingestion | Complete locally | SHA-256 content-addressed raw documents with collision checks |
| Versioned text/layout artifacts | Complete for text-bearing files | TXT, Markdown, and PDF text plus page/line layout JSON |
| Durable task workflow | Complete locally | SQLite state machine with guarded transitions through Gate A and gold |
| Deterministic eligibility extraction | Complete for supported profiles | Normalized, portfolio-guideline, CME, FICC GSD, DTC, and ISDA VM profiles |
| Independent validation | Complete for supported profiles | Separate deterministic parser/evidence validators; disputes block Gate A |
| Gate A review | Complete locally | HTML/JSON packets, identified CLI approval, no automatic approval |
| Deterministic gold promotion | Complete locally | Bitemporal eligibility records with all contributing silver IDs |
| Quality reporting | Complete locally | Executive briefing, dashboard JSON, and audit appendix |
| Synthetic regression corpus | Complete technically | 10 documents, 100% expected-field accuracy, zero disputes |
| Public PDF corpus | Complete technically | 5 hashed PDFs, 154 eligibility records, 2,156 silver fields |
| Provider-neutral semantic extraction | Foundation complete | Strict JSON schemas, original-language evidence, system-field rejection |
| Independent semantic validation | Foundation complete | Separate-session enforcement and full judgment coverage |
| Production semantic provider adapter | N3 engineering complete | OpenAI Responses adapter, CLI wiring, separate sessions, bounded retries, latency/token metadata |
| Local/Ollama semantic provider support | Engineering complete for dev/test | `local`, `ollama`, and `openai-compatible` provider routes with output-token and timeout controls |
| Semantic schema registry | Engineering complete | `semantic_schemas/` modules for eligibility and collateral valuation/margins |
| Chunked semantic extraction | Engineering complete | Schema-defined chunks, per-chunk audit calls, path reindexing, `--semantic-chunk-concurrency` |
| Federal Reserve valuation-margin schema | Engineering baseline complete | Fast local extraction for Fed securities valuation rows with lineage and chunking |
| Local schema catalog | Complete | `docs/workflows/local-schema-catalog.md` maps semantic schemas and deterministic profiles |
| Semantic audit trail | Foundation complete | Provider/model/session/version metadata plus request/response hashes |
| Owner correction/dispute workflow | Local baseline complete | Authenticated confirm/correct/dispute on silver rows via a terminal review CLI; read-only review packet; append-only correction log; disputes block Gate A |
| Operational SQL contracts | Complete for implemented layers | Bronze, silver, gold, tasks, gates, regression, semantic-call, and correction-action DDL |

### 0.2 Verified repository evidence

- Automated suite: **101 passing tests** at this checkpoint.
- Static checks: **Ruff passing; strict mypy has previously passed for the
  repo baseline and should be rerun before release/PR merge**.
- Public corpus: **5/5 documents reach `gate_a_pending`**.
- Public corpus output: **154 eligibility records / 2,156 silver fields**.
- Public corpus validation: **zero disputes and zero unresolved locators for
  found values**.
- Fast local public-profile suite: **15 passing tests** for deterministic
  profile coverage.
- Fed valuation-margin local semantic run: **58 silver fields** with two
  extractor chunk calls plus one validator call recorded when run with
  `--semantic-provider local --semantic-chunk-concurrency 2`.
- Chunked semantic runner: full pytest suite passes; Ruff and `git diff --check`
  pass after the implementation.
- Unknown-language foundation: a Spanish unseen-template test routes through
  different extractor/validator sessions and stops at Gate A.
- Prompt-injection control: model attempts to set system-controlled fields are
  rejected before silver persistence.

These are engineering compatibility results, not production accuracy evidence.
No public document or synthetic case is counted as an owner-verified golden
extraction.

### 0.3 Supported execution paths

1. Known profiles use deterministic parsing and deterministic/evidence
   validation.
2. Unknown profiles stop for classification review by default.
3. Unknown or review-required profiles may use the semantic route when both a
   semantic extractor and an independent semantic validator adapter are
   configured through the CLI or programmatically.
4. Every successful path stops at Gate A unless an identified reviewer approves
   it.
5. Schema modules may define bounded chunks. The extractor can run those chunks
   serially or with `--semantic-chunk-concurrency N`, merge/reindex field paths,
   and persist every chunk call in the semantic audit log.

### 0.4 Not complete

- OpenAI is selected as the initial approved semantic-model provider, gated by zero-data-retention account/project settings before any production call.
- Production semantic provider adapter and CLI wiring exist for the OpenAI Responses API; credentials remain environment-only.
- Ollama/local model experimentation is supported, but local 14B-class models on
  the owner's 24 GB RAM Mac are slow and inconsistent for large structured JSON
  outputs. Prefer deterministic/local profile parsers where structure is stable.
- OCR/layout coordinate contracts and a deterministic text-line coordinate adapter are implemented; scanned/image OCR benchmark execution is still pending.
- No owner-verified ten-document golden set or measured review-time evidence.
- Authenticated correction/dispute workflow exists as a terminal CLI baseline
  (interactive `review` command plus a read-only review packet and durable
  correction log). The distiller now replays that log into owner-reviewable
  constitution-rule and golden-case proposals (`document-refinery distill`); a
  hosted/authenticated UI and auto-applied constitution/golden updates remain to
  build (the owner still batch-approves every proposal).
- No production object storage, managed Delta jobs, access controls, monitoring,
  or retry orchestration.
- No full CSA economics gold schema (threshold, MTA, IA, rounding, interest,
  dispute timing, custody).
- No amendment/base reconciliation, term diff, or Autopilot transform.
- No released multilingual language/document-class pair.

## 1. Mission Statement

Document Refinery ingests collateral schedules and other high-value financial documents, extracts their economic content with clause-level lineage, and lands it in canonical, versioned, bitemporal Delta tables designed for downstream quantitative use. The owner acts as CEO: he defines document classes and canonical schemas, signs off extractions at gates, and consumes coverage/quality briefings. Agents do the reading, structuring, validating, and reconciling.

The end state: any quant model or agent in the ecosystem can query "what were the effective eligibility terms for counterparty X as known on date D" — or join document-derived features into a training set — without ever touching a PDF.

## 2. Document Universe (initial scope, expandable)

**Tier 1 — launch (owner's core domain, highest structure/value ratio):**
- CSAs and credit support annex amendments (eligibility, haircuts, thresholds, MTA, currencies)
- Collateral eligibility schedules (tri-party and bilateral), concentration limits
- GMRA / MRA / MSLA schedules and annexes (repo & securities lending terms)
- Fee schedules and rate cards (securities lending)

**Tier 2 — near-term:**
- ISDA master agreement key terms (termination events, thresholds)
- Tri-party allocation reports and RQV statements (semi-structured)
- Rating agency reports (issuer/issue ratings, watch/outlook changes)
- Term sheets for financing transactions

**Tier 3 — later:**
- Prospectuses / offering docs (security master enrichment)
- Corporate action notices
- Regulatory texts affecting eligibility (e.g., UMR phase rules) — reference extraction only

**Locked decision:** each document class enters scope only with (a) a canonical target schema, (b) a golden set of ≥ 10 owner-verified example extractions, and (c) a named downstream consumer (a model, the Autopilot rule engine, or a feature table). No speculative ingestion.

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│ CEO LAYER (Joshua)                                   │
│ schema definitions · extraction sign-offs (Gate A) · │
│ golden-set curation · coverage/quality briefings     │
├──────────────────────────────────────────────────────┤
│ ORCHESTRATION LAYER (shared chassis)                 │
│ Landing-zone watcher → classify → route → task DAG:  │
│ ingest → classify → extract → validate → reconcile → │
│ land → publish views                                 │
├──────────────────────────────────────────────────────┤
│ AGENT LAYER                                          │
│ Deterministic parsers + Semantic Extractor router ·  │
│ Independent Semantic Validator · Reconciler ·        │
│ Schema Steward · Quality Reporter · Distiller        │
├──────────────────────────────────────────────────────┤
│ STORAGE / MEMORY LAYER                               │
│ Bronze: raw docs + text/layout artifacts             │
│ Silver: clause-level extractions w/ lineage          │
│ Gold: canonical bitemporal term tables               │
│ Platinum: quant-ready feature views                  │
│ + Extraction constitutions (per doc class)           │
│ + Golden sets (regression corpus)                    │
└──────────────────────────────────────────────────────┘
```

## 4. Storage Layer Specification (the heart of this project)

### 4.1 Bronze — immutable raw (`refinery.bronze_documents`)
```sql
(doc_id STRING, source STRING, counterparty STRING,
 doc_class_hint STRING, file_uri STRING, file_hash STRING,
 page_count INT, received_at TIMESTAMP,
 text_artifact_uri STRING,      -- extracted text w/ page/coord map
 layout_artifact_uri STRING)    -- tables/structure extraction
```
Raw files are immutable; re-processing always starts from bronze. OCR/text extraction outputs are versioned artifacts, not overwrites.

### 4.2 Silver — clause-level extractions (`refinery.silver_extractions`)
```sql
(extraction_id STRING, doc_id STRING, doc_class STRING,
 extractor_version STRING, constitution_version STRING,
 field_path STRING,             -- canonical schema field addressed
 raw_value STRING, normalized_value STRING, value_type STRING,
 unit STRING, currency STRING,
 source_clause TEXT,            -- verbatim clause text
 source_locator STRING,         -- page/paragraph/table-cell anchor
 confidence DOUBLE,
 ambiguity_flag BOOLEAN, ambiguity_note STRING,
 validator_status STRING,       -- pending | confirmed | disputed | corrected
 corrected_value STRING, corrected_by STRING,
 created_at TIMESTAMP)
```
**Locked decision:** every gold-table value must be traceable to a silver row with a source_locator. Clause-level lineage is non-negotiable — it is what makes extractions auditable, disputable, and trainable.

### 4.3 Gold — canonical bitemporal term tables (per document class)
Follow the owner's existing bitemporal pattern (as in the FRED pipeline): every table carries `valid_from / valid_to` (economic effectiveness) and `knowledge_from / knowledge_to` (when the system knew it). Example, eligibility terms:

```sql
CREATE TABLE refinery.gold_eligibility_terms (
  counterparty STRING, agreement_id STRING, schedule_version STRING,
  margin_type STRING,               -- VM | IM | Repo | Clearing Fund | Secured Financing
  asset_criterion STRING,           -- Bloomberg-taxonomy-aligned key
  eligible BOOLEAN, haircut_pct DOUBLE,
  concentration_limit_pct DOUBLE, concentration_basis STRING,
  currency_scope ARRAY<STRING>, rating_floor STRING, tenor_cap_days INT,
  valid_from DATE, valid_to DATE,
  knowledge_from TIMESTAMP, knowledge_to TIMESTAMP,
  silver_extraction_ids ARRAY<STRING>,   -- lineage
  doc_id STRING
) USING DELTA;
```
Analogous gold tables per class: `gold_csa_terms` (thresholds, MTA, IA), `gold_repo_terms`, `gold_lending_fee_terms`, `gold_ratings`, `gold_isda_terms`. Schema Steward agent proposes; owner approves all gold DDL (Gate S).

### 4.4 Platinum — quant-ready feature views
Derived views/tables shaped for model consumption, e.g.:
- `plat_eligibility_breadth(counterparty, as_of, n_eligible_asset_classes, avg_haircut, haircut_dispersion, concentration_tightness_score)`
- `plat_terms_change_events(counterparty, event_date, dimension, direction, magnitude)` — schedule tightening/loosening as an event series (usable as features or labels in Foundry models)
- `plat_doc_coverage(counterparty, doc_class, freshness_days, completeness_pct)`
Platinum is where "documents become features." Every platinum column documents its gold provenance.

## 5. Agent Layer Specification

### 5.1 Classifier agent
Assigns doc_class + counterparty + agreement linkage from landing-zone files; routes to the right extractor. Low-confidence classifications go to owner review, never guessed silently.

### 5.2 Extractor agents (one per document class)
- Input: bronze text/layout artifacts + canonical schema + extraction constitution for the class.
- Output: silver rows only — never write gold directly (locked decision).
- Rules: verbatim source_clause and source_locator required per field; ambiguous language flagged with ambiguity_note; missing fields explicitly emitted as `not_found` rather than omitted (absence is information); all normalizations (units, percentages vs. bps, date conventions, rating scales) applied at silver with both raw and normalized values retained.

### 5.3 Adversarial Validator agent
- Separate session from the extractor (same parser/reviewer split as Autopilot — locked decision).
- Independently re-derives a stratified sample of fields (all low-confidence rows + random sample of high-confidence) and cross-checks. Disagreements → `disputed` status → owner queue.
- Runs class-specific consistency rules (e.g., haircuts monotone in rating bands unless clause says otherwise; concentration limits ≤ 100%; valid_from ≤ valid_to).

### 5.4 Reconciler agent
- Cross-document consistency: amendment vs. base agreement, schedule vs. tri-party setup reports, extracted ratings vs. vendor feeds where available. Produces discrepancy reports; material discrepancies gate to owner.
- On amendment: computes term diffs and hands the change summary to Autopilot's schedule-diff workflow (integration point).

### 5.5 Schema Steward agent
- Owns canonical schema evolution: when extractors repeatedly hit content the schema can't hold, proposes DDL migrations (additive-preferred, bitemporal-safe) for owner approval. Maintains the schema registry and field dictionaries (definitions, units, allowed values, Bloomberg taxonomy mappings).

### 5.6 Quality Reporter agent (presenter)
Three altitudes, shared pattern:
1. **Executive briefing:** coverage %, freshness, extraction accuracy vs. golden sets, open disputes, this week's schema/constitution changes — one paragraph plus a small table.
2. **Dashboard payload** for the Dash stack (coverage heatmap by counterparty × doc class, confidence distributions, dispute aging).
3. **Audit appendix** with full lineage samples.

### 5.7 Distiller agent (learning loop)
- Sources: owner corrections on silver rows, validator disputes and resolutions, reconciler findings.
- Outputs: extraction-constitution diffs per doc class ("CP-X defines 'investment grade' by internal ratings — map via table T"; "Fee schedules from custodian Y quote in bps on loan value, not market value"), golden-set additions, and normalization-rule updates. Owner batch-approves monthly.
- Every owner correction must end up as either a constitution rule or a golden-set case — corrections that evaporate are the failure mode this agent exists to prevent.

### 5.8 Hybrid semantic extraction layer (active next tranche)

The production extraction path is hybrid:

1. OCR/layout adapters produce versioned page text, coordinates, table cells,
   and reading order in bronze.
2. High-precision deterministic parsers run first for known document profiles.
3. Unknown templates, varied legal phrasing, and supported non-English language
   route to a semantic extractor operating under the document-class
   constitution and canonical field dictionary.
4. Model output is schema-validated and converted to silver rows by trusted
   application code. Models never create system IDs, validation status, or gold.
5. A separately prompted validator, using a different model session, re-derives
   the required sample directly from the source artifact.
6. Where a schema can produce bounded chunks, extraction may run chunk-by-chunk
   with optional parallelism. The application merges silver rows, reindexes
   repeated field paths, stores every extractor chunk call, and then runs the
   independent validator over the merged candidate set.

Semantic model calls must record provider, model, prompt/constitution/schema
versions, session ID, request timestamp, and response artifact hash. Document
content is untrusted data: instructions contained inside a document never alter
the system role, output schema, tools, gates, or validation policy.

Current schema locations:

- Semantic schemas: `src/document_refinery/semantic_schemas/`
  - `eligibility.py`: collateral eligibility semantic target (asset/haircut table).
  - `valuation_margin.py`: Federal Reserve collateral valuation/margins schema,
    including securities-row chunking.
  - `collateral_rule_schedule.py`: **fallback rule-engine schema** (v0.3.0) for
    rich negotiated dealer CSAs **and CCP/clearing-house schedules** (CME, ICE,
    LCH) that exceed the eligibility table: issuer/country/rating bands, maturity
    bands, FX haircuts, valuation percentages, wrong-way-risk, settlement/
    custodian, clearing-house context, account-scoped + dual regulatory/internal
    eligibility, priority score, document-level CSA economics, plus a general
    `limit[i]` sub-model (sector/credit-quality/asset-type/issuer/country/currency
    caps, absolute-$ or %, market vs post-haircut basis, various aggregations,
    value-scoped). Derived from `docs/real-world-collateral-schedule-examples.md`
    and `docs/additional-real-world-collateral-optimizer-references.md`.
  - `margin_requirement.py`: **demand-side sibling** (SIMM/IM/VM required amounts
    per counterparty/netting set — what the optimizer must satisfy).
  - `margin_operations.py`: **operational sibling** (`collateral_margin_operation`
    — margin calls, posted/eligible assets, substitutions, disputes, settlement
    status, inventory source).
  - The rule schema and both siblings are `0.x` templates pending their own
    owner-verified golden sets, named consumers (the collateral optimizer), and
    Gate M/Gate S approval before production (Locked Decision 6). Silver-only like
    every schema; full CSA economics gold stays Milestone N5.
  - `base.py`: `SemanticSchemaSpec` and `SemanticTextChunk`.
  - `registry.py`: runtime schema registry.
- Fast deterministic public profiles:
  `src/document_refinery/agents/public_schedules.py`.
- Human-readable catalog:
  `docs/workflows/local-schema-catalog.md`.

Current fast local coverage:

- Example 1: `portfolio_guidelines`.
- Example 2: `cme`.
- Example 3: `ficc_gsd`.
- Example 4: `dtc`.
- Example 5: `isda_vm`.
- Fed collateral valuation PDF: semantic route with `--semantic-provider local`
  and optional `--semantic-chunk-concurrency`.

Language support is admitted one language/document-class pair at a time. Each
pair requires terminology mappings, normalization rules, ≥10 owner-verified
golden documents, and the same regression gate as an English class. Translation
may assist review but the verbatim source clause and locator always refer to the
original-language artifact.

## 6. Workflow & Gates

`land → classify → extract (silver) → validate → [disputes to owner] → reconcile → [Gate A: owner signs off doc-level extraction for Tier-1 classes] → land gold (bitemporal upsert) → refresh platinum views → quality briefing`

- **Gate A (extraction sign-off):** required per document for Tier-1 classes until class-level accuracy vs. golden set ≥ 98% for 3 consecutive months, after which the owner may downgrade that class to sampling-based review (owner decision, recorded in policy).
- **Gate S (schema):** all gold DDL changes.
- **Gate M (model release):** provider/model, prompt, constitution, schema, or
  routing-policy changes must pass the relevant owner-verified multilingual
  golden sets with no lineage regression before deployment.
- Regression rule: every extractor or constitution version bump re-runs against the class golden set before deployment; accuracy regressions block release.

## 7. Integration Points

| Consumer | What it takes | Contract |
|---|---|---|
| Collateral Desk Autopilot | `gold_eligibility_terms` → rule-engine format; amendment diffs | Refinery replaces/feeds Autopilot's Schedule Parser; Autopilot's Gate A and Refinery's Gate A unify into one sign-off |
| Model Foundry | Platinum feature views; `plat_terms_change_events` as features/labels | Foundry data contracts reference platinum views + snapshot pins |
| Dash dashboards | Quality Reporter payloads; coverage heatmaps | JSON contract defined Phase 1 |
| FRED pipeline pattern | Bitemporal conventions | Reuse the same valid/knowledge timestamp idioms and vintage query helpers |

**Locked decision:** Refinery is the single source of document-derived terms for the ecosystem. Autopilot and Foundry consume gold/platinum; they never parse documents independently once the relevant class is live in Refinery.

## 8. Build Plan

### Phase 0 — Foundations — engineering complete; production acceptance pending
- Bronze/silver DDL; landing zone + watcher job; text/layout extraction toolchain selection (test against 3 gnarly real schedules — scanned, multi-column, nested tables — before committing).
- Golden-set tooling: a lightweight review UI or notebook flow for the owner to confirm/correct silver rows efficiently (this is the highest-leverage UX in the project; owner review throughput determines everything).

Delivered: local bronze/silver/gold adapters, watcher, task workflow, review
packets, quality outputs, and text-bearing PDF support. Still required for
production acceptance: the three-document OCR/layout benchmark and authenticated
owner correction workflow.

### Phase 1 — One class, end to end — engineering complete; owner acceptance pending
- Single Tier-1 class: **collateral eligibility schedules**, 2–3 counterparties the owner knows cold (shared choice with Autopilot Phase 3 — same pilot, one effort).
- Build: classifier (trivial at one class), extractor, validator, gold_eligibility_terms, Gate A flow, golden set of ≥ 10 docs, quality briefing v1.
- Exit criteria: field-level accuracy ≥ 95% vs. golden set; every gold value traceable to a clause; owner review time per document ≤ 15 minutes.

Delivered: complete local vertical slice, six deterministic profiles, synthetic
and public corpora, clause lineage, Gate A, bitemporal promotion, and quality
reporting. Still required for owner acceptance: ≥10 owner-verified schedules,
two or three pilot counterparties, ≥95% measured accuracy, and ≤15-minute
measured review time.

### Phase 1B — Hybrid semantic generalization — foundation complete; active next phase
- Add provider-neutral model request/response contracts and strict silver-output
  validation; retain deterministic profiles as the preferred high-precision
  route.
- Add separate semantic extractor and validator sessions with recorded model,
  prompt, schema, and constitution versions.
- Route unknown English templates through the semantic path only when a model
  adapter is configured; otherwise continue to classification review.
- Add OCR/layout coordinate contracts before enabling scanned documents.
- Admit the first non-English language only after terminology mapping and ≥10
  owner-verified examples for the target class.
- Exit criteria: unseen-template accuracy ≥95% on the owner golden set; 100% of
  found values have original-language evidence; prompt-injection tests pass;
  deterministic-profile accuracy does not regress.

Delivered: provider-neutral contracts, complete response schemas, trusted
silver conversion, separate-session validation, semantic routing hooks,
original-language evidence enforcement, prompt-injection/system-field
rejection, OpenAI Responses API adapter, CLI configuration for separate
extractor/validator sessions, bounded retries/timeouts, semantic latency/token
metadata, semantic audit hashes, JSONL audit storage, Delta DDL,
OpenAI-compatible/Ollama/local provider wiring, output-token caps, semantic
schema registry, Fed valuation-margin schema, chunked semantic extraction, and
local schema catalog documentation. Still required: owner-verified
unseen-template corpus, scanned/layout benchmark results, and release approval
for the first language/class pair.

### Phase 2 — Reconciler + Autopilot integration — not started
- Amendment diffing, gold → rule-engine transform, unified sign-off with Autopilot.

### Phase 3 — Platinum features + Foundry integration — not started
- First feature views (`plat_eligibility_breadth`, `plat_terms_change_events`); register as Foundry data contracts; one Foundry experiment consumes them as proof.

### Phase 4 — Class expansion — not started
- Add CSA terms and lending fee schedules (Tier 1 completion), then GMRA/MRA. Each class follows the locked entry rule (schema + golden set + named consumer).

### Phase 5 — Learning-loop hardening + review downgrade — not started
- Distiller cadence, constitution/golden-set growth, accuracy tracking per class, first sampling-based review downgrade if a class earns it.

## 9. Locked Decisions
1. Clause-level lineage on every extracted value (source_clause + source_locator); no lineage, no landing.
2. Extractors write silver only; gold is landed by a deterministic promotion job after validation/gates.
3. Extractor and validator are separate agent sessions.
4. Ambiguity is flagged, never silently resolved; missing fields are emitted as `not_found`, not omitted.
5. All gold tables are bitemporal (valid + knowledge time), following the owner's established pattern.
6. Document classes enter scope only with schema + golden set + named consumer.
7. Golden-set regression testing gates every extractor/constitution release.
8. Refinery is the single document-parsing authority once a class is live; siblings consume, never re-parse.
9. Raw documents are immutable; reprocessing starts from bronze.
10. Deterministic parsers remain the preferred path when their profile matches;
    semantic extraction handles variability rather than replacing proven rules.
11. Model responses are untrusted until strict schema, lineage, and consistency
    validation succeeds; provider SDK objects never enter silver directly.
12. Semantic extractor and validator use different sessions and independently
    authored prompts; they do not share hidden reasoning or extraction heuristics.
13. Model/provider/prompt/schema/constitution versions and response hashes are
    recorded for every semantic call.
14. Document text is data, never instruction. Embedded prompts cannot change
    schemas, tools, gates, or system policy.
15. Multilingual support is released per language and document class with its
    own owner-verified golden set; original-language lineage is mandatory.
16. Chunking is an extraction optimization, not a validation shortcut. Chunked
    extractor calls must still produce silver rows with verbatim source clauses,
    merged/reindexed field paths, and independent validation before Gate A.

## 10. Open Decisions (for owner)
- Production OCR/layout toolchain (the text-bearing PDF baseline is implemented;
  evaluate scanned, multi-column, and nested-table documents before selection).
- Authenticated review UX for corrections and disputes (generated HTML/JSON plus
  CLI approval is implemented as the local baseline).
- Whether verbatim clause text in silver raises any internal data-handling constraints (compliance check; if so, store locators + hashes and fetch clauses on demand from bronze).
- Accuracy threshold and duration for downgrading a class from per-document to sampling review (default proposal: 98% / 3 months).
- Which two or three counterparties seed Phase 1 (align with Autopilot Phase 3).
- PII/confidentiality handling policy for Tier 2+ classes.
- Initial semantic model provider and approved data-retention/region policy: **closed for N1**. OpenAI is approved only under zero-data-retention, environment-scoped service-account credentials, hash-only local audit logging plus controlled response-artifact storage, and pre-deployment verification of account/project retention settings.
- First non-English language and terminology owner/reviewer.
- Whether model routing optimizes first for accuracy, latency, cost, or a
  constrained combination after minimum quality gates are satisfied.
- Whether to add a `--semantic-skip-validator` or local-validator fallback mode
  for faster LLM experimentation while keeping rows pending for human review.

## 11. Success Criteria and Current Status
- Phase 1 exit criteria: **pending owner evidence** (≥95% field accuracy and
  ≤15-minute review time are not yet measured; technical lineage is complete).
- Zero silently-wrong gold values discovered downstream (every error traceable to a flagged ambiguity or open dispute, not a silent guess).
- Autopilot live consumption: **not started**.
- Foundry platinum consumption: **not started**.
- Month-over-month learned improvement: **not started**.
- Bitemporal point-in-time query: **implemented at the domain/reference-adapter
  level; not deployed to production Delta**.

## 12. Prioritized Next Steps

### Milestone N1 — owner decisions and evaluation inputs — complete for provider/policy gate

1. **Complete:** initial semantic-model provider is OpenAI. Production calls are
   permitted only when zero-data-retention is enabled/verified for the
   account/project, processing-region constraints are checked before deployment,
   application audit logs store request/response hashes rather than prompt text
   by default, response artifacts are controlled, and credentials come from
   environment-scoped service-account API keys.
2. **Complete for engineering start:** pilot counterparties remain
   owner-selected outside the repository; no production release is implied until
   ≥10 sanitized, owner-reviewable eligibility schedules are supplied.
3. **Complete for engineering start:** the required benchmark classes are
   scanned, multi-column, and nested/merged-cell documents; execution moves to
   N2 using the new OCR/layout coordinate contract.
4. **Complete for engineering start:** first non-English language/class pair is
   Spanish collateral eligibility schedules, with terminology review required
   before release.
5. **Complete:** verbatim silver clauses may be stored in local/dev silver and
   review packets; production confidential deployments may switch to
   locator/hash-controlled retrieval if compliance requires it.

**N1 exit achieved for this implementation boundary:** the repository records the
approved provider and data-handling policy needed to build N2/N3. Production
release remains gated by owner-verified documents, benchmark results, and Gate M.

### Milestone N2 — production document understanding — engineering complete; owner evidence pending

1. **Complete:** the selected PDF layout adapter is implemented behind the
   provider-neutral `LayoutAdapter` interface.
2. **Complete:** versioned bronze layout artifacts persist page geometry,
   line/token coordinates, table cells, merged-cell fields, confidence, and
   deterministic reading order.
3. **Complete for engineering start:** the benchmark runner publishes text, table,
   locator reproducibility, latency, cost, and layout artifact hash evidence. The
   owner-approved three-document evidence pack remains external to the repository.
4. **Complete:** image-only or structurally failed documents fail the layout
   quality gate and are kept out of semantic extraction until a passing artifact
   exists.

**N2 exit achieved for this implementation boundary:** reproducible locator
checks and the selected toolchain harness are implemented. Production release
remains gated by the owner-approved three-document benchmark decision, including
any required OCR adapter for image-only schedules.

### Milestone N3 — production semantic provider adapter — engineering complete; release evidence pending

1. **Complete:** the approved OpenAI Responses API adapter implements the
   existing `SemanticModel` protocol while keeping SDK types and credentials out
   of domain code.
2. **Complete:** CLI wiring creates distinct extractor and validator model
   sessions when `--semantic-provider openai` and both model names are supplied.
3. **Complete for local audit:** request/response hashes, provider/model/session
   identity, schema/constitution/prompt versions, latency, and token metadata are
   retained in the semantic call audit. Response artifact storage remains
   controlled by the existing hash-only local audit policy until production
   storage is selected in N5.
4. **Complete:** the adapter has bounded retries, timeouts, transient HTTP/rate
   limit handling, and fail-closed behavior.
5. **Complete in automated tests:** prompt-injection/system-field rejection,
   malformed JSON, missing evidence, unsupported fields, same-session rejection,
   provider-identity checks, strict OpenAI payload mapping, and transient retry
   behavior are covered.

**N3 exit achieved for this implementation boundary:** unknown templates can be
routed to Gate A through two independent OpenAI model sessions without
model-controlled system fields when credentials and ZDR policy are configured.
Production release remains gated by N2 benchmark evidence, owner-verified
corpora, and Gate M approval.

### Milestone N3B — local model/schema acceleration — engineering complete; evidence pending

1. **Complete:** local semantic provider path supports the same strict
   extractor/validator contracts without sending document text off-machine.
2. **Complete:** Ollama and OpenAI-compatible chat-completions adapters support
   timeout, retry, and output-token controls for model experimentation.
3. **Complete:** semantic schemas are centralized in `semantic_schemas/`; known
   deterministic public-profile parsers remain in `agents/public_schedules.py`.
4. **Complete:** the Fed collateral valuation/margins table has a semantic
   schema and fast local extractor path.
5. **Complete:** schema-defined extraction chunks can be run serially or
   concurrently with `--semantic-chunk-concurrency`, with per-chunk model-call
   audit records and field-path offsetting.
6. **Observed:** local Qwen 14B can run through Ollama, but on the owner's
   24 GB RAM Mac it is slow and inconsistent for larger JSON responses. Use
   deterministic/local schemas where structure is stable; reserve local LLMs for
   ambiguous layouts or exploratory extraction.

**N3B exit achieved for engineering:** the local acceleration path works for
the Fed valuation table and the known public profiles. Production acceptance
still requires owner-verified examples and review-time evidence.

### Milestone N4 — owner-verified release evidence

1. **Local baseline complete:** an authenticated confirm/correct/dispute
   workflow driven entirely from the terminal. The `review` CLI walks each field
   (value, status, locator, clause) and prompts the identified reviewer to
   confirm, correct, or dispute it (`--list` for a read-only view,
   `--pending-only` for re-review passes, `--corrections FILE` for scripted
   application). Actions preserve raw/normalized lineage, write a `reviewed`
   silver stage, and append to a durable correction log. The generated review
   packet is a read-only artifact. Disputes keep the document in
   `gate_a_pending` and block approval until resolved. A hosted/authenticated UI
   and the distiller feedback wiring remain to build.
2. Curate ≥10 owner-verified English eligibility schedules and ≥10 for the first
   non-English language/class pair.
3. Measure field accuracy, locator accuracy, ambiguity/dispute rate, review
   time, latency, and cost by profile/language/model version. **Harness
   delivered:** `document-refinery accuracy` scores the extractor against a
   golden corpus with independently authored ground truth (field/found-value
   accuracy, locator coverage, per-field/per-document breakdown, mismatch list,
   release gate). A 10-document realistic-synthetic corpus ships in
   `examples/golden_corpus/` (98.9% field accuracy, gate correctly NOT READY
   until documents are owner-verified). Point `--corpus` at owner-verified real
   documents to produce release evidence. The `accuracy` command scores the
   **deterministic** eligibility route by default and the **semantic route** with
   `--semantic-provider` (routing each case by its ground-truth `doc_class`), so
   semantic-only classes such as `collateral_rule_schedule` are scorable against
   a real model. The report folds in semantic **latency** and **token usage** per
   run, plus an estimated **cost** when the owner supplies `--cost-per-1k-input`/
   `--cost-per-1k-output` rates (no prices are hardcoded). **Intake + review-time
   harness delivered:**
   `document-refinery corpus-check` validates an owner corpus (ground-truth ↔
   document consistency, owner-verified counts, release blockers) before scoring,
   and `document-refinery review-time` reports measured owner review time against
   the ≤15-minute exit target from durable per-review timing captured by the
   `review` command. A `collateral_rule_schedule` intake scaffold ships in
   `examples/collateral_rule_corpus/` (owner-verified false, gate blocked).
   **Remaining (deferred):** metrics are reported per corpus run but not yet
   sliced **by model version** within a single report; add this when comparing
   models (it only matters for model-vs-model release decisions under Gate M).
4. Feed every correction into a golden case or constitution rule. **Delivered:**
   `document-refinery distill` turns the correction log into constitution-rule
   proposals (repeated corrections) and golden-case proposals (every
   owner-decided value, emitted as a ground-truth fragment via
   `--ground-truth-out`), with disputes surfaced as unresolved. Owner batch-
   approves; nothing is auto-applied.
5. Enforce Gate M against deterministic and semantic regression corpora.
6. Expand fast local schemas only when a document family has stable structure;
   otherwise add semantic schemas and keep the owner in Gate A.

**N4 exit:** ≥95% field accuracy, 100% found-value lineage, ≤15-minute owner
review time, no deterministic regression, and explicit owner release approval.

### Milestone N5 — production storage and full CSA economics

1. Implement object-storage and managed Delta adapters for bronze, silver, gold,
   workflow tasks, Gate A decisions, and semantic call audits. **Gold delivered:**
   a `DeltaGoldStore` (delta-rs, no Spark) writes real versioned Delta tables for
   `gold_eligibility_terms` to local or cloud object-store URIs, preserving
   bitemporal semantics and clause lineage (`--gold-store delta`); bronze/silver/
   tasks/audits remain local pending the same treatment.
2. Add canonical `gold_csa_terms` fields for threshold, MTA, IA, rounding,
   eligible currencies, interest, dispute timing, custody, and reuse rights.
   **Gate-S limits table delivered (engineering):** `gold_collateral_limits`
   (`sql/005_collateral_limits.sql`, domain `GoldCollateralLimit`, and
   `application/limit_promotion.py`) promotes validated `limit[i].*` silver rows
   from `collateral_rule_schedule` into canonical bitemporal portfolio-limit
   records — dimension, scoped value, absolute-or-percent value with basis and
   aggregation, schedule identity, and silver lineage. Promotion guardrails
   enforce percent∈[0,100], absolute⇒currency, and one document per record.
   Landing behind Gate S; pending owner-verified golden cases and Gate S sign-off
   before production, and not yet wired to the live approval flow (the
   rule-schedule class is a 0.x template).
3. Add schema migrations through Gate S and owner-verified CSA golden cases.
4. Add operational access control, encryption, secrets management, monitoring,
   retries, and recovery procedures.

**N5 exit:** one approved pilot counterparty is queryable in production Delta
with complete CSA economics and point-in-time lineage.

### Next steps to tackle (collateral-limit / rule-schedule track)

Follow-ups from the `collateral_rule_schedule` limit work, in order:

1. **Limit-consistency validator rules (§5.3).** Add the deterministic adversarial
   checks that mirror the `gold_collateral_limits` promotion guardrails: a
   value-scoped limit must not exceed its blanket parent for the same dimension;
   `basis` required when `limit_unit=percent`; percent limits ≤ 100%; absolute
   limits carry a currency; aggregation stated. Catches silent extraction errors
   before Gate A. Small, high-signal, no new storage.
2. **Wire limit promotion into the live pipeline.** Once `collateral_rule_schedule`
   earns a Gate S sign-off and an owner-verified golden set, route its validated
   `limit[i]` rows through `LimitPromotion` at approval and land them via the gold
   store (`--gold-store delta` alongside `gold_eligibility_terms`). Until then the
   promotion stays engineering-only (the class is a 0.x template).
3. **The optimizer join.** Compose `gold_collateral_limits` +
   `gold_eligibility_terms` + (future) `margin_requirement` gold into the
   constraint + demand set a collateral optimizer's solver consumes, joined on
   counterparty/agreement/CSA-schedule-ref. This is Phase 2/3 territory (Reconciler
   + platinum feature views) and must wait until N1–N5 gates are met.

### Then proceed to Phase 2

Only after N1-N5 should the project prioritize amendment reconciliation,
gold-to-Autopilot transformation, unified sign-off, platinum features, or broad
document-class expansion.

## 13. Handoff Instructions for the Next LLM
1. Read this document fully; locked decisions are binding. Lineage (Locked Decision 1) and silver-only extractors (2) are the structural core — do not weaken them for convenience.
2. The active phase is Phase 1B. N1 and N3 are engineering-complete; prioritize
   N2 layout/OCR benchmark evidence and N4 owner-verified release evidence next.
   Do not restart completed Phase 0/1 work.
3. Reuse the owner's bitemporal idioms from his FRED pipeline; match his engineering patterns (packaged Python repos, pytest suites, Delta/Databricks conventions, Bloomberg taxonomy alignment).
4. Extractor prompts must always include: role, class constitution, canonical schema with field dictionary, the lineage/ambiguity/not_found rules, and output schema. Validator prompts must be written independently — do not share extraction heuristics between them.
5. Optimize the owner's review throughput relentlessly: his correction bandwidth is the scarce resource, and every correction must flow into constitutions or golden sets via the distiller.
6. Keep chassis consistency with Model Foundry and Collateral Desk Autopilot (task table, gates, presenter altitudes, distiller loop, sandbox TTL). Shared code where practical.
7. For unknown templates, extend the provider-neutral semantic contracts before
   adding provider-specific logic. Keep API credentials and SDK response types
   outside the domain layer.
8. Never translate away evidence: store original-language clauses and locators;
   translations are optional review artifacts only.
9. Read `README.md`, `docs/phase-0-1-completion.md`,
   `docs/public-corpus-validation.md`,
   `docs/workflows/local-schema-catalog.md`, and ADRs 0001-0003 before changing
   architecture.
10. Run the synthetic regression, public PDF suite, Ruff, and strict mypy before
    every extractor, validator, prompt, constitution, schema, or routing change.
11. For local model work, start with `--semantic-provider local` to verify the
    route and row count, then test Ollama with `--semantic-chunk-concurrency 1`
    before trying parallel Qwen calls. On 24 GB RAM, multiple Qwen calls may
    be slower than serial execution due to memory pressure.
