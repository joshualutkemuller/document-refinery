"""Risk band assignment for calibrated recall probabilities."""

from __future__ import annotations

from loan_recall_prediction.common.config import RISK_BAND_THRESHOLDS


def assign_risk_band(probability: float) -> str:
    """Convert a probability in [0, 1] to the approved operational risk band."""
    if probability < 0 or probability > 1:
        msg = f"probability must be between 0 and 1, got {probability}"
        raise ValueError(msg)
    if probability < RISK_BAND_THRESHOLDS["LOW_MAX"]:
        return "LOW"
    if probability < RISK_BAND_THRESHOLDS["MODERATE_MAX"]:
        return "MODERATE"
    if probability < RISK_BAND_THRESHOLDS["HIGH_MAX"]:
        return "HIGH"
    return "CRITICAL"
