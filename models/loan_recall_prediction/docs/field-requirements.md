# Loan Recall Prediction Field Requirements

This document defines the minimum required fields, data types, nullability rules, and validation expectations for the loan recall prediction model. These tables are intended for data engineering, quantitative research, model validation, platform engineering, and model-risk handoff.

## Field Requirement Conventions

| Column | Meaning |
|---|---|
| Field | Stable field name used in contracts, features, tables, or API payloads. |
| Type | Logical data type expected by the model contract. |
| Required | Whether the field is mandatory for the MVP pipeline. |
| Nullable | Whether null values are permitted after validation. |
| Example | Representative value. |
| Validation / Notes | Key quality, lineage, or point-in-time rule. |

## Loan Snapshot Input Fields

One record is required per eligible open loan and scoring timestamp.

| Field | Type | Required | Nullable | Example | Validation / Notes |
|---|---|---:|---:|---|---|
| `loan_id` | string | Yes | No | `LN123` | Primary loan identifier; must be stable across events. |
| `as_of_timestamp` | timestamp | Yes | No | `2026-07-10T13:00:00Z` | Prediction timestamp; all features must be available at or before this time. |
| `security_id` | string | Yes | No | `US0378331005` | Security identifier used for joins to market and corporate-action data. |
| `lender_id` | string | Yes | No | `LENDER_A` | Lender or agent-lender identifier used for historical recall behavior. |
| `borrower_id` | string | Yes | No | `BORROWER_1` | Borrower or desk identifier used for operational segmentation. |
| `open_date` | date | Yes | No | `2026-05-01` | Must be on or before `as_of_timestamp`. |
| `current_quantity` | decimal | Yes | No | `100000` | Must be greater than zero for active loans. |
| `original_quantity` | decimal | Yes | Yes | `150000` | Null allowed only when source history is unavailable. |
| `market_value` | decimal | Yes | No | `1850000.25` | Must be non-negative and currency-aligned. |
| `currency` | string | Yes | No | `USD` | ISO currency code. |
| `fee_or_rebate` | decimal | Yes | Yes | `1.75` | Required for production scoring when available; impute only under approved policy. |
| `loan_type` | string | Yes | No | `OPEN` | Approved values include `OPEN` and `TERM`. |
| `collateral_type` | string | Yes | Yes | `CASH` | Null is permitted for markets where collateral is managed externally. |
| `settlement_location` | string | Yes | Yes | `DTC` | Used for operational severity and cut-off rules. |
| `already_under_recall_flag` | boolean | Yes | No | `false` | Loans already under recall are excluded from new recall labeling/scoring. |

## Recall Event and Outcome Fields

These fields define labels, outcomes, and post-prediction feedback. Recall labels must use only events available after the prediction timestamp and must exclude borrower-initiated returns.

| Field | Type | Required | Nullable | Example | Validation / Notes |
|---|---|---:|---:|---|---|
| `event_id` | string | Yes | No | `EVT789` | Unique event identifier for deduplication and audit. |
| `loan_id` | string | Yes | No | `LN123` | Must join to an eligible loan snapshot. |
| `event_timestamp` | timestamp | Yes | No | `2026-07-13T09:15:00Z` | Timestamp used to determine horizon labels. |
| `event_type` | string | Yes | No | `LENDER_RECALL` | Only lender-initiated recall events are positive labels. |
| `event_source` | string | Yes | No | `SWIFT` | Source channel for lineage and reconciliation. |
| `recall_quantity` | decimal | Yes | Yes | `50000` | Required when supplied by source; supports partial recall modeling. |
| `full_recall_flag` | boolean | Yes | Yes | `false` | True when recall quantity equals remaining open quantity. |
| `cancelled_flag` | boolean | Yes | No | `false` | Cancelled recalls are excluded or separately modeled. |
| `duplicate_event_flag` | boolean | Yes | No | `false` | Duplicate events must be suppressed before label generation. |
| `user_action` | string | No | Yes | `PREPARE_REPLACEMENT` | Captured after alert review for feedback learning. |
| `intervention_success` | boolean | No | Yes | `true` | Records whether the action reduced recall-related cost or risk. |
| `estimated_value` | decimal | No | Yes | `12500.00` | Optional business value estimate from avoided fail, buy-in, or sourcing cost. |

## Feature Store Fields

Every feature must be point-in-time correct and traceable to a source timestamp, effective timestamp, ingestion timestamp, and availability timestamp.

| Field | Type | Required | Nullable | Example | Validation / Notes |
|---|---|---:|---:|---|---|
| `entity_id` | string | Yes | No | `LN123` | Loan, security, lender, or composite entity key. |
| `entity_type` | string | Yes | No | `LOAN` | Approved values include `LOAN`, `SECURITY`, `LENDER`, `MARKET`, and `OPERATIONAL`. |
| `feature_name` | string | Yes | No | `lender_recall_rate_10d` | Stable versioned feature identifier. |
| `feature_value` | decimal/string/boolean | Yes | Yes | `0.18` | Type must match feature catalog definition. |
| `feature_version` | string | Yes | No | `v1` | Increment when definition, source, or transformation changes. |
| `source_system` | string | Yes | No | `LOAN_BOOK` | System of record or approved derived source. |
| `source_timestamp` | timestamp | Yes | No | `2026-07-10T12:45:00Z` | Timestamp from the source system. |
| `effective_timestamp` | timestamp | Yes | No | `2026-07-10T00:00:00Z` | Business-effective time for the feature. |
| `ingestion_timestamp` | timestamp | Yes | No | `2026-07-10T12:55:00Z` | Time the value arrived in the platform. |
| `availability_timestamp` | timestamp | Yes | No | `2026-07-10T13:00:00Z` | Must be on or before the prediction timestamp to avoid leakage. |
| `data_quality_status` | string | Yes | No | `PASS` | Approved values include `PASS`, `WARN`, and `FAIL`. |

## Prediction Output Table

Predictions must be stored for replay, audit, monitoring, calibration review, user feedback, and model-risk evidence.

| Field | Type | Required | Nullable | Example | Validation / Notes |
|---|---|---:|---:|---|---|
| `prediction_id` | string | Yes | No | `PRED456` | Unique prediction identifier. |
| `loan_id` | string | Yes | No | `LN123` | Must refer to the scored active loan. |
| `as_of_timestamp` | timestamp | Yes | No | `2026-07-10T13:00:00Z` | Prediction timestamp. |
| `model_version` | string | Yes | No | `recall_model_1.0.0` | Registered model artifact version. |
| `feature_set_version` | string | Yes | No | `feature_set_1.0.0` | Versioned feature set used for scoring. |
| `probability_1d` | decimal | Yes | No | `0.12` | Must be in `[0, 1]`. |
| `probability_3d` | decimal | Yes | No | `0.27` | Must be in `[0, 1]`. |
| `probability_5d` | decimal | Yes | No | `0.41` | Must be in `[0, 1]`. |
| `probability_10d` | decimal | Yes | No | `0.63` | Must be in `[0, 1]`. |
| `risk_band` | string | Yes | No | `HIGH` | Approved values are `LOW`, `MODERATE`, `HIGH`, and `CRITICAL`. |
| `reason_code_1` | string | Yes | No | `LENDER_RECENT_RECALL_ACTIVITY` | Primary reason code; must be approved and explainable. |
| `reason_code_2` | string | Yes | No | `UPCOMING_PROXY_EVENT` | Secondary reason code. |
| `reason_code_3` | string | Yes | No | `HIGH_FUND_TURNOVER` | Tertiary reason code. |
| `data_quality_status` | string | Yes | No | `PASS` | Alerts should be suppressed or flagged when status is not `PASS`. |
| `created_timestamp` | timestamp | Yes | No | `2026-07-10T13:01:00Z` | Time prediction was written. |

## API Request Fields

The prediction API must reject malformed requests before scoring.

| Field | Type | Required | Nullable | Example | Validation / Notes |
|---|---|---:|---:|---|---|
| `loan_ids` | array[string] | Yes | No | `["LN123", "LN456"]` | Must contain at least one loan identifier. |
| `as_of_timestamp` | timestamp | Yes | No | `2026-07-10T13:00:00Z` | Must be timezone-aware and not after available feature timestamps. |
| `horizons` | array[integer] | Yes | No | `[1, 3, 5, 10]` | Allowed values are `1`, `3`, `5`, and `10` business days. |

## Minimum MVP Data Contract

The MVP cannot enter production until these required tables are contractually available and quality-gated.

| Data Contract | Grain | Required Keys | Required Timestamps | Quality Gate |
|---|---|---|---|---|
| Loan snapshot | Loan-as-of time | `loan_id`, `security_id`, `lender_id`, `borrower_id` | `as_of_timestamp`, `open_date` | Active-loan count, positive quantity, valid status. |
| Recall events | Event | `event_id`, `loan_id` | `event_timestamp` | Deduplicate events, exclude cancelled and borrower-initiated returns. |
| Security market data | Security-as-of time | `security_id` | `source_timestamp`, `availability_timestamp` | Freshness, range, missingness, corporate-action joins. |
| Lender history | Lender-as-of time | `lender_id` | `effective_timestamp`, `availability_timestamp` | No future aggregation leakage. |
| Feature store | Entity-feature-as-of time | `entity_id`, `entity_type`, `feature_name`, `feature_version` | `availability_timestamp` | Point-in-time correctness and schema validation. |
| Prediction store | Prediction event | `prediction_id`, `loan_id` | `as_of_timestamp`, `created_timestamp` | Probability range, required reason codes, model version present. |
