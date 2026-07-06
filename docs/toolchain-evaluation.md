# Text and layout toolchain evaluation

## Current baseline

The local adapter supports UTF-8 text/Markdown and text-bearing PDFs through
`pypdf`. It produces stable page/line locators and is sufficient for exercising
the complete orchestration and governance path.

It is not designated as the production OCR/layout toolchain.

## Required evidence set

Production selection requires three sanitized owner documents:

1. a scanned schedule requiring OCR;
2. a multi-column schedule with cross-column reading-order risk;
3. a schedule containing nested or merged-cell tables.

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
disabled rather than silently degrading to unreliable text.

