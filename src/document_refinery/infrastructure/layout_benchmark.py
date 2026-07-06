"""Reproducible N2 OCR/layout benchmark runner."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from document_refinery.infrastructure.artifacts import ArtifactStore
from document_refinery.infrastructure.layout import LayoutAdapter, read_layout_artifact


@dataclass(frozen=True, slots=True)
class LayoutBenchmarkCase:
    name: str
    path: Path
    minimum_text_characters: int = 1
    minimum_table_cells: int = 0
    expected_locator_count: int | None = None


@dataclass(frozen=True, slots=True)
class LayoutBenchmarkResult:
    name: str
    adapter: str
    adapter_version: str
    status: str
    text_characters: int
    table_cell_count: int
    mean_confidence: float
    reading_order_locators: int
    locator_reproducibility: float
    latency_ms: int
    estimated_cost_usd: float
    artifact_sha256: str
    issues: tuple[str, ...]


def run_layout_benchmark(
    *,
    workspace: Path,
    cases: tuple[LayoutBenchmarkCase, ...],
    layout_adapter: LayoutAdapter,
) -> tuple[LayoutBenchmarkResult, ...]:
    """Run benchmark documents through bronze text/layout extraction.

    Results are written to ``workspace / "layout_benchmark_results.json"`` so the
    three-document N2 benchmark can be published without changing artifact bytes.
    """

    primary_store = ArtifactStore(
        workspace / "artifacts" / "primary", layout_adapter=layout_adapter
    )
    replay_store = ArtifactStore(
        workspace / "artifacts" / "replay", layout_adapter=layout_adapter
    )
    results: list[LayoutBenchmarkResult] = []
    for case in cases:
        started = time.perf_counter()
        document = primary_store.ingest(case.path, source=f"layout-benchmark:{case.name}")
        _document, text_artifact = primary_store.extract_text(document)
        latency_ms = int((time.perf_counter() - started) * 1000)
        artifact_path = Path(text_artifact.layout_uri)
        artifact = read_layout_artifact(artifact_path)

        replay_document = replay_store.ingest(
            case.path, source=f"layout-benchmark-replay:{case.name}"
        )
        _replay_document, replay_text_artifact = replay_store.extract_text(replay_document)
        replay_artifact = read_layout_artifact(Path(replay_text_artifact.layout_uri))

        locators = tuple(locator for page in artifact.pages for locator in page.reading_order)
        replay_locators = tuple(
            locator for page in replay_artifact.pages for locator in page.reading_order
        )
        locator_reproducibility = 1.0 if locators == replay_locators else 0.0
        issues = list(artifact.quality.issues)
        if artifact.quality.text_characters < case.minimum_text_characters:
            issues.append("below_minimum_text_fidelity")
        if artifact.quality.table_cell_count < case.minimum_table_cells:
            issues.append("below_minimum_table_cells")
        if case.expected_locator_count is not None and len(locators) != case.expected_locator_count:
            issues.append("unexpected_locator_count")
        if locator_reproducibility < 1.0:
            issues.append("non_reproducible_locators")
        status = "passed" if artifact.quality.status == "passed" and not issues else "failed"
        results.append(
            LayoutBenchmarkResult(
                name=case.name,
                adapter=artifact.adapter,
                adapter_version=artifact.adapter_version,
                status=status,
                text_characters=artifact.quality.text_characters,
                table_cell_count=artifact.quality.table_cell_count,
                mean_confidence=artifact.quality.mean_confidence,
                reading_order_locators=len(locators),
                locator_reproducibility=locator_reproducibility,
                latency_ms=latency_ms,
                estimated_cost_usd=0.0,
                artifact_sha256=_sha256(artifact_path),
                issues=tuple(issues),
            )
        )
    output = workspace / "layout_benchmark_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(result) for result in results], indent=2) + "\n")
    return tuple(results)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
