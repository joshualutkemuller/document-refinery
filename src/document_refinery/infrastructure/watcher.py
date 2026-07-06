"""Polling-friendly landing-zone discovery with stable file ordering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LandingCandidate:
    path: Path
    source: str


class LandingZoneWatcher:
    SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
    IGNORED_NAMES = {"README.md"}

    def __init__(self, landing_zone: Path, *, source: str) -> None:
        self.landing_zone = landing_zone
        self.source = source

    def discover(self) -> tuple[LandingCandidate, ...]:
        if not self.landing_zone.exists():
            return ()
        return tuple(
            LandingCandidate(path=path, source=self.source)
            for path in sorted(self.landing_zone.iterdir())
            if path.is_file()
            and path.suffix.casefold() in self.SUPPORTED_SUFFIXES
            and not path.name.startswith(".")
            and path.name not in self.IGNORED_NAMES
        )
