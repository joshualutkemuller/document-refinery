# Document Refinery

Document Refinery turns financial documents into auditable, bitemporal,
quant-ready records. The first supported document class is collateral
eligibility schedules.

The repository currently provides the Phase 0/1 domain foundation:

- immutable bronze, clause-level silver, and bitemporal gold SQL contracts;
- strict silver and gold domain models;
- deterministic eligibility-term promotion;
- independently defined extractor and validator prompt contracts;
- golden-set accuracy scoring and release gates;
- unit tests for lineage, ambiguity, promotion, bitemporal history, and gates.

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
```

## Repository map

```text
src/document_refinery/
  agents/       independent extractor and validator contracts
  application/  deterministic promotion and bitemporal history
  domain/       canonical value objects and invariants
  quality/      golden-set metrics and release gates
sql/            Databricks/Delta DDL
tests/          executable specification of locked decisions
docs/adr/       architecture decisions
```

## What remains evidence-dependent

OCR/layout tooling will be selected only after benchmarking three representative
documents (scanned, multi-column, and nested-table). The owner must also provide
at least ten verified schedules, pilot counterparties, and the chosen review UX
before Phase 1 can meet its exit criteria.

