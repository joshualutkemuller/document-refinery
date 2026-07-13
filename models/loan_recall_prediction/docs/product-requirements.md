# Product Requirements

## Objective

Score eligible open securities lending loans and estimate lender-initiated recall probabilities for 1, 3, 5, and 10 business-day horizons.

## Functional Requirements

- Score all eligible open loans.
- Produce calibrated probabilities for each approved horizon.
- Assign operational risk bands: Low, Moderate, High, Critical.
- Return at least three reason codes per prediction.
- Store predictions, features, model version, feature set version, and outcomes.
- Support replay, backtesting, duplicate-alert suppression, and user action capture.

## Nonfunctional Requirements

- Daily scoring completes before the agreed market cut-off.
- Predictions are reproducible from versioned code, data, and configuration.
- Sensitive loan, lender, borrower, and client data is access-controlled.
- Data freshness, schema, and range checks gate production alerts.
- Rollback to the prior approved model is supported.

## MVP Recommendation

The first release should be a decision-support workflow using daily batch scoring, calibrated gradient-boosted trees plus a logistic benchmark, dashboard/API delivery, shadow-mode pilot, and monthly model performance review.
