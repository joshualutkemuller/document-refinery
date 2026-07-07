# Collateral rule-schedule intake corpus (scaffold)

Intake scaffold for the `collateral_rule_schedule` class, seeded from the five
public sources in [`docs/real-world-collateral-schedule-examples.md`](../../docs/real-world-collateral-schedule-examples.md).

**This is a template, not evidence.** Every case is `owner_verified: false` and
the `.txt` files are *illustrative transcriptions* of the summary tables in that
doc — not the real documents. They exist so the intake gate and schema can be
exercised immediately. Nothing here counts toward the N4 release gate until the
owner fetches, sanitizes, and verifies the real documents.

## Sources

| Case | Source | Class fit |
| --- | --- | --- |
| `01-sec-isda-csa-1994` | SEC-filed ISDA CSA (1994 NY Law) | Rich negotiated CSA |
| `02-isda-template-schedule` | ISDA UMR IM template schedules | Rating-bucketed schedule |
| `03-isda-vm-csa-2016` | 2016 ISDA Variation Margin CSA | Regulatory VM schedule |
| `04-isda-operational-eligibility` | ISDA "Documentation to Operations" guidance | Full operational rule engine |
| `05-dealer-csa-rule` | Dealer/SEC-filed CSA rule | Rule engine w/ wrong-way-risk + priority |

Source URLs are recorded per case in `ground_truth.json`.

## Verification workflow (per document)

1. **Fetch** the source from its URL.
2. **Sanitize** — remove anything confidential; these are the *public* references,
   but confirm before use.
3. **Extract text** and replace the illustrative `{case_id}.txt` with the real
   document text (keep the same file name).
4. **Verify** every field in `ground_truth.json[{case_id}].expected` against the
   fetched document. Fix values, add rows, remove the illustrative `note`.
5. Fill the `[REPLACE ...]` counterparty/agreement placeholders with verified
   values (or a documented sanitized alias).
6. Set `owner_verified: true` only once you have independently confirmed the case.

## Validate the corpus

```bash
document-refinery corpus-check --corpus examples/collateral_rule_corpus
```

`corpus-check` verifies structure (every case has a `.txt`, no orphan files,
string-typed expected values) and reports how many owner-verified documents are
still needed for the release gate (≥10). It exits non-zero on structural
problems.

## Scoring note

`document-refinery accuracy` currently scores with the **deterministic
eligibility extractor**, which targets the narrow `collateral_eligibility_schedule`
class (asset/haircut tables). This corpus targets the richer
`collateral_rule_schedule` class, whose `rule[i].*` fields are extracted on the
**semantic route**. Field-accuracy scoring for this class therefore depends on
semantic-route scoring, which is not yet wired into the `accuracy` command —
`corpus-check` is the immediate, honest intake gate. Wiring semantic-route
accuracy scoring is the natural follow-up once the first documents are verified.
