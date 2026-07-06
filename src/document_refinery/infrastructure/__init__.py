"""Local infrastructure adapters for Phase 0/1."""

from .artifacts import ArtifactStore, BronzeDocument, TextArtifact
from .model_calls import SemanticCallStore
from .records import GoldStore, SilverStore
from .tasks import TaskRecord, TaskStatus, TaskStore
from .watcher import LandingCandidate, LandingZoneWatcher

__all__ = [
    "ArtifactStore",
    "BronzeDocument",
    "GoldStore",
    "LandingCandidate",
    "LandingZoneWatcher",
    "SilverStore",
    "SemanticCallStore",
    "TaskRecord",
    "TaskStatus",
    "TaskStore",
    "TextArtifact",
]
