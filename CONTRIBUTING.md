# Contributing

Changes must preserve the locked decisions in the handoff.

Before opening a pull request:

```bash
ruff check .
mypy src
pytest
```

Any extractor or extraction-constitution change must include golden-set
regression evidence. Schema changes are additive-preferred and require owner
approval (Gate S). Never add real counterparty documents, clauses, credentials,
or generated artifacts to this repository.

