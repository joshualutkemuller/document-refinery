# Public collateral schedule corpus

These files are public examples used to exercise document classification,
table/text extraction, clause lineage, validation, and Gate A review.
`manifest.json` records the authoritative source URL, retrieval date, SHA-256
hash, parser profile, and minimum expected record count for every document.

Run the complete corpus:

```bash
document-refinery watch example_schedules \
  --workspace .refinery-public-examples \
  --source public-example
```

The expected result is five documents in `gate_a_pending`, with a JSON and HTML
review packet for each. The command intentionally does not approve Gate A.

Important limitations:

- These examples are public regression fixtures, not owner-verified golden data.
- The CME schedule does not state an effective date in its document text, so
  `valid_from` is emitted as `not_found` and gold promotion remains blocked.
- Table extraction is deterministic and profile-aware. Unknown document layouts
  still require classification review rather than being silently guessed.
- Re-downloads must be reviewed and their manifest hashes updated explicitly;
  upstream schedules may change without retaining the old file at the same URL.

