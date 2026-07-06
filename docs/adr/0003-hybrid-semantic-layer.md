# ADR 0003: Hybrid semantic extraction layer

- Status: accepted
- Date: 2026-07-05

## Context

Deterministic profiles provide high precision for known schedules but cannot
generalize safely across unseen templates, varied legal phrasing, or additional
languages. Replacing them wholesale with a language model would weaken
repeatability and make failures harder to diagnose.

## Decision

Use deterministic-first routing. When a profile is unknown and an approved model
adapter is configured, route the document to a provider-neutral semantic
extractor constrained by the class constitution and canonical response schema.

Trusted application code validates the response and creates silver rows. The
model cannot assign system IDs, validator status, or gold values. Every found
value requires verbatim original-language evidence and a locator.

A separately prompted validator must use a different session and judge every
candidate row directly against the source artifact. Extractor and validator call
metadata, version identifiers, request hashes, and response hashes are retained.

Document content is always untrusted data. Instructions inside a document cannot
change system prompts, schemas, tools, gates, or validation policy.

## Consequences

Known profiles stay fast and deterministic. Semantic extraction can generalize
without bypassing lineage or Gate A. Provider-specific SDKs remain adapters
rather than domain dependencies.

No production provider is selected by this ADR. OCR/layout coordinates,
provider data-handling approval, owner-verified multilingual corpora, and model
quality gates remain prerequisites for production release.

