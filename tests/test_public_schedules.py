from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from document_refinery import cli
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


_DETERMINISTIC = [
    doc for doc in MANIFEST["documents"]
    if doc.get("expected_route", "deterministic") == "deterministic"
]
_CLASSIFICATION_REVIEW = [
    doc for doc in MANIFEST["documents"]
    if doc.get("expected_route") == "classification_review"
]


@pytest.mark.parametrize("document", _DETERMINISTIC, ids=lambda item: item["profile"])
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


@pytest.mark.parametrize(
    "document", _CLASSIFICATION_REVIEW, ids=lambda item: str(item["path"])
)
def test_unknown_layout_routes_to_classification_review(
    tmp_path: Path,
    document: dict[str, object],
) -> None:
    # Without a configured semantic extractor, an unknown layout must stop for
    # owner review rather than being force-parsed by a mismatched profile.
    pipeline = RefineryPipeline(tmp_path / "unknown")
    try:
        with pytest.raises(ValueError, match="classification requires owner review"):
            pipeline.run(
                ROOT / "example_schedules" / str(document["path"]),
                source="public-example",
            )
    finally:
        pipeline.close()


def test_watch_corpus_is_resilient_to_unknown_layouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A batch watch over a mixed corpus must report unknown layouts and keep
    # going, not abort on the first document that needs classification review.
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "document-refinery",
            "watch",
            str(ROOT / "example_schedules"),
            "--workspace",
            str(tmp_path / "w"),
            "--source",
            "public-example",
        ],
    )
    exit_code = cli.main()
    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.count('"task_status": "gate_a_pending"') == len(_DETERMINISTIC)
    assert '"task_status": "classification_review_required"' in out
