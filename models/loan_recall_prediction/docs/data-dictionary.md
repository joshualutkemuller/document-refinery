# Data Dictionary

## Prediction Fields

| Field | Description |
|---|---|
| `prediction_id` | Unique prediction event identifier. |
| `loan_id` | Active loan identifier. |
| `as_of_timestamp` | Point-in-time scoring timestamp. |
| `model_version` | Registered model artifact version. |
| `feature_set_version` | Versioned feature definition set. |
| `probability_1d` | Probability of valid recall within 1 business day. |
| `probability_3d` | Probability of valid recall within 3 business days. |
| `probability_5d` | Probability of valid recall within 5 business days. |
| `probability_10d` | Probability of valid recall within 10 business days. |
| `risk_band` | Operational risk category. |
| `reason_code_1` | Primary local explanation. |
| `reason_code_2` | Secondary local explanation. |
| `reason_code_3` | Tertiary local explanation. |
| `data_quality_status` | Data quality gate result. |

## Primary Label

`label_recall_h = 1` when a valid lender-initiated recall occurs after the prediction timestamp and on or before the approved horizon end; otherwise `0`.
