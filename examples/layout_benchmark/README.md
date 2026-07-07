# N2 layout/OCR benchmark

This directory holds the manifest for the three-document N2 benchmark named in the
handoff (§12-N2) and `docs/toolchain-evaluation.md`. The benchmark harness itself
lives in `document_refinery.infrastructure.layout_benchmark` and is reachable from
the CLI.

## Running

```bash
document-refinery benchmark examples/layout_benchmark/manifest.json \
  --workspace .benchmark --adapter pdfplumber
```

`--adapter` selects the layout backend under test:

- `pdfplumber` — text-bearing PDFs (default). Needs the `pdf` extra.
- `ocr` — scanned/image-only PDFs via the OCR adapter. Needs the `ocr` extra
  (`pip install -e ".[ocr]"`) and a system `tesseract` binary.
- `text-line` — deterministic text/Markdown fallback (used for smoke checks).

The runner writes `layout_benchmark_results.json` to the workspace with adapter
version, text characters, table-cell count, mean confidence, reading-order
locator count, locator reproducibility (primary vs. replay pass), latency, cost,
and the layout artifact SHA-256. Exit code is non-zero if any case fails its
thresholds or the structural quality gate.

## The required documents

`manifest.json` ships as a **template** with placeholder paths under
`documents/`. Supply the three owner-approved, sanitized schedules and update the
paths/thresholds:

1. a scanned schedule requiring OCR (run with `--adapter ocr`);
2. a multi-column schedule with cross-column reading-order risk;
3. a schedule containing nested or merged-cell tables.

The documents themselves are intentionally **not** committed — they are the
owner-approved evidence set and stay external to the repository until sanitized.
Point the manifest at wherever they live locally.
