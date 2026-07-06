from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from document_refinery.application.pipeline import RefineryPipeline
from document_refinery.infrastructure.tasks import TaskStatus

pytest.importorskip("pypdf")


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads(
    (ROOT / "example_schedules" / "manifest.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("document", MANIFEST["documents"], ids=lambda item: item["profile"])
def test_public_schedule_hash_matches_manifest(document: dict[str, object]) -> None:
    path = ROOT / "example_schedules" / str(document["path"])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == document["sha256"]


@pytest.mark.parametrize("document", MANIFEST["documents"], ids=lambda item: item["profile"])
def test_public_schedule_reaches_gate_a_with_confirmed_lineage(
    tmp_path: Path,
    document: dict[str, object],
) -> None:
    pipeline = RefineryPipeline(tmp_path / str(document["profile"]))
    try:
        result = pipeline.run(
            ROOT / "example_schedules" / str(document["path"]),
            source="public-example",
        )
        record_count = len(result.silver_rows) // 14
        assert record_count >= int(document["expected_minimum_eligibility_records"])
        assert not [row for row in result.silver_rows if row.validator_status == "disputed"]
        assert not [
            row
            for row in result.silver_rows
            if row.normalized_value != "not_found"
            and "unresolved" in row.source_locator
        ]
        assert result.review_html.exists()
        assert pipeline.tasks.get(result.document.doc_id).status is TaskStatus.GATE_A_PENDING
    finally:
        pipeline.close()
