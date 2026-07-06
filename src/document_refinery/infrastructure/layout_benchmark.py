"""Reproducible N2 OCR/layout benchmark runner."""

from __future__ import annotations

import json
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

    store = ArtifactStore(workspace / "artifacts", layout_adapter=layout_adapter)
    results: list[LayoutBenchmarkResult] = []
    for case in cases:
        document = store.ingest(case.path, source=f"layout-benchmark:{case.name}")
        _document, text_artifact = store.extract_text(document)
        artifact = read_layout_artifact(Path(text_artifact.layout_uri))
        issues = list(artifact.quality.issues)
        if artifact.quality.text_characters < case.minimum_text_characters:
            issues.append("below_minimum_text_fidelity")
        if artifact.quality.table_cell_count < case.minimum_table_cells:
            issues.append("below_minimum_table_cells")
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
                reading_order_locators=sum(len(page.reading_order) for page in artifact.pages),
                issues=tuple(issues),
            )
        )
    output = workspace / "layout_benchmark_results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps([asdict(result) for result in results], indent=2) + "\n")
    return tuple(results)
