"""Point-in-time label helpers for lender-initiated recall events."""

from __future__ import annotations

from datetime import date, timedelta


def add_business_days(start_date: date, business_days: int) -> date:
    """Return the date after adding business days, excluding Saturday and Sunday."""
    if business_days < 0:
        msg = "business_days must be non-negative"
        raise ValueError(msg)

    current_date = start_date
    days_added = 0
    while days_added < business_days:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5:
            days_added += 1
    return current_date


def recall_within_horizon(
    prediction_date: date,
    recall_date: date | None,
    horizon_business_days: int,
) -> int:
    """Return 1 when a valid recall occurs after prediction date and within horizon."""
    if recall_date is None or recall_date <= prediction_date:
        return 0
    horizon_end = add_business_days(prediction_date, horizon_business_days)
    return int(recall_date <= horizon_end)
