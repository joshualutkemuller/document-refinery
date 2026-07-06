# Public collateral schedule corpus

These files are public examples used to exercise document classification,
table/text extraction, clause lineage, validation, and Gate A review.
`manifest.json` records the authoritative source URL, retrieval date, SHA-256
hash, parser profile, and expected pipeline route for every document.

Each manifest entry declares an `expected_route`:

- `deterministic` — a known profile parses the document; it reaches
  `gate_a_pending` with at least `expected_minimum_eligibility_records`.
- `classification_review` — an unknown layout the classifier conservatively
  sends to owner review; without a configured semantic extractor the pipeline
  stops rather than force-parsing it. `Example6` is a synthetic fixture that
  exercises this route (real CSAs, triparty schedules, and central-bank haircut
  tables behave the same way).

Run the deterministic documents:

```bash
document-refinery watch example_schedules \
  --workspace .refinery-public-examples \
  --source public-example
```

The five deterministic documents reach `gate_a_pending`, each with a JSON and
HTML review packet; the command intentionally does not approve Gate A. The
synthetic `Example6` stops at classification review by design.

## Adding a document

Download the file (this repo's CI environment cannot fetch external hosts) and
wire it in with the helper, which computes the SHA-256, copies the file here,
and upserts the manifest entry. `--check` runs the pipeline first and reports the
actual route so you can set `--route` correctly:

```bash
python scripts/add_corpus_document.py path/to/file.pdf \
  --title "..." --source-url "https://..." \
  --route classification_review --profile unknown --check
```

See `docs/test-corpus-downloads.md` for a curated list of real documents to add.

Important limitations:

- These examples are public regression fixtures, not owner-verified golden data.
- The CME schedule does not state an effective date in its document text, so
  `valid_from` is emitted as `not_found` and gold promotion remains blocked.
- Table extraction is deterministic and profile-aware. Unknown document layouts
  still require classification review rather than being silently guessed.
- Re-downloads must be reviewed and their manifest hashes updated explicitly;
  upstream schedules may change without retaining the old file at the same URL.

