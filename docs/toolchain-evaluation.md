# Text and layout toolchain evaluation

## N2 selected adapter

The N2 implementation keeps the provider-neutral layout interface and adds a
`pdfplumber-layout` adapter for production PDF layout benchmarking. It preserves
page geometry, line/token coordinates, table-cell coordinates, confidence, and
deterministic reading-order locators in immutable bronze layout artifacts. The
existing `text-line-layout` adapter remains the deterministic fallback for UTF-8
text/Markdown fixtures and non-PDF smoke tests.

Scanned/image-only PDFs are intentionally not promoted by this adapter: if no
confidence-bearing text coordinates are produced, the layout quality report is
`failed` with structural issues such as `no_text_coordinates` and
`missing_reading_order`. Semantic extraction must not run for those documents
until an OCR adapter produces artifacts that pass the structural gate.

## Required evidence set

Production acceptance still requires the three sanitized owner documents named
in the handoff:

1. a scanned schedule requiring OCR;
2. a multi-column schedule with cross-column reading-order risk;
3. a schedule containing nested or merged-cell tables.

Run them with `run_layout_benchmark` from
`document_refinery.infrastructure.layout_benchmark`, using the selected layout
adapter and document-specific minimum text/table thresholds. The runner writes a
publishable `layout_benchmark_results.json` containing adapter version, text
characters, table-cell count, confidence, reading-order locator count, status,
and all threshold issues.

## Scoring rubric

Each candidate must be run without manual cleanup and scored on:

| Dimension | Weight | Minimum |
|---|---:|---:|
| Character/text fidelity | 20% | 98% |
| Table-cell structure fidelity | 25% | 95% |
| Source-locator reproducibility | 25% | 100% |
| Eligibility field accuracy | 20% | 95% |
| Operational cost/latency | 5% | Recorded |
| Data-handling fit | 5% | Approved |

A candidate that cannot reproduce a clause locator is ineligible regardless of
aggregate score. Record tool/version, configuration, document hash, runtime,
cost, extracted artifact hashes, and all observed failures for every run.

## Decision gate

The owner approves the production backend after reviewing the benchmark report.
Until then, production ingestion of scanned or structurally complex PDFs remains
blocked from semantic extraction rather than silently degrading to unreliable
text.
