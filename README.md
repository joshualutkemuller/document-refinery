# Document Refinery

Document Refinery turns financial documents into auditable, bitemporal,
quant-ready records. The first supported document class is collateral
eligibility schedules.

The repository provides a complete local Phase 0/1 reference implementation:

- immutable content-addressed bronze, text, and layout artifacts;
- landing-zone discovery and a durable task-state workflow;
- conservative profile classification and clause-level extraction;
- independent validation and HTML/JSON Gate A review packets;
- deterministic, lineage-complete bitemporal gold promotion;
- executive, dashboard, and audit quality outputs;
- ten synthetic regression cases and five provenance-tracked public PDFs.

This is currently a deterministic extraction system, not an LLM-backed semantic
reader. Agent prompt contracts exist, but no production model provider is wired
into the execution path.

## Non-negotiable invariants

1. Every extracted value carries a source clause and locator.
2. Extractors produce silver rows only.
3. Validators run independently from extractors.
4. Missing values are explicit `not_found` rows; ambiguity is never hidden.
5. Only validated rows can be promoted to gold.
6. Every gold record is bitemporal and retains all contributing silver IDs.
7. Extractor or constitution releases must pass golden-set regression checks.

See [the handoff](document_refinery_handoff.md) and
[the architecture decision](docs/adr/0001-phase-1-foundation.md) for the full
product and engineering context.

## Processing flow

```text
landing zone
  → immutable bronze document
  → versioned text and line-layout artifacts
  → conservative document profile
  → clause-level silver extractions
  → independent validation
  → Gate A review packet
  → identified owner approval
  → deterministic bitemporal gold
  → quality briefing and audit output
```

An extractor never writes gold. A document with an unknown profile, a disputed
field, or unresolved Gate A approval cannot be promoted.

## Supported inputs and profiles

The landing watcher accepts `.txt`, `.md`, and text-bearing `.pdf` files.

| Profile | Recognized content | Current extraction |
|---|---|---|
| Normalized schedule | Repository pipe-delimited reference format | Eligibility, haircuts, limits, currencies, ratings, and tenor |
| Portfolio guidelines | SEC-filed investment/portfolio requirements | Concentration rules and liquidation-period haircuts |
| CME | Acceptable performance-bond collateral schedule | Selected collateral classes and maturity-bucket haircuts |
| FICC GSD | Clearing-fund haircut schedule | Published security/maturity haircut rows |
| DTC | Eligible collateral haircut schedule | Security, rating, maturity, and haircut rows |
| ISDA VM | Paragraph 13 eligible-collateral table | ICAD assets, rating condition, maturity, and valuation-percentage-derived haircut |

Profile detection requires known English-language signatures. Unknown or changed
layouts are routed to classification review rather than forced through a parser.

For CSA documents, a published valuation percentage is retained as the raw
silver value and normalized to an economic haircut:

```text
haircut_pct = 100 - valuation_percentage
```

## Quick start

Requires Python 3.11 or newer. `pypdf` is installed as a core dependency;
development checks are installed through the `dev` extra.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
document-refinery ddl
document-refinery regression --json
```

Process one schedule and stop for Gate A review:

```bash
document-refinery run schedule.txt --workspace .refinery
```

After reviewing the generated HTML packet, an identified reviewer can approve
and land gold:

```bash
document-refinery approve DOC_ID --workspace .refinery --approved-by "Joshua"
```

Run the five provenance-tracked public examples:

```bash
document-refinery watch example_schedules \
  --workspace .refinery-public-examples \
  --source public-example
```

The public corpus covers portfolio concentration guidelines, CME performance
bond collateral, FICC and DTC haircut schedules, and an ISDA VM collateral
table. Each document reaches Gate A with clause-level source locators; nothing is
automatically approved.

## CLI

| Command | Purpose |
|---|---|
| `document-refinery ddl` | Print packaged Delta DDL in migration order |
| `document-refinery regression --json` | Run the synthetic ten-document regression corpus |
| `document-refinery run FILE --workspace DIR` | Process one document and stop at Gate A |
| `document-refinery watch LANDING --workspace DIR` | Process every supported landing-zone document |
| `document-refinery approve DOC_ID --workspace DIR --approved-by NAME` | Record Gate A approval and promote eligible rows |

The workspace contains content-addressed raw/text/layout artifacts, SQLite task
state, extracted and validated silver JSONL, review packets, local gold JSONL,
and a three-altitude quality report.

## Storage and records

- **Bronze:** immutable source bytes plus content hash and versioned text/layout
  artifacts.
- **Silver:** one row per canonical field, including raw and normalized values,
  clause text, locator, confidence, ambiguity, validation, and correction data.
- **Gold:** deterministic eligibility records with valid time, knowledge time,
  and every contributing silver extraction ID.
- **Quality:** executive prose, dashboard metrics, and a complete audit appendix.

The local filesystem, SQLite, and JSONL implementations are reference adapters.
The packaged SQL defines the intended Delta contracts for managed deployment.

## Validation evidence

The public corpus currently produces:

| Measure | Result |
|---|---:|
| Documents | 5 |
| Eligibility records | 154 |
| Silver fields | 2,156 |
| Validator disputes | 0 |
| Unresolved locators for found values | 0 |
| Final workflow state | 5 at `gate_a_pending` |

Thirty automated tests cover domain invariants, bitemporal behavior, workflow
transitions, public-file hashes, every public PDF profile, and Gate A behavior.
These are deterministic compatibility results, not owner-verified extraction
accuracy. See [public corpus validation](docs/public-corpus-validation.md).

## Repository map

```text
src/document_refinery/
  agents/          extractors, validators, and model prompt contracts
  application/     classification, workflow, gates, promotion, and history
  domain/          canonical records, enums, and invariants
  infrastructure/  local artifact, task, silver, and gold adapters
  quality/         golden-set metrics, regression, and reporting
  sql/             packaged Delta DDL
example_schedules/ provenance-tracked public PDF regression corpus
examples/          normalized sample schedule
tests/             executable specification of locked decisions
docs/              ADRs, validation evidence, roadmap, and toolchain rubric
```

## Current limitations

1. **No production language model.** Extraction is deterministic and
   profile-specific. The agent contracts are not connected to OpenAI or another
   model runtime.
2. **English and known wording only.** Classification relies on exact
   English-language signatures. Multilingual documents, paraphrases, and major
   template revisions are not semantically recognized.
3. **No OCR.** PDFs must contain an extractable text layer. Scans, handwriting,
   poor encodings, and image-only tables are unsupported.
4. **Limited layout understanding.** Layout artifacts preserve page and line
   anchors, not bounding boxes, merged cells, reading-order graphs, or complete
   table topology.
5. **Profile-bound extraction.** The five public parsers are validated against
   exact document hashes. Upstream revisions can require parser and golden-case
   updates.
6. **Eligibility-focused schema.** The current gold model does not yet promote
   full CSA economics such as threshold, MTA, independent amount, rounding,
   interest, dispute timing, or custody terms.
7. **No amendment reconciliation.** The pipeline does not link amendments to a
   base agreement, compute term diffs, or close superseded economic intervals
   across documents.
8. **Basic validation for public profiles.** It verifies evidence, normalized
   ranges, and source support; it does not yet perform a second semantic
   re-derivation with a separately prompted model.
9. **Uncalibrated confidence.** Rule-based confidence values are fixed and are
   not calibrated probabilities.
10. **Local review UX.** Gate A is generated HTML/JSON plus a CLI approval. There
    is no authenticated correction UI, dispute queue, or automatic distiller
    feedback loop.
11. **Local operational adapters.** Object storage, managed Delta merge jobs,
    access controls, monitoring, retries, and secrets management are not
    productionized.
12. **Incomplete owner evidence.** The ten-case regression set is synthetic and
    the five public documents are not owner-verified golden extractions.

## Extending beyond simple schedules

The next recommended tranche is a hybrid semantic extraction architecture:

1. Add OCR/layout backends and retain page coordinates, table cells, and reading
   order in bronze artifacts.
2. Introduce a model adapter that emits the existing strict silver schema,
   including verbatim evidence and explicit `not_found`/ambiguity states.
3. Keep profile rules as high-precision anchors and use the model for varied
   language, unseen templates, and clause interpretation.
4. Run an independently prompted validator that re-derives sampled fields from
   source artifacts without sharing extractor reasoning.
5. Add canonical schemas and constitutions for CSA economics, GMRA/MRA terms,
   lending fee schedules, and amendments.
6. Feed every owner correction into golden cases and versioned constitution
   rules before expanding release scope.

## Acceptance status

Phase 0/1 engineering is complete and executable locally. Production acceptance
remains evidence-dependent: OCR/layout tooling must be benchmarked on three real
representative documents, and the synthetic corpus must be replaced or promoted
with at least ten owner-verified schedules. The release gate reports
`phase_one_release_ready=false` until that evidence exists.

See [Phase 0/1 completion](docs/phase-0-1-completion.md) for the distinction
between delivered capability and owner acceptance.
