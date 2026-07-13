# Model Card: Loan Recall Prediction Model

## Intended Use

Predict near-term lender-initiated recall risk for open securities lending loans for internal decision support.

## Users

Securities lending desks, operations teams, inventory managers, product owners, model risk reviewers, and governed optimization systems.

## Prohibited Use

- Fully autonomous loan termination.
- Direct client-facing predictions without review.
- Legal interpretation or contractual eligibility decisions.
- Dynamic pricing changes based solely on model output.

## Candidate Model Families

- Rules-based benchmark.
- Regularized logistic regression benchmark.
- Gradient-boosted tree champion candidate with calibration.
- Discrete-time survival model challenger after MVP.

## Required Validation Evidence

- Rolling out-of-time backtests.
- Precision and recall at top operational capacity bands.
- PR-AUC, Brier score, log loss, and calibration error.
- Segment stability by lender, security, market, asset class, and liquidity.
- Leakage review and point-in-time feature availability review.
