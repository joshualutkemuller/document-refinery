"""Provider-neutral OCR/layout coordinate artifacts for bronze storage."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError("invalid bounding box coordinates")


@dataclass(frozen=True, slots=True)
class LayoutToken:
    text: str
    bbox: BoundingBox
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("layout confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class LayoutLine:
    line: int
    text: str
    locator: str
    bbox: BoundingBox | None
    tokens: tuple[LayoutToken, ...]
    confidence: float


@dataclass(frozen=True, slots=True)
class TableCell:
    table_id: str
    row: int
    column: int
    row_span: int
    column_span: int
    text: str
    locator: str
    bbox: BoundingBox | None
    confidence: float

    def __post_init__(self) -> None:
        if self.row_span < 1 or self.column_span < 1:
            raise ValueError("table spans must be positive")


@dataclass(frozen=True, slots=True)
class LayoutPage:
    page: int
    width: float | None
    height: float | None
    lines: tuple[LayoutLine, ...]
    table_cells: tuple[TableCell, ...]
    reading_order: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LayoutArtifact:
    doc_id: str
    adapter: str
    adapter_version: str
    pages: tuple[LayoutPage, ...]


class LayoutAdapter(Protocol):
    @property
    def adapter_name(self) -> str: ...

    @property
    def adapter_version(self) -> str: ...

    def analyze(self, *, doc_id: str, path: Path, pages: tuple[str, ...]) -> LayoutArtifact: ...


class TextLineLayoutAdapter:
    """Deterministic fallback coordinate layer for text-bearing artifacts."""

    adapter_name = "text-line-layout"
    adapter_version = "1.0.0"

    def analyze(self, *, doc_id: str, path: Path, pages: tuple[str, ...]) -> LayoutArtifact:
        del path
        layout_pages: list[LayoutPage] = []
        for page_number, page_text in enumerate(pages, start=1):
            lines: list[LayoutLine] = []
            reading_order: list[str] = []
            for line_number, line in enumerate(page_text.splitlines(), start=1):
                locator = f"page={page_number};line={line_number}"
                bbox = BoundingBox(
                    0.0,
                    float(line_number - 1),
                    float(len(line)),
                    float(line_number),
                )
                lines.append(
                    LayoutLine(
                        line=line_number,
                        text=line,
                        locator=locator,
                        bbox=bbox,
                        tokens=(LayoutToken(line, bbox, 1.0),) if line else (),
                        confidence=1.0,
                    )
                )
                reading_order.append(locator)
            layout_pages.append(
                LayoutPage(
                    page=page_number,
                    width=None,
                    height=None,
                    lines=tuple(lines),
                    table_cells=(),
                    reading_order=tuple(reading_order),
                )
            )
        return LayoutArtifact(doc_id, self.adapter_name, self.adapter_version, tuple(layout_pages))


def write_layout_artifact(path: Path, artifact: LayoutArtifact) -> None:
    payload = asdict(artifact)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != serialized:
        raise RuntimeError(f"immutable layout artifact collision at {path}")
    path.write_text(serialized, encoding="utf-8")
