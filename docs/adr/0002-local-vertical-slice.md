# ADR 0002: Local Phase 0/1 vertical slice

- Status: accepted
- Date: 2026-07-05

## Context

Phase 0/1 needs an executable flow before platform and OCR vendor choices can be
made responsibly. Real financial documents are not stored in the repository.

## Decision

Use content-addressed filesystem artifacts, SQLite workflow state, and JSONL
silver/gold stores as local reference adapters. Keep domain, validation, Gate A,
promotion, and quality behavior independent of those adapters.

Support normalized text and text-bearing PDFs now. Do not claim a production OCR
selection until three representative owner documents have been benchmarked.

Treat the packaged ten-document corpus as synthetic regression evidence only.
Owner verification is a separate, machine-enforced release condition.

## Consequences

The full workflow can be developed and tested without cloud credentials or
confidential documents. Production storage and extraction adapters can be
replaced without weakening lineage or governance. Production acceptance remains
blocked on real-document evidence rather than silently downgraded.

