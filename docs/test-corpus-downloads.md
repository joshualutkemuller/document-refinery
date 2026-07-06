# Test corpus — documents to download and add

This is a curated shopping list of **real, public** collateral documents to
download and drop into `example_schedules/` so the pipeline can be exercised
against genuine layouts. They are not committed here because the CI/agent
environment's egress policy blocks all external hosts (SEC, Clearstream, DTCC,
the Fed, etc. all return `403` at the proxy). Download them from a normal browser
or a network that allows these hosts, then wire each one in with the helper.

## How to add each document

```bash
python scripts/add_corpus_document.py path/to/downloaded-file.pdf \
  --title "Human-readable title" \
  --source-url "https://exact/source/url" \
  --route classification_review \
  --profile unknown \
  --check
```

`--check` runs the document through the pipeline first (no semantic provider) and
prints the observed route:

- `deterministic` → it matched a known profile and reached Gate A. Re-run with
  `--route deterministic --profile <name> --expected-records <N>`.
- `classification_review` → unknown layout; it correctly stops for owner review.
  To actually extract it, configure a semantic provider. Use
  `--semantic-provider openai` for real extraction (needs `OPENAI_API_KEY` +
  network), or `--semantic-provider local` to run the offline heuristic double
  end-to-end with no key/network (good for verifying the pipeline plumbing on a
  new document before spending API calls). See the README's "Running an unknown
  layout" section.

Notes before you download:

- Use **text-bearing PDFs** (or TXT/MD). Scanned/image-only PDFs fail the N2
  layout quality gate by design until an OCR adapter is added.
- Respect each source's terms of use and copyright before committing a file to
  the repository. SEC EDGAR filings and US federal publications are public
  domain; exchange/CCP/ICSD schedules are published but copyrighted — mirror the
  existing corpus's provenance discipline (`source_url` + retrieval date + hash).
- After adding, run `pytest tests/test_public_schedules.py tests/test_corpus.py`
  to confirm the hash and route assertions pass.

## Recommended documents

| # | Document | Class | Suggested route | Why it's a good test |
|---|---|---|---|---|
| 1 | **SEC EDGAR — Credit Support Annex (CSA)** exhibits | CSA / VM terms | `classification_review` (until semantic configured) | The Tier-1 launch class: real negotiated thresholds, MTA, IA, eligible collateral, haircuts |
| 2 | **Clearstream — collateral criteria & allocation profiles** | Triparty eligibility | `classification_review` | Real ICSD triparty eligibility criteria + allocation profiles; varied layout |
| 3 | **Fed discount window — Collateral Margins Table** | Central-bank haircut schedule | `classification_review` (likely) | Public-domain, many asset classes and margins; multi-column table stress |
| 4 | **CCP acceptable collateral & haircuts** (LCH or Eurex) | CCP schedule | `classification_review` (likely) | Non-US CCP schedule beyond the CME/FICC/DTC profiles already covered |

### 1. SEC EDGAR — Credit Support Annex exhibits

- Where: SEC EDGAR full-text search — <https://efts.sec.gov> (human UI: EDGAR
  full-text search). Query for `"Credit Support Annex"` and open the `EX-10`
  exhibits; download the exhibit as PDF.
- Templates already in this corpus (same source): `Example5_EX-10.03.pdf`
  (JPMorgan/Cambridge ISDA) and `Example1_ex99-k2i.pdf` (investment guidelines).
- Why: this is the actual Phase-1 launch class. A handful of real CSAs is the
  best free proxy for the owner's own counterparty agreements.
- Add:
  ```bash
  python scripts/add_corpus_document.py edgar-csa.pdf \
    --title "SEC EDGAR EX-10 Credit Support Annex — <issuer>" \
    --source-url "https://www.sec.gov/Archives/edgar/data/.../exhibit.htm" \
    --route classification_review --profile unknown --check
  ```

### 2. Clearstream — collateral criteria & allocation profiles

- Where: <https://www.clearstream.com/caas/v1/media/1316102/data/3af7f0da7da47064dd799f4e63eae3b4/collateral-criteria-allocation-profiles.pdf>
- Related: "Haircuts on collateral value of securities"
  <https://www.clearstream.com/clearstream-en/products-and-services/settlement/a20108-2115096>
  and the CmaX Triparty Product Guide
  <https://www.clearstream.com/caas/v1/media/1318456/data/07a6291fc3091e5c4c611cd411741c9c/cmax-product-guide.pdf>
- Avoid the full eligible-securities list — Clearstream notes it is very large
  (they recommend opening it in MS Access); it is not a good fixture.
- Add:
  ```bash
  python scripts/add_corpus_document.py clearstream-criteria.pdf \
    --title "Clearstream collateral criteria and allocation profiles" \
    --source-url "https://www.clearstream.com/.../collateral-criteria-allocation-profiles.pdf" \
    --route classification_review --profile unknown --check
  ```

### 3. Federal Reserve discount window — Collateral Margins Table

- Where: <https://www.frbdiscountwindow.org> → Collateral → Collateral
  Valuation; download the collateral margins table (haircuts by asset class).
- Why: public-domain, broad asset coverage, and a genuinely multi-column table —
  directly useful for the N2 layout benchmark (scanned/multi-column/nested).
- Add:
  ```bash
  python scripts/add_corpus_document.py fed-collateral-margins.pdf \
    --title "Federal Reserve discount window collateral margins table" \
    --source-url "https://www.frbdiscountwindow.org/.../collateral-margins" \
    --route classification_review --profile unknown --check
  ```

### 4. CCP acceptable collateral & haircuts (LCH or Eurex)

- Where: LCH — <https://www.lch.com> (Risk Management → acceptable collateral &
  haircuts); or Eurex Clearing — <https://www.eurex.com> (eligible collateral /
  haircut list).
- Why: another CCP schedule beyond the CME/FICC/DTC profiles already in the
  corpus, to test classifier robustness and (with semantic) extraction breadth.
- Add:
  ```bash
  python scripts/add_corpus_document.py lch-acceptable-collateral.pdf \
    --title "LCH acceptable collateral and haircuts" \
    --source-url "https://www.lch.com/.../acceptable-collateral" \
    --route classification_review --profile unknown --check
  ```

## Optional: a Spanish-language schedule

The first non-English language/class pair named in the handoff (N1) is Spanish
collateral eligibility schedules. A public Spanish-language eligibility or
haircut schedule (e.g. from a Spanish clearing house or custodian) added the same
way exercises the original-language-lineage path once the semantic route and
terminology mapping are configured.
