"""Durable per-document review-time log — the missing N4 exit metric.

The N4 exit criteria include an owner review time of **≤15 minutes per document**
(handoff §1 Phase-1 exit, §11, §12-N4.3), which the project notes is "not yet
measured". This log captures how long each Gate A review actually took so the
metric becomes real evidence rather than an aspiration. One append-only JSONL
line per completed review pass; the same document reviewed twice records twice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

TARGET_REVIEW_MINUTES = 15.0


@dataclass(frozen=True, slots=True)
class ReviewTiming:
    doc_id: str
    reviewer: str
    seconds: float
    action_count: int
    decided_at: datetime

    def __post_init__(self) -> None:
        if self.seconds < 0:
            raise ValueError("review seconds must be non-negative")

    @property
    def minutes(self) -> float:
        return self.seconds / 60.0

    def to_json(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "reviewer": self.reviewer,
            "seconds": self.seconds,
            "action_count": self.action_count,
            "decided_at": self.decided_at.isoformat(),
        }

    @classmethod
    def from_json(cls, payload: dict[str, object]) -> ReviewTiming:
        return cls(
            doc_id=str(payload["doc_id"]),
            reviewer=str(payload["reviewer"]),
            seconds=float(str(payload["seconds"])),
            action_count=int(str(payload["action_count"])),
            decided_at=datetime.fromisoformat(str(payload["decided_at"])),
        )


@dataclass(frozen=True, slots=True)
class ReviewTimingSummary:
    count: int
    median_minutes: float
    mean_minutes: float
    max_minutes: float
    within_target_count: int
    target_minutes: float

    @property
    def meets_target(self) -> bool:
        # The exit metric is a per-document ceiling: every measured review ≤ target.
        return self.count > 0 and self.within_target_count == self.count

    def to_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "median_minutes": round(self.median_minutes, 2),
            "mean_minutes": round(self.mean_minutes, 2),
            "max_minutes": round(self.max_minutes, 2),
            "within_target_count": self.within_target_count,
            "target_minutes": self.target_minutes,
            "meets_target": self.meets_target,
        }


def summarize_timings(
    timings: tuple[ReviewTiming, ...], *, target_minutes: float = TARGET_REVIEW_MINUTES
) -> ReviewTimingSummary:
    if not timings:
        return ReviewTimingSummary(0, 0.0, 0.0, 0.0, 0, target_minutes)
    minutes = [timing.minutes for timing in timings]
    within = sum(1 for value in minutes if value <= target_minutes)
    return ReviewTimingSummary(
        count=len(minutes),
        median_minutes=median(minutes),
        mean_minutes=sum(minutes) / len(minutes),
        max_minutes=max(minutes),
        within_target_count=within,
        target_minutes=target_minutes,
    )


class ReviewTimingLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, timing: ReviewTiming) -> Path:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(timing.to_json(), sort_keys=True) + "\n")
        return self.path

    def read_all(self) -> tuple[ReviewTiming, ...]:
        if not self.path.exists():
            return ()
        return tuple(
            ReviewTiming.from_json(json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
