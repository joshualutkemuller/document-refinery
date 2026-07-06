# Contributing

Changes must preserve the locked decisions in the handoff.

Before opening a pull request:

```bash
ruff check .
mypy src
pytest
```

Run `document-refinery regression --json` when extraction or constitution
behavior changes. Synthetic regression success does not authorize a production
release; the owner-verified document count must also satisfy the release gate.

Any extractor or extraction-constitution change must include golden-set
regression evidence. Schema changes are additive-preferred and require owner
approval (Gate S). Never add real counterparty documents, clauses, credentials,
or generated artifacts to this repository.
