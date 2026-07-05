# ADR 0001: Phase 1 foundation

- Status: accepted
- Date: 2026-07-05

## Context

The handoff directs the project to begin with collateral eligibility schedules.
Real source documents and owner-verified golden records are not yet present, so
choosing OCR tooling or claiming extraction accuracy would be unevidenced.

## Decision

Build the contracts and deterministic core first:

- keep raw documents immutable in bronze;
- represent every field as a lineage-bearing silver extraction;
- isolate extractor and validator instructions;
- promote only confirmed or owner-corrected silver rows;
- aggregate eligibility fields deterministically into bitemporal gold records;
- gate releases on golden-set field accuracy.

The initial implementation is dependency-light Python with Delta SQL kept as
deployable source files. Platform adapters will depend inward on these contracts.

## Consequences

The core can be tested locally without Databricks or an LLM. OCR, model, storage,
and review-UI choices remain replaceable. End-to-end accuracy and review-time
targets cannot be asserted until owner-provided documents and corrections exist.

