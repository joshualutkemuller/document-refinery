# Document Refinery

Document Refinery turns financial documents into auditable, bitemporal,
quant-ready records. The first supported document class is collateral
eligibility schedules.

The repository provides a complete local Phase 0/1 vertical slice:

- immutable content-addressed bronze, text, and layout artifacts;
- landing-zone discovery and a durable task-state workflow;
- conservative classification and clause-level extraction;
- independent validation and HTML/JSON Gate A review packets;
- deterministic, lineage-complete bitemporal gold promotion;
- executive, dashboard, and audit quality outputs;
- a ten-document synthetic regression corpus with separate technical and
  owner-verification gates.

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

## Quick start

Requires Python 3.11 or newer.

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

## Repository map

```text
src/document_refinery/
  agents/       independent extractor and validator contracts
  application/  deterministic promotion and bitemporal history
  domain/       canonical value objects and invariants
  infrastructure/ local artifact, task, silver, and gold adapters
  quality/      golden-set metrics and release gates
example_schedules/ provenance-tracked public PDF regression corpus
sql/            Databricks/Delta DDL
tests/          executable specification of locked decisions
docs/adr/       architecture decisions
```

## Acceptance status

Phase 0/1 engineering is complete and executable locally. Production acceptance
remains evidence-dependent: OCR/layout tooling must be benchmarked on three real
representative documents, and the synthetic corpus must be replaced or promoted
with at least ten owner-verified schedules. The release gate reports
`phase_one_release_ready=false` until that evidence exists.

See [Phase 0/1 completion](docs/phase-0-1-completion.md) for the distinction
between delivered capability and owner acceptance.
