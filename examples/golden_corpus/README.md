# Golden corpus — collateral schedules + ground truth

Ten varied collateral schedules with independently authored ground truth, used to
**measure extraction accuracy** (`document-refinery accuracy`).

| # | Document | Type |
|---|---|---|
| 01 | Sterling Bridge Bank, N.A. | ISDA CSA (VM), USD |
| 02 | Meridian Global Markets SA | ISDA CSA (VM), EUR |
| 03 | Halcyon Asset Management LLP | ISDA CSA (IM, SIMM) |
| 04 | Pacific Rim Clearing Ltd | Tri-party repo (GMRA) |
| 05 | Northwind Securities Inc | Securities lending (GMSLA) |
| 06 | Thames Capital Partners LLP | CSA (VM), GBP / Gilts |
| 07 | Sakura Trust Bank, Ltd. | CSA (VM), JPY / JGB |
| 08 | Andes Frontier Bank | CSA (VM), EM sovereign USD |
| 09 | Coastal Reserve Trust | CSA (VM), cash & T-bills |
| 10 | Global Nexus Custody | Tri-party basket (Repo), multi-ccy |

## Important: what these are and are not

- **Realistic synthetic fixtures**, modeled on the structure and economics of real
  collateral schedules (CSAs, tri-party eligibility, GMRA/GMSLA). Counterparties
  are fictional.
- **Not real published documents.** The build environment cannot fetch them (egress
  is blocked); see [`../../docs/test-corpus-downloads.md`](../../docs/test-corpus-downloads.md)
  for real documents to download.
- **Not owner-verified.** `owner_verified` is `false` for every case, so the
  Phase-1 release gate stays `NOT READY` regardless of the accuracy number — by
  design. Owner verification is the missing N4 evidence.

## Ground truth is independent

`ground_truth.json` records the **human-correct** normalized value for every
field — authored independently of the extractor. A few documents carry real-world
variations (`Variation Margin` vs `VM`, `1.50%` vs `1.5`, currency names vs ISO
codes, `Y` vs `yes`) whose ground truth stays correct, so the harness surfaces
**genuine extractor normalization gaps** (~99% accuracy) rather than grading the
extractor against itself.

## Usage

```bash
document-refinery accuracy                       # score this corpus
document-refinery accuracy --json                # machine-readable report
document-refinery accuracy --corpus /path/to/owner/docs   # your verified docs
```

Regenerate with `python scripts/build_golden_corpus.py` (prints the extractor-vs-
ground-truth gaps as a self-check).

## Measuring your own documents

Drop `*.txt` schedules and a `ground_truth.json` (`{case_id: {title,
owner_verified, expected: {field_path: value}}}`) into a directory and point
`--corpus` at it. Set `owner_verified: true` on cases you have verified; once ≥10
verified cases score ≥95%, the release gate reads `READY`.
