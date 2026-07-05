# Delivery roadmap

## Complete in this foundation

- [x] Professional packaged-Python repository and CI
- [x] Bronze, silver, and eligibility-gold Delta contracts
- [x] Domain enforcement for lineage, ambiguity, missing values, and correction
- [x] Independent extractor and validator contracts
- [x] Deterministic silver-to-gold promotion
- [x] Reference bitemporal knowledge-version closure
- [x] Golden-set scoring and Phase 1 release threshold

## Owner inputs required for the next tranche

- [ ] Provide three difficult, sanitized schedules for extraction-tool benchmarking
- [ ] Select two or three pilot counterparties
- [ ] Confirm verbatim-clause data-handling policy
- [ ] Choose Gate A / golden-set review UX
- [ ] Curate at least ten owner-verified schedule extractions
- [ ] Provide the FRED pipeline bitemporal helpers for convention alignment
- [ ] Name the first Autopilot rule-engine contract/version

## Evidence-driven implementation sequence

1. Benchmark text/layout extraction on scanned, multi-column, and nested-table
   examples; record accuracy, locator fidelity, latency, cost, and failure modes.
2. Implement immutable artifact storage and an idempotent landing-zone watcher.
3. Connect the eligibility extractor to the silver contract.
4. Build the separate-session stratified validator and owner dispute queue.
5. Implement Delta merge jobs from the tested promotion behavior.
6. Build the review flow and ten-document golden corpus.
7. Release only after ≥95% field accuracy, full gold lineage, and owner review
   time ≤15 minutes per document.

