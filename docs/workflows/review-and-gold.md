# Review and Gold Promotion Workflow

This workflow starts after you run a document through `document-refinery run` or
`document-refinery watch`. The system writes silver rows first, creates a Gate A
review packet, and lands gold only after an identified reviewer confirms or
corrects every required value.

## 1. Run a document

For a known deterministic profile:

```bash
document-refinery run path/to/schedule.pdf --workspace .refinery
```

For an unknown layout with local Llama through Ollama:

```bash
document-refinery run path/to/schedule.pdf \
  --workspace .refinery \
  --semantic-provider ollama \
  --semantic-extractor-model llama3.1:8b \
  --semantic-validator-model llama3.1:8b
```

For the approved OpenAI provider, after verifying the account/project
zero-data-retention settings:

```bash
export OPENAI_API_KEY=sk-...

document-refinery run path/to/schedule.pdf \
  --workspace .refinery \
  --semantic-provider openai \
  --semantic-extractor-model gpt-5.5 \
  --semantic-validator-model gpt-5.5
```

The command prints a JSON object. Keep the `doc_id`.

```json
{
  "doc_id": "abc123...",
  "task_status": "gate_a_pending",
  "silver_fields": 84,
  "gold_records": 0,
  "review_html": ".refinery/reviews/abc123.review.html"
}
```

If the task status is `classification_review_required`, the document was unknown
and no semantic provider was configured. Re-run it with `--semantic-provider`.

## 2. Inspect Gate A

Use the read-only terminal view:

```bash
document-refinery review DOC_ID --workspace .refinery --list
```

You can also open the generated HTML review packet from the `review_html` path.
The HTML file is read-only; all review decisions happen through the CLI.

## 3. Review the rows

Walk every silver row interactively:

```bash
document-refinery review DOC_ID \
  --workspace .refinery \
  --reviewer "Joshua"
```

For each row, choose one action:

```text
[c]onfirm  c[o]rrect  [d]ispute  [s]kip  [q]uit
```

- `confirm`: value, clause, and locator are acceptable.
- `correct`: enter the correct value and an optional note.
- `dispute`: block approval until the issue is resolved.
- `skip`: leave the row unchanged for now.
- `quit`: stop the review and keep actions already collected.

For follow-up passes, review only rows that still need attention:

```bash
document-refinery review DOC_ID \
  --workspace .refinery \
  --reviewer "Joshua" \
  --pending-only
```

Corrections are durable. The system appends them to the correction log and folds
them into correction memory, so later reviews can surface the same fix as a
suggestion.

## 4. Apply corrections from a file

For repeatable or bulk review, pass a JSON corrections file:

```json
{
  "corrections": [
    {
      "extraction_id": "abc...",
      "action": "correct",
      "corrected_value": "2026-01-01",
      "note": "Effective date stated in header"
    },
    {
      "extraction_id": "def...",
      "action": "confirm"
    }
  ]
}
```

Apply it:

```bash
document-refinery review DOC_ID \
  --workspace .refinery \
  --reviewer "Joshua" \
  --corrections corrections.json
```

## 5. Approve and land gold

After every row is confirmed or corrected, approve the document:

```bash
document-refinery approve DOC_ID \
  --workspace .refinery \
  --approved-by "Joshua"
```

Successful approval prints:

```json
{
  "doc_id": "abc123...",
  "task_status": "gold_landed",
  "gold_records": 6
}
```

The default gold output is:

```text
.refinery/gold/eligibility_terms.jsonl
```

To land gold to a local Delta table instead:

```bash
document-refinery approve DOC_ID \
  --workspace .refinery \
  --approved-by "Joshua" \
  --gold-store delta
```

To choose a Delta URI:

```bash
document-refinery approve DOC_ID \
  --workspace .refinery \
  --approved-by "Joshua" \
  --gold-store delta \
  --gold-uri s3://my-bucket/refinery/gold_eligibility_terms
```

## If Gold Promotion Is Blocked

Approval can fail closed with `gold_promotion_blocked`. The document stays at
Gate A so you can correct it and try again.

Common causes:

- A row is still pending or disputed.
- A required field is `not_found`.
- A row is marked ambiguous.
- A required value has an invalid type or format.

Gold promotion currently requires these fields for each eligibility record:

```text
counterparty
agreement_id
schedule_version
margin_type
asset_criterion
eligible
valid_from
```

Fix the missing or disputed values:

```bash
document-refinery review DOC_ID \
  --workspace .refinery \
  --reviewer "Joshua" \
  --pending-only
```

Then approve again.

## Useful Inspection Commands

Review learned corrections:

```bash
document-refinery memory --workspace .refinery
document-refinery memory --workspace .refinery --json
```

Distill the correction log into owner-reviewable proposals (the learning loop,
§5.7): repeated corrections become constitution-rule proposals, every
owner-decided value becomes a golden-case proposal, and disputes are surfaced as
unresolved. Nothing is applied — the owner batch-approves.

```bash
document-refinery distill --workspace .refinery
```

Proposals are written to `.refinery/distiller/proposals.{json,md}`. To emit the
golden-case proposals as a ground-truth fragment you can review and merge into a
corpus for regression:

```bash
document-refinery distill --workspace .refinery \
  --ground-truth-out review/distilled_ground_truth.json
```

Run the packaged regression corpus:

```bash
document-refinery regression --json
```

Measure accuracy against a golden corpus:

```bash
document-refinery accuracy --corpus examples/golden_corpus
document-refinery accuracy --corpus examples/golden_corpus --json
```
