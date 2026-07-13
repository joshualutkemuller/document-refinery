"""Lightweight API schemas for loan recall prediction requests and responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from loan_recall_prediction.common.config import HORIZONS_BUSINESS_DAYS


@dataclass(frozen=True)
class PredictionRequest:
    """Validated API request for loan recall prediction."""

    loan_ids: tuple[str, ...]
    as_of_timestamp: datetime
    horizons: tuple[int, ...] = HORIZONS_BUSINESS_DAYS

    def __post_init__(self) -> None:
        if not self.loan_ids:
            raise ValueError("loan_ids must not be empty")
        unsupported = set(self.horizons).difference(HORIZONS_BUSINESS_DAYS)
        if unsupported:
            raise ValueError(f"unsupported horizons: {sorted(unsupported)}")
