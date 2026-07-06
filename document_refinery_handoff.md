# Document Refinery — Build Plan & LLM Handoff Document

**Version:** 1.1 (hybrid semantic extraction tranche)
**Owner/CEO:** Joshua (quantitative researcher, securities finance / collateral / ML systems)
**Purpose of this document:** Complete context transfer to any LLM or engineer continuing development. Read fully before writing code. Locked decisions are binding unless the owner explicitly reverses them.
**Sibling projects:** Model Foundry (model lifecycle factory) and Collateral Desk Autopilot (desk operations copilot). Document Refinery is the third leg: it is the *ingestion and structuring layer* that turns unstructured financial documents into bitemporal, quant-ready Delta tables consumed by both siblings. It shares their chassis (task table, gates, presenter altitudes, distiller learning loop, sandbox TTL).

---

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
  margin_type STRING,               -- VM | IM | Repo
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

Semantic model calls must record provider, model, prompt/constitution/schema
versions, session ID, request timestamp, and response artifact hash. Document
content is untrusted data: instructions contained inside a document never alter
the system role, output schema, tools, gates, or validation policy.

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

### Phase 0 — Foundations (week 1–2)
- Bronze/silver DDL; landing zone + watcher job; text/layout extraction toolchain selection (test against 3 gnarly real schedules — scanned, multi-column, nested tables — before committing).
- Golden-set tooling: a lightweight review UI or notebook flow for the owner to confirm/correct silver rows efficiently (this is the highest-leverage UX in the project; owner review throughput determines everything).

### Phase 1 — One class, end to end (week 2–6) ← **start here**
- Single Tier-1 class: **collateral eligibility schedules**, 2–3 counterparties the owner knows cold (shared choice with Autopilot Phase 3 — same pilot, one effort).
- Build: classifier (trivial at one class), extractor, validator, gold_eligibility_terms, Gate A flow, golden set of ≥ 10 docs, quality briefing v1.
- Exit criteria: field-level accuracy ≥ 95% vs. golden set; every gold value traceable to a clause; owner review time per document ≤ 15 minutes.

### Phase 1B — Hybrid semantic generalization (active)
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

### Phase 2 — Reconciler + Autopilot integration (week 6–9)
- Amendment diffing, gold → rule-engine transform, unified sign-off with Autopilot.

### Phase 3 — Platinum features + Foundry integration (week 8–11)
- First feature views (`plat_eligibility_breadth`, `plat_terms_change_events`); register as Foundry data contracts; one Foundry experiment consumes them as proof.

### Phase 4 — Class expansion (week 11–16)
- Add CSA terms and lending fee schedules (Tier 1 completion), then GMRA/MRA. Each class follows the locked entry rule (schema + golden set + named consumer).

### Phase 5 — Learning-loop hardening + review downgrade (week 16–20)
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

## 10. Open Decisions (for owner)
- Text/layout extraction toolchain (evaluate in Phase 0 against real documents; options include open-source layout parsers vs. vendor OCR — decide on evidence, not defaults).
- Review UX for golden-set curation and Gate A (notebook, lightweight web form, or dashboard-embedded).
- Whether verbatim clause text in silver raises any internal data-handling constraints (compliance check; if so, store locators + hashes and fetch clauses on demand from bronze).
- Accuracy threshold and duration for downgrading a class from per-document to sampling review (default proposal: 98% / 3 months).
- Which two or three counterparties seed Phase 1 (align with Autopilot Phase 3).
- PII/confidentiality handling policy for Tier 2+ classes.
- Initial semantic model provider and approved data-retention/region policy.
- First non-English language and terminology owner/reviewer.
- Whether model routing optimizes first for accuracy, latency, cost, or a
  constrained combination after minimum quality gates are satisfied.

## 11. Success Criteria
- Phase 1 exit criteria met (≥ 95% field accuracy, full lineage, ≤ 15 min review per doc).
- Zero silently-wrong gold values discovered downstream (every error traceable to a flagged ambiguity or open dispute, not a silent guess).
- Autopilot consumes Refinery gold for at least one counterparty's live schedule by end of Phase 2.
- One Foundry model/experiment consumes platinum features by end of Phase 3.
- Documented month-over-month accuracy improvement per class attributable to constitution/golden-set growth.
- Owner can answer "what terms applied for counterparty X as known on date D" with one query.

## 12. Handoff Instructions for the Next LLM
1. Read this document fully; locked decisions are binding. Lineage (Locked Decision 1) and silver-only extractors (2) are the structural core — do not weaken them for convenience.
2. Ask the owner which phase is active before writing code.
3. Reuse the owner's bitemporal idioms from his FRED pipeline; match his engineering patterns (packaged Python repos, pytest suites, Delta/Databricks conventions, Bloomberg taxonomy alignment).
4. Extractor prompts must always include: role, class constitution, canonical schema with field dictionary, the lineage/ambiguity/not_found rules, and output schema. Validator prompts must be written independently — do not share extraction heuristics between them.
5. Optimize the owner's review throughput relentlessly: his correction bandwidth is the scarce resource, and every correction must flow into constitutions or golden sets via the distiller.
6. Keep chassis consistency with Model Foundry and Collateral Desk Autopilot (task table, gates, presenter altitudes, distiller loop, sandbox TTL). Shared code where practical.
7. For unknown templates, extend the provider-neutral semantic contracts before
   adding provider-specific logic. Keep API credentials and SDK response types
   outside the domain layer.
8. Never translate away evidence: store original-language clauses and locators;
   translations are optional review artifacts only.
