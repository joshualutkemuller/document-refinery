"""Provider-neutral OCR/layout coordinate artifacts for bronze storage."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast


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

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("layout confidence must be between 0 and 1")


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
    merged_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.row_span < 1 or self.column_span < 1:
            raise ValueError("table spans must be positive")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("layout confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class LayoutQualityReport:
    status: str
    mean_confidence: float
    text_characters: int
    table_cell_count: int
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.status not in {"passed", "failed"}:
            raise ValueError("layout quality status must be passed or failed")
        if not 0.0 <= self.mean_confidence <= 1.0:
            raise ValueError("layout confidence must be between 0 and 1")


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
    quality: LayoutQualityReport


class LayoutAdapter(Protocol):
    @property
    def adapter_name(self) -> str: ...

    @property
    def adapter_version(self) -> str: ...

    def analyze(self, *, doc_id: str, path: Path, pages: tuple[str, ...]) -> LayoutArtifact: ...


class TextLineLayoutAdapter:
    """Deterministic fallback coordinate layer for text-bearing artifacts."""

    adapter_name = "text-line-layout"
    adapter_version = "1.1.0"

    def analyze(self, *, doc_id: str, path: Path, pages: tuple[str, ...]) -> LayoutArtifact:
        del path
        layout_pages: list[LayoutPage] = []
        for page_number, page_text in enumerate(pages, start=1):
            lines: list[LayoutLine] = []
            reading_order: list[str] = []
            for line_number, line in enumerate(page_text.splitlines(), start=1):
                locator = f"page={page_number};line={line_number}"
                bbox = BoundingBox(
                    0.0, float(line_number - 1), float(len(line)), float(line_number)
                )
                lines.append(
                    LayoutLine(
                        line_number,
                        line,
                        locator,
                        bbox,
                        (LayoutToken(line, bbox, 1.0),) if line else (),
                        1.0,
                    )
                )
                reading_order.append(locator)
            layout_pages.append(
                LayoutPage(page_number, None, None, tuple(lines), (), tuple(reading_order))
            )
        return LayoutArtifact(
            doc_id,
            self.adapter_name,
            self.adapter_version,
            tuple(layout_pages),
            _quality(tuple(layout_pages)),
        )


class PdfPlumberLayoutAdapter:
    """Production PDF layout adapter selected for N2 benchmarking.

    It preserves page geometry, word coordinates, deterministic reading order and
    table-cell coordinates. Scanned/image-only PDFs fail quality until an OCR
    engine supplies text and confidence-bearing coordinates.
    """

    adapter_name = "pdfplumber-layout"
    adapter_version = "1.0.0"

    def analyze(self, *, doc_id: str, path: Path, pages: tuple[str, ...]) -> LayoutArtifact:
        if path.suffix.casefold() != ".pdf":
            return TextLineLayoutAdapter().analyze(doc_id=doc_id, path=path, pages=pages)
        try:
            import pdfplumber  # type: ignore[import-not-found]
        except ImportError as error:
            raise RuntimeError(
                "PdfPlumber layout extraction requires the 'pdf' project extra"
            ) from error
        layout_pages: list[LayoutPage] = []
        with pdfplumber.open(path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
                lines_by_top: dict[float, list[dict[str, Any]]] = {}
                for word in words:
                    lines_by_top.setdefault(round(float(word["top"]), 1), []).append(word)
                lines: list[LayoutLine] = []
                reading_order: list[str] = []
                for line_number, (_top, line_words) in enumerate(
                    sorted(lines_by_top.items()), start=1
                ):
                    ordered = sorted(line_words, key=lambda word: float(word["x0"]))
                    text = " ".join(str(word["text"]) for word in ordered)
                    bbox = BoundingBox(
                        min(float(w["x0"]) for w in ordered),
                        min(float(w["top"]) for w in ordered),
                        max(float(w["x1"]) for w in ordered),
                        max(float(w["bottom"]) for w in ordered),
                    )
                    tokens = tuple(
                        LayoutToken(
                            str(w["text"]),
                            BoundingBox(
                                float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"])
                            ),
                            1.0,
                        )
                        for w in ordered
                    )
                    locator = f"page={page_number};line={line_number}"
                    lines.append(LayoutLine(line_number, text, locator, bbox, tokens, 1.0))
                    reading_order.append(locator)
                cells: list[TableCell] = []
                for table_index, table in enumerate(page.find_tables(), start=1):
                    table_id = f"page={page_number};table={table_index}"
                    for row_index, row in enumerate(table.rows, start=1):
                        for column_index, cell_bbox in enumerate(row.cells, start=1):
                            if cell_bbox is None:
                                continue
                            bbox = BoundingBox(
                                float(cell_bbox[0]),
                                float(cell_bbox[1]),
                                float(cell_bbox[2]),
                                float(cell_bbox[3]),
                            )
                            text = (page.crop(cell_bbox).extract_text() or "").strip()
                            locator = f"{table_id};row={row_index};col={column_index}"
                            cells.append(
                                TableCell(
                                    table_id,
                                    row_index,
                                    column_index,
                                    1,
                                    1,
                                    text,
                                    locator,
                                    bbox,
                                    1.0,
                                )
                            )
                            reading_order.append(locator)
                layout_pages.append(
                    LayoutPage(
                        page_number,
                        float(page.width),
                        float(page.height),
                        tuple(lines),
                        tuple(cells),
                        tuple(reading_order),
                    )
                )
        return LayoutArtifact(
            doc_id,
            self.adapter_name,
            self.adapter_version,
            tuple(layout_pages),
            _quality(tuple(layout_pages)),
        )


def _quality(pages: tuple[LayoutPage, ...]) -> LayoutQualityReport:
    confidences = [line.confidence for page in pages for line in page.lines] + [
        cell.confidence for page in pages for cell in page.table_cells
    ]
    chars = sum(len(line.text) for page in pages for line in page.lines)
    cell_count = sum(len(page.table_cells) for page in pages)
    issues: list[str] = []
    if chars == 0:
        issues.append("no_text_coordinates")
    if not all(page.reading_order for page in pages):
        issues.append("missing_reading_order")
    mean = sum(confidences) / len(confidences) if confidences else 0.0
    if mean < 0.95:
        issues.append("low_layout_confidence")
    return LayoutQualityReport(
        "failed" if issues else "passed", mean, chars, cell_count, tuple(issues)
    )


def assert_layout_passed(artifact: LayoutArtifact) -> None:
    if artifact.quality.status != "passed":
        raise ValueError(
            "layout artifact failed structural quality gates: " + ", ".join(artifact.quality.issues)
        )


def read_layout_artifact(path: Path) -> LayoutArtifact:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    pages = tuple(_page_from_json(page) for page in payload["pages"])
    quality_payload = cast(dict[str, Any], payload.get("quality"))
    quality = (
        LayoutQualityReport(**quality_payload) if quality_payload is not None else _quality(pages)
    )
    return LayoutArtifact(
        str(payload["doc_id"]),
        str(payload["adapter"]),
        str(payload["adapter_version"]),
        pages,
        quality,
    )


def _page_from_json(payload: dict[str, Any]) -> LayoutPage:
    return LayoutPage(
        page=int(payload["page"]),
        width=_optional_float(payload.get("width")),
        height=_optional_float(payload.get("height")),
        lines=tuple(_line_from_json(line) for line in payload["lines"]),
        table_cells=tuple(_cell_from_json(cell) for cell in payload["table_cells"]),
        reading_order=tuple(payload["reading_order"]),
    )


def _line_from_json(payload: dict[str, Any]) -> LayoutLine:
    bbox = _bbox(payload.get("bbox"))
    token_payloads = cast(tuple[dict[str, Any], ...], tuple(payload["tokens"]))
    tokens = tuple(
        LayoutToken(str(token["text"]), _required_bbox(token["bbox"]), float(token["confidence"]))
        for token in token_payloads
    )
    return LayoutLine(
        int(payload["line"]),
        str(payload["text"]),
        str(payload["locator"]),
        bbox,
        tokens,
        float(payload["confidence"]),
    )


def _cell_from_json(payload: dict[str, Any]) -> TableCell:
    return TableCell(
        str(payload["table_id"]),
        int(payload["row"]),
        int(payload["column"]),
        int(payload["row_span"]),
        int(payload["column_span"]),
        str(payload["text"]),
        str(payload["locator"]),
        _bbox(payload.get("bbox")),
        float(payload["confidence"]),
        tuple(payload.get("merged_from", ())),
    )


def _bbox(payload: object) -> BoundingBox | None:
    if payload is None:
        return None
    payload = cast(dict[str, Any], payload)
    return BoundingBox(
        float(payload["x0"]), float(payload["y0"]), float(payload["x1"]), float(payload["y1"])
    )


def _optional_float(value: object) -> float | None:
    return None if value is None else float(cast(Any, value))


def _required_bbox(payload: object) -> BoundingBox:
    bbox = _bbox(payload)
    if bbox is None:
        raise ValueError("token bounding boxes are required")
    return bbox


def write_layout_artifact(path: Path, artifact: LayoutArtifact) -> None:
    payload = asdict(artifact)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != serialized:
        raise RuntimeError(f"immutable layout artifact collision at {path}")
    path.write_text(serialized, encoding="utf-8")
