# Owner Action Items — What Unblocks N4 & Production

**Audience:** Joshua (owner/CEO).
**Purpose:** The engineering is far ahead of the evidence. Almost everything left
is gated on *your* decisions, documents, or sign-off — not on more code. This is
the short list of what only you can provide, ordered by leverage.

The one-line version: **name the pilot counterparties and hand over a few
sanitized real documents.** That single move unblocks the release-evidence track,
the first real accuracy number, and production landing of the new gold tables.

---

## 1. The critical bottleneck (unblocks the most)

- [ ] **Name 2–3 pilot counterparties** for Phase 1 (align with Autopilot Phase 3).
      → Gates: the whole N4 evidence track, Phase 1 exit, real accuracy numbers.
- [ ] **Supply ≥10 sanitized, owner-verifiable eligibility schedules** for those
      counterparties (English).
      → Gates: the Phase-1 release gate (needs ≥10 owner-verified docs at ≥95%).
- [ ] **Verify the ground truth** for each doc field-by-field, then flip
      `owner_verified: true`.
      → Tooling is ready: drop docs + `ground_truth.json` into a corpus dir and run
      `document-refinery corpus-check` then `document-refinery accuracy`.

**Until this is done:** every accuracy/review-time number stays "NOT READY," and
the new gold tables cannot go to production. This is the scarce resource the
whole project was designed around.

---

## 2. Gate sign-offs (owner-only approvals)

- [ ] **Gate S — approve the new gold DDL** before any of it lands in production:
      `gold_collateral_limits` (`sql/005_…`), `gold_margin_requirements`
      (`sql/006_…`). (Existing `gold_eligibility_terms` already in use.)
- [ ] **Gate S — approve the new semantic schemas** leaving `0.x` template status:
      `collateral_rule_schedule`, `margin_requirement`, `collateral_margin_operation`.
- [ ] **Name the downstream consumer** for those template classes (Locked
      Decision 6 requires a named consumer — is the collateral optimizer a
      committed consumer?).
- [ ] **Gate M — approve model/prompt/schema for release** once the golden sets
      exist (no lineage regression, passes the owner-verified corpora).

---

## 3. N2 — production document understanding (scanned/OCR)

- [ ] **Provide the 3 gnarly sanitized benchmark documents:** one scanned schedule
      (needs OCR), one multi-column schedule, one nested/merged-cell table.
- [ ] **Choose the production OCR/layout toolchain** after reviewing the benchmark
      report (`document-refinery benchmark <manifest> --adapter …`).

The harness, the layout adapters, and an OCR adapter (`ocr` extra) are all built
and tested — they just need your documents to produce the acceptance evidence.

---

## 4. Policy / compliance decisions (§10 open decisions)

- [ ] **Verbatim clause storage** — any internal data-handling constraint on
      storing clause text in silver? If yes, we switch to locator+hash retrieval.
- [ ] **PII / confidentiality policy** for Tier 2+ document classes.
- [ ] **Routing priority** after minimum quality gates: accuracy vs latency vs
      cost (or a constrained combination)?
- [ ] **Review-downgrade threshold** — confirm the default (98% for 3 consecutive
      months) before a class moves from per-document to sampling-based review.
- [ ] **`--semantic-skip-validator`** — do you want a faster local-experimentation
      mode that keeps rows pending for human review?
- [ ] **Token cost rates** — supply your provider's per-1k input/output prices to
      fold cost into `document-refinery accuracy --cost-per-1k-input/-output`.

---

## 5. Multilingual (when ready)

- [ ] **Confirm the first non-English language/class pair** (Spanish collateral
      eligibility was proposed) and **name the terminology owner/reviewer**.
- [ ] **Supply ≥10 owner-verified examples** for that pair (same bar as English).

---

## What is NOT waiting on you (already built or in progress)

For context — these are done or can proceed without any input from you, so they
are deliberately off this list:

- N2 OCR adapter + benchmark CLI; distiller feedback loop; N4 review-time +
  corpus-check harness; semantic-route accuracy scoring with latency/cost.
- The rule-schedule / CCP / margin schemas and their **gold contracts,
  promotions, consistency validator, opt-in pipeline landing, Delta storage, and
  the optimizer constraint-set join** — all engineering-complete behind Gate S.
- Remaining pure-engineering follow-ups I can pick up anytime: margin-requirement
  Delta landing, per-model-version metric slicing.

---

## Fastest path to a real release number

1. You: pick pilot counterparties (§1) and hand over a handful of sanitized docs.
2. Me: wire them into a corpus, run `corpus-check` + `accuracy`, report the score
   and the weakest fields.
3. You: verify/correct ground truth (the `review` CLI + distiller capture every
   correction), flip `owner_verified: true`.
4. You: Gate S sign-off (§2) → we land real gold and turn on the new tables.

Everything in steps 2 and 4-mechanics is already built and tested.
