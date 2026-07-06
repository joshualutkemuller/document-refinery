# Phase 0/1 completion record

Date: 2026-07-05

## Outcome

The Phase 0 and Phase 1 software path is implemented end to end:

`land → artifact extraction → classify → extract silver → independent validate
→ Gate A packet → owner approval → deterministic gold → quality report`

The repository can run that path locally on normalized text schedules and
text-bearing PDFs. All locked architectural decisions are enforced in code.

## Delivered controls

| Handoff requirement | Implementation |
|---|---|
| Immutable bronze | SHA-256 content-addressed raw objects; collision checks |
| Versioned text/layout | Hash-addressed text and line-layout artifacts |
| Landing watcher | Stable discovery for TXT, Markdown, and PDF |
| Task chassis | Durable SQLite state machine with guarded transitions |
| Classifier | Conservative one-class classifier; low confidence blocks |
| Silver-only extraction | Extractor returns only silver records |
| Clause lineage | Source clause and locator are required domain fields |
| Missing/ambiguous handling | Explicit `not_found`; ambiguity requires notes |
| Independent validator | Separate parser and consistency checks |
| Gate A | HTML/JSON packet and identified reviewer decision |
| Gold promotion | Validated rows only; full silver ID lineage |
| Bitemporal history | Valid and knowledge time with version closure |
| Golden regression | Ten synthetic documents, 100% expected field accuracy |
| Presenter altitudes | Executive prose, dashboard JSON, audit appendix |
| Delta contracts | Bronze, silver, gold, tasks, gates, and regression results |

## Acceptance gates

Engineering completion and production acceptance are intentionally different.

- Technical regression: **passing** — 10 synthetic documents, 100% expected
  field accuracy, zero validator disputes.
- Owner-verified golden set: **awaiting owner evidence** — 0 of 10 documents.
- OCR/layout selection: **awaiting representative documents** — scanned,
  multi-column, and nested-table samples have not been supplied.
- Review time ≤15 minutes: **not measurable** until owner review sessions occur.
- Pilot counterparties: **not selected**.

The CLI will not report Phase 1 release readiness until ten documents are marked
owner-verified and field accuracy remains at least 95%.

## Productionization boundary

The local adapters are intentionally transparent and testable. Production
deployment must add controlled object storage, managed Delta merge jobs,
identity/access policies, secrets management, monitoring, and the selected
OCR/layout backend. Those adapters must preserve the domain and gate behavior
demonstrated here.

