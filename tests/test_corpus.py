from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from document_refinery.golden import corpus


def test_sha256_of_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "doc.txt"
    path.write_bytes(b"collateral schedule bytes")
    assert corpus.sha256_of(path) == hashlib.sha256(b"collateral schedule bytes").hexdigest()


def test_build_entry_deterministic_requires_records() -> None:
    with pytest.raises(ValueError, match="positive expected record count"):
        corpus.build_entry(
            path="d.pdf",
            title="t",
            source_url="https://x",
            sha256="abc",
            profile="cme",
            expected_route="deterministic",
            expected_minimum_eligibility_records=0,
        )


def test_build_entry_classification_review_omits_record_count() -> None:
    entry = corpus.build_entry(
        path="d.txt",
        title="t",
        source_url="synthetic://x",
        sha256="abc",
        profile="unknown",
        expected_route="classification_review",
        synthetic=True,
        note="fixture",
    )
    assert "expected_minimum_eligibility_records" not in entry
    assert entry["expected_route"] == "classification_review"
    assert entry["synthetic"] is True
    assert entry["note"] == "fixture"


def test_upsert_entry_replaces_by_path() -> None:
    docs = [{"path": "a.pdf", "title": "old"}, {"path": "b.pdf", "title": "keep"}]
    updated = corpus.upsert_entry(docs, {"path": "a.pdf", "title": "new"})
    by_path = {doc["path"]: doc for doc in updated}
    assert len(updated) == 2
    assert by_path["a.pdf"]["title"] == "new"
    assert by_path["b.pdf"]["title"] == "keep"


def test_manifest_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    manifest = {"retrieved_at": "2026-07-06", "documents": [{"path": "a.pdf"}]}
    corpus.save_manifest(path, manifest)
    assert corpus.load_manifest(path) == manifest
    # Trailing newline for clean diffs.
    assert path.read_text(encoding="utf-8").endswith("}\n")


def test_shipped_manifest_is_consistent() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = corpus.load_manifest(root / "example_schedules" / "manifest.json")
    for doc in manifest["documents"]:
        route = doc.get("expected_route", "deterministic")
        assert route in {"deterministic", "classification_review"}
        if route == "deterministic":
            assert doc["expected_minimum_eligibility_records"] > 0
        # Committed hash matches the committed file.
        path = root / "example_schedules" / doc["path"]
        assert corpus.sha256_of(path) == doc["sha256"]
    # Serialized form is what json.dumps(indent=2) produces (no drift).
    serialized = json.dumps(manifest, indent=2) + "\n"
    assert (root / "example_schedules" / "manifest.json").read_text(encoding="utf-8") == serialized
