# Document Refinery

Document Refinery turns financial documents into auditable, bitemporal,
quant-ready records. The first supported document class is collateral
eligibility schedules.

The repository provides a complete local Phase 0/1 reference implementation:

- immutable content-addressed bronze, text, and layout artifacts;
- landing-zone discovery and a durable task-state workflow;
- conservative profile classification and clause-level extraction;
- independent validation, a terminal Gate A review (confirm/correct/dispute),
  and read-only HTML/JSON review packets;
- deterministic, lineage-complete bitemporal gold promotion;
- executive, dashboard, and audit quality outputs;
- ten synthetic regression cases and five provenance-tracked public PDFs.

The deterministic path is production-independent. A provider-neutral semantic
extractor/validator contract is available for unknown templates, and the approved
OpenAI Responses API adapter can now be wired from the CLI with separate extractor
and validator sessions when zero-data-retention policy requirements are satisfied.

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

Review the extraction in the terminal — the `review` CLI walks each field
(value, status, locator, clause) and prompts the identified reviewer to
`[c]onfirm`, `c[o]rrect`, or `[d]ispute` it. Disputes block approval until
resolved:

```bash
document-refinery review DOC_ID --workspace .refinery --list        # read-only view
document-refinery review DOC_ID --workspace .refinery --reviewer "Joshua"
```

Corrections preserve the original clause lineage, are recorded in an append-only
correction log, and can also be applied non-interactively with
`--corrections FILE`. Once every field is confirmed or corrected, an identified
reviewer approves and lands gold:

```bash
document-refinery approve DOC_ID --workspace .refinery --approved-by "Joshua"
```

### Running an unknown layout (semantic path)

Documents that do not match a deterministic profile route to classification
review and stop unless a semantic extractor is configured. Choose a provider with
`--semantic-provider`; the bare flag defaults to `ollama`, the most secure option
(the model runs locally and document text never leaves your machine):

| Provider | Data leaves machine? | Needs | Use for |
|---|---|---|---|
| `ollama` (default) | No — local model | Ollama running + a pulled model | Real extraction on confidential docs |
| `openai` | Yes (OpenAI, ZDR-approved) | `OPENAI_API_KEY` + network | Approved production path |
| `openai-compatible` | Yes (third party) | `--semantic-base-url` + `OPENAI_COMPATIBLE_API_KEY` | Free/hosted testing on non-confidential docs |
| `local` | No — offline heuristic | nothing | Pipeline plumbing tests (not a real LLM) |

```bash
# Ollama — local model, data stays on your machine (secure default)
document-refinery run doc.pdf --workspace .refinery \
  --semantic-provider ollama \
  --semantic-extractor-model llama3.1 --semantic-validator-model llama3.1

# OpenAI — approved ZDR production provider
export OPENAI_API_KEY=sk-...
document-refinery run doc.pdf --workspace .refinery \
  --semantic-provider openai \
  --semantic-extractor-model <model> --semantic-validator-model <model>

# Generic OpenAI-compatible endpoint (Groq/Together/OpenRouter) — data leaves your machine
export OPENAI_COMPATIBLE_API_KEY=...
document-refinery run doc.pdf --workspace .refinery \
  --semantic-provider openai-compatible \
  --semantic-base-url https://api.groq.com/openai/v1/chat/completions \
  --semantic-extractor-model <model> --semantic-validator-model <model>

# Local heuristic double — no key, no network (pipeline testing only)
document-refinery run example_schedules/Example6_synthetic-triparty-eligibility-profile.txt \
  --workspace .refinery --semantic-provider local
```

All providers run the same route — separate extractor and validator sessions,
strict schema-to-silver conversion, semantic audit records, and Gate A. The
`openai-compatible` provider prints a notice that document text leaves the
machine and is **not** covered by the approved OpenAI ZDR policy; prefer `ollama`
for confidential agreements. The `local` provider is a heuristic double for the
pipe-delimited/`Key: Value` layout, not a production extractor, and makes no
accuracy claim. Gold promotion still requires the economic fields (`margin_type`,
`schedule_version`, `valid_from`, …); when they are absent, `approve` reports
`gold_promotion_blocked` and the document stays recoverable at Gate A.

Run the five provenance-tracked public examples:

```bash
document-refinery watch example_schedules \
  --workspace .refinery-public-examples \
  --source public-example
```

The public corpus covers portfolio concentration guidelines, CME performance
bond collateral, FICC and DTC haircut schedules, and an ISDA VM collateral
table. Each document reaches Gate A with clause-level source locators; nothing is
automatically approved. A sixth entry (`Example6`) is a synthetic unknown-layout
fixture that stops at classification review — the same conservative path real
CSAs, triparty schedules, and central-bank haircut tables take until a semantic
extractor is configured.

To grow the corpus with real documents, see
[`docs/test-corpus-downloads.md`](docs/test-corpus-downloads.md) for a curated
download list and wire each one in with `scripts/add_corpus_document.py`.

## CLI

| Command | Purpose |
|---|---|
| `document-refinery ddl` | Print packaged Delta DDL in migration order |
| `document-refinery regression --json` | Run the synthetic ten-document regression corpus |
| `document-refinery run FILE --workspace DIR [--language TAG] [--semantic-provider openai]` | Process one document and stop at Gate A |
| `document-refinery watch LANDING --workspace DIR [--language TAG] [--semantic-provider openai]` | Process every supported landing-zone document |
| `document-refinery review DOC_ID --workspace DIR [--list] [--reviewer NAME] [--pending-only] [--corrections FILE]` | Confirm/correct/dispute silver rows in the terminal before Gate A |
| `document-refinery approve DOC_ID --workspace DIR --approved-by NAME [--gold-store delta] [--gold-uri URI]` | Record Gate A approval and promote eligible rows (JSONL or Delta Lake) |

The workspace contains content-addressed raw/text/layout artifacts, SQLite task
state, extracted and validated silver JSONL, review packets, local gold JSONL,
and a three-altitude quality report.

### Production gold storage (Delta Lake)

By default gold lands to local JSONL (zero dependencies). For a production,
quant-queryable table, land gold to **Delta Lake** instead — real versioned
Delta tables that Databricks / Spark / DuckDB / Polars read directly:

```bash
pip install "document-refinery[delta]"

# Local Delta table
document-refinery approve DOC_ID --workspace .refinery --approved-by "Joshua" \
  --gold-store delta

# Cloud object store (credentials/region via the usual environment variables)
document-refinery run doc.pdf --workspace .refinery --approved-by "Joshua" \
  --gold-store delta --gold-uri s3://my-bucket/refinery/gold_eligibility_terms
```

The Delta adapter preserves the same bitemporal semantics (`valid_from/valid_to`,
`knowledge_from/knowledge_to`) and clause lineage as JSONL; each `approve` writes
a new Delta version, so point-in-time/time-travel queries and an audit history
come from the `_delta_log`. `deltalake`/`pyarrow` are an optional extra — the
core stays dependency-light and JSONL remains the default.

## Storage and records

- **Bronze:** immutable source bytes plus content hash and versioned text/layout
  artifacts.
- **Silver:** one row per canonical field, including raw and normalized values,
  clause text, locator, confidence, ambiguity, validation, and correction data.
- **Gold:** deterministic eligibility records with valid time, knowledge time,
  and every contributing silver extraction ID — landed to local JSONL or to a
  versioned Delta Lake table (`--gold-store delta`).
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

Forty-two automated tests cover domain invariants, bitemporal behavior, workflow
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

1. **Semantic production release remains gated.** The OpenAI adapter and CLI
   wiring exist, but production calls still require verified zero-data-retention
   settings, environment-scoped credentials, and Gate M release approval.
2. **English and known wording only without semantic configuration.** Classification relies on exact
   English-language signatures. Multilingual documents, paraphrases, and major
   template revisions are not semantically recognized.
3. **Image-only OCR remains gated.** The selected N2 PDF adapter persists
   confidence-bearing coordinates for text-bearing PDFs; scans and image-only
   tables fail closed until an OCR engine supplies passing layout artifacts.
4. **Owner benchmark evidence remains external.** The N2 benchmark runner records
   text, table, locator reproducibility, latency, cost, and artifact hashes, but
   production release still requires the owner-approved three-document evidence
   pack described in the handoff.
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
10. **Local review UX.** Gate A review runs in the terminal (`review` CLI:
    confirm/correct/dispute with a durable correction log) plus a read-only
    HTML/JSON packet and CLI approval. There is no hosted authenticated UI,
    dispute queue, or automatic distiller feedback loop yet.
11. **Local operational adapters.** Object storage, managed Delta merge jobs,
    access controls, monitoring, retries, and secrets management are not
    productionized.
12. **Incomplete owner evidence.** The ten-case regression set is synthetic and
    the five public documents are not owner-verified golden extractions.

## Extending beyond simple schedules

The hybrid semantic extraction foundation now provides strict JSON response
contracts, original-language lineage validation, separate-session enforcement,
model-call audit hashes, and routing for unknown profiles when adapters are
configured programmatically. The next tranche is:

1. Publish owner-approved N2 benchmark evidence for the selected layout adapter
   on scanned, multi-column, and nested/merged-cell schedules.
2. Add an approved production model adapter that emits the existing strict
   silver schema, including verbatim evidence and explicit
   `not_found`/ambiguity states.
3. Keep profile rules as high-precision anchors and use the model for varied
   language, unseen templates, and clause interpretation.
4. Run an independently prompted validator that re-derives sampled fields from
   source artifacts without sharing extractor reasoning; the CLI now creates
   distinct OpenAI extractor and validator sessions for semantic routing.
5. Add canonical schemas and constitutions for CSA economics, GMRA/MRA terms,
   lending fee schedules, and amendments.
6. Feed every owner correction into golden cases and versioned constitution
   rules before expanding release scope.

## Acceptance status

Phase 0/1 engineering is complete and executable locally. Production acceptance
remains evidence-dependent: the selected OCR/layout toolchain decision must be
owner-approved from the three-document benchmark, and the synthetic corpus must
be replaced or promoted with at least ten owner-verified schedules. The release gate reports
`phase_one_release_ready=false` until that evidence exists.

See [Phase 0/1 completion](docs/phase-0-1-completion.md) for the distinction
between delivered capability and owner acceptance.
