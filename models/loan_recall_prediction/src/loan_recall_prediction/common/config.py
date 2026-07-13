"""Configuration constants for the loan recall prediction model."""

from __future__ import annotations

HORIZONS_BUSINESS_DAYS: tuple[int, ...] = (1, 3, 5, 10)
RISK_BAND_THRESHOLDS: dict[str, float] = {
    "LOW_MAX": 0.10,
    "MODERATE_MAX": 0.25,
    "HIGH_MAX": 0.50,
}
DEFAULT_MODEL_VERSION = "recall_model_0.1.0"
DEFAULT_FEATURE_SET_VERSION = "feature_set_0.1.0"
DEFAULT_REASON_CODE = "NO_DOMINANT_DRIVER_IDENTIFIED"
DEFAULT_DATA_QUALITY_STATUS = "PASS"
