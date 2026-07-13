from datetime import UTC, date, datetime

import pytest
from loan_recall_prediction.api.schemas import PredictionRequest
from loan_recall_prediction.labels.horizons import add_business_days, recall_within_horizon
from loan_recall_prediction.scoring.prediction import build_prediction
from loan_recall_prediction.scoring.risk_bands import assign_risk_band


def test_add_business_days_skips_weekends() -> None:
    assert add_business_days(date(2026, 7, 10), 1) == date(2026, 7, 13)


def test_recall_within_horizon_labels_future_recall() -> None:
    assert recall_within_horizon(date(2026, 7, 10), date(2026, 7, 13), 1) == 1
    assert recall_within_horizon(date(2026, 7, 10), date(2026, 7, 14), 1) == 0


@pytest.mark.parametrize(
    ("probability", "expected"),
    [(0.01, "LOW"), (0.10, "MODERATE"), (0.25, "HIGH"), (0.50, "CRITICAL")],
)
def test_assign_risk_band(probability: float, expected: str) -> None:
    assert assign_risk_band(probability) == expected


def test_build_prediction_pads_reason_codes_and_uses_max_risk() -> None:
    prediction = build_prediction(
        loan_id="LN123",
        as_of_timestamp=datetime(2026, 7, 10, 13, tzinfo=UTC),
        horizon_probabilities={1: 0.12, 3: 0.27, 5: 0.41, 10: 0.63},
        reason_codes=["LENDER_RECENT_RECALL_ACTIVITY"],
    )

    assert prediction.risk_band == "CRITICAL"
    assert prediction.reason_codes[0] == "LENDER_RECENT_RECALL_ACTIVITY"
    assert len(prediction.reason_codes) == 3
    assert prediction.to_dict()["probabilities"] == {
        "1d": 0.12,
        "3d": 0.27,
        "5d": 0.41,
        "10d": 0.63,
    }


def test_prediction_request_rejects_empty_loans() -> None:
    with pytest.raises(ValueError, match="loan_ids"):
        PredictionRequest(loan_ids=(), as_of_timestamp=datetime.now(UTC))
