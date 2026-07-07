"""Local infrastructure adapters for Phase 0/1."""

from .artifacts import ArtifactStore, BronzeDocument, TextArtifact
from .layout import (
    OcrLayoutAdapter,
    PdfPlumberLayoutAdapter,
    TesseractOcrEngine,
    TextLineLayoutAdapter,
)
from .layout_benchmark import LayoutBenchmarkCase, LayoutBenchmarkResult, run_layout_benchmark
from .model_calls import SemanticCallStore
from .records import GoldLimitStore, GoldMarginRequirementStore, GoldStore, SilverStore
from .review_timing import ReviewTiming, ReviewTimingLog, summarize_timings
from .tasks import TaskRecord, TaskStatus, TaskStore
from .watcher import LandingCandidate, LandingZoneWatcher

__all__ = [
    "ArtifactStore",
    "BronzeDocument",
    "GoldLimitStore",
    "GoldMarginRequirementStore",
    "GoldStore",
    "LandingCandidate",
    "LandingZoneWatcher",
    "LayoutBenchmarkCase",
    "LayoutBenchmarkResult",
    "OcrLayoutAdapter",
    "PdfPlumberLayoutAdapter",
    "ReviewTiming",
    "ReviewTimingLog",
    "TesseractOcrEngine",
    "SilverStore",
    "SemanticCallStore",
    "summarize_timings",
    "TaskRecord",
    "TaskStatus",
    "TaskStore",
    "TextLineLayoutAdapter",
    "TextArtifact",
    "run_layout_benchmark",
]
