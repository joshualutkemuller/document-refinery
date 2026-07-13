"""Prediction response builders for loan recall scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from loan_recall_prediction.common.config import (
    DEFAULT_DATA_QUALITY_STATUS,
    DEFAULT_FEATURE_SET_VERSION,
    DEFAULT_MODEL_VERSION,
    DEFAULT_REASON_CODE,
    HORIZONS_BUSINESS_DAYS,
)
from loan_recall_prediction.scoring.risk_bands import assign_risk_band


@dataclass(frozen=True)
class RecallPrediction:
    """Serializable loan-level recall prediction."""

    loan_id: str
    as_of_timestamp: datetime
    probabilities: dict[str, float]
    risk_band: str
    reason_codes: tuple[str, str, str]
    data_quality_status: str = DEFAULT_DATA_QUALITY_STATUS
    model_version: str = DEFAULT_MODEL_VERSION
    feature_set_version: str = DEFAULT_FEATURE_SET_VERSION
    created_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible prediction payload."""
        return {
            "loan_id": self.loan_id,
            "as_of_timestamp": self.as_of_timestamp.isoformat(),
            "model_version": self.model_version,
            "feature_set_version": self.feature_set_version,
            "probabilities": self.probabilities,
            "risk_band": self.risk_band,
            "reason_codes": list(self.reason_codes),
            "data_quality_status": self.data_quality_status,
            "created_timestamp": self.created_timestamp.isoformat(),
        }


def build_prediction(
    loan_id: str,
    as_of_timestamp: datetime,
    horizon_probabilities: dict[int, float],
    reason_codes: list[str] | tuple[str, ...] | None = None,
    data_quality_status: str = DEFAULT_DATA_QUALITY_STATUS,
) -> RecallPrediction:
    """Build a validated prediction payload from raw horizon probabilities."""
    missing_horizons = set(HORIZONS_BUSINESS_DAYS).difference(horizon_probabilities)
    if missing_horizons:
        msg = f"missing probabilities for horizons: {sorted(missing_horizons)}"
        raise ValueError(msg)

    probabilities = {
        f"{horizon}d": horizon_probabilities[horizon]
        for horizon in HORIZONS_BUSINESS_DAYS
    }
    for probability in probabilities.values():
        if probability < 0 or probability > 1:
            msg = f"probability must be between 0 and 1, got {probability}"
            raise ValueError(msg)

    supplied_reason_codes = list(reason_codes or [])[:3]
    padded_reason_codes = supplied_reason_codes + [DEFAULT_REASON_CODE] * (
        3 - len(supplied_reason_codes)
    )

    return RecallPrediction(
        loan_id=loan_id,
        as_of_timestamp=as_of_timestamp,
        probabilities=probabilities,
        risk_band=assign_risk_band(max(probabilities.values())),
        reason_codes=(padded_reason_codes[0], padded_reason_codes[1], padded_reason_codes[2]),
        data_quality_status=data_quality_status,
    )
