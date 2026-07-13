# Loan Recall Prediction Model

This folder contains a standalone model blueprint and reference implementation for a securities lending loan recall prediction platform. It is intentionally isolated from the core `document_refinery` package so it can evolve, be validated, and be governed as a separate model.

## Objective

For every eligible active securities lending loan, estimate the probability that a lender-initiated recall will occur within 1, 3, 5, and 10 business-day horizons. The model output is designed for decision support, alerts, dashboarding, inventory workflows, and controlled optimizer inputs.

## MVP Scope

- Daily batch scoring with optional intraday refresh points.
- Binary recall probabilities for 1d, 3d, 5d, and 10d horizons.
- Risk bands: `LOW`, `MODERATE`, `HIGH`, and `CRITICAL`.
- Stable reason codes and data-quality status in every prediction.
- Point-in-time label construction helpers.
- JSON-compatible API request and response schemas.
- Governance documentation for model risk and operational handoff.

## Repository Layout

```text
models/loan_recall_prediction/
├── README.md
├── configs/
│   └── base.yaml
├── docs/
│   ├── architecture.md
│   ├── data-dictionary.md
│   ├── model-card.md
│   ├── product-requirements.md
│   └── runbook.md
├── src/loan_recall_prediction/
│   ├── api/
│   ├── common/
│   ├── features/
│   ├── labels/
│   └── scoring/
└── tests/
```

## Minimal Local Checks

From the repository root:

```bash
python -m pytest models/loan_recall_prediction/tests
```

The implementation avoids mandatory third-party model libraries. Production training can add approved packages such as scikit-learn, XGBoost, LightGBM, or CatBoost after model-risk and platform review.

## Intended Use

Use this model only as a decision-support signal for internal securities lending desks, operations, inventory management, and governed optimization workflows. Do not use it for autonomous loan termination, direct client communication, legal interpretation, or unapproved pricing actions.
