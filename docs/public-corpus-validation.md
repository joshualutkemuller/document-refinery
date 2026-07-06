# Public collateral corpus validation

Validation date: 2026-07-05

## Result

The five PDFs in `example_schedules/` run through the Phase 0/1 pipeline from
landing through independent validation and Gate A packet generation.

| Profile | Eligibility records | Silver fields | Final state |
|---|---:|---:|---|
| Portfolio guidelines | 6 | 84 | `gate_a_pending` |
| CME performance bond collateral | 17 | 238 | `gate_a_pending` |
| FICC GSD haircut schedule | 33 | 462 | `gate_a_pending` |
| DTC collateral haircut schedule | 92 | 1,288 | `gate_a_pending` |
| ISDA VM collateral table | 6 | 84 | `gate_a_pending` |
| **Total** | **154** | **2,156** | **5 pending reviews** |

All 2,156 silver fields received a validator decision. There were zero disputes,
zero pending validations, and zero unresolved locators for found values.
Optional fields absent from a document were emitted explicitly as `not_found`,
which produces aggregate field completeness of 56.73%.

## Verification

```bash
document-refinery watch example_schedules \
  --workspace /tmp/refinery-public-watch \
  --source public-example

pytest
ruff check .
mypy src
```

The automated suite contains 34 tests, including manifest hash verification and
an end-to-end Gate A assertion for each public PDF.

## Interpretation

This result demonstrates deterministic compatibility with these exact document
hashes. It is not an owner-verified accuracy score and does not authorize gold
promotion. The CME document does not state an effective date in its extracted
text, so its `valid_from` remains `not_found` until resolved during Gate A.

Profile detection is conservative. A document with an unknown layout or missing
signature is sent to classification review rather than forced through one of
these parsers.
