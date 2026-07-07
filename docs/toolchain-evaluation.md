# Text and layout toolchain evaluation

## N2 selected adapter

The N2 implementation keeps the provider-neutral layout interface and adds a
`pdfplumber-layout` adapter for production PDF layout benchmarking. It preserves
page geometry, line/token coordinates, table-cell coordinates, confidence, and
deterministic reading-order locators in immutable bronze layout artifacts. The
existing `text-line-layout` adapter remains the deterministic fallback for UTF-8
text/Markdown fixtures and non-PDF smoke tests.

Scanned/image-only PDFs are intentionally not promoted by the `pdfplumber-layout`
adapter: if no confidence-bearing text coordinates are produced, the layout
quality report is `failed` with structural issues such as `no_text_coordinates`
and `missing_reading_order`. Semantic extraction must not run for those documents
until an OCR adapter produces artifacts that pass the structural gate.

## OCR adapter for image-only schedules

The `ocr-layout` adapter (`OcrLayoutAdapter`) closes the image-only gap. It is
driven by a vendor-neutral `OcrEngine` boundary so the OCR toolchain remains an
open owner decision (§10). Recognized words are grouped into deterministic,
reading-order lines with confidence-bearing token coordinates, letting a scanned
schedule produce a passing bronze layout artifact instead of failing the
structural gate. Because OCR confidence is lower than deterministic text
extraction, the adapter applies a dedicated `confidence_floor` (default `0.8`)
rather than the `0.95` text-adapter threshold; low-confidence pages still fail
with `low_layout_confidence` and stay out of semantic extraction.

A reference `TesseractOcrEngine` (Tesseract via `pytesseract` + `pypdfium2`,
behind the `ocr` extra) is provided; it is a thin I/O boundary, while all
line-grouping, reading-order, and quality logic lives in the tested adapter.

## Required evidence set

Production acceptance still requires the three sanitized owner documents named
in the handoff:

1. a scanned schedule requiring OCR;
2. a multi-column schedule with cross-column reading-order risk;
3. a schedule containing nested or merged-cell tables.

Run them with the `benchmark` CLI command (or `run_layout_benchmark` from
`document_refinery.infrastructure.layout_benchmark` directly), using the selected
layout adapter and document-specific minimum text/table thresholds:

```bash
document-refinery benchmark examples/layout_benchmark/manifest.json \
  --workspace .benchmark --adapter ocr
```

The manifest lists the benchmark cases (name, path, and per-document thresholds);
see `examples/layout_benchmark/`. The runner writes a publishable
`layout_benchmark_results.json` containing adapter version, text characters,
table-cell count, confidence, reading-order locator count, locator
reproducibility, latency, zero-dollar local adapter cost, layout artifact hash,
status, and all threshold issues. The command exits non-zero if any case fails.

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
