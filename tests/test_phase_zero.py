from __future__ import annotations

from pathlib import Path

import pytest

from document_refinery.infrastructure.artifacts import ArtifactStore
from document_refinery.infrastructure.tasks import TaskStatus, TaskStore
from document_refinery.infrastructure.watcher import LandingZoneWatcher


def test_artifacts_are_content_addressed_and_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "schedule.txt"
    source.write_text("page one\fpage two", encoding="utf-8")
    store = ArtifactStore(tmp_path / "store")
    first = store.ingest(source, source="test")
    second = store.ingest(source, source="test")
    enriched, artifact = store.extract_text(first)

    assert first.doc_id == second.doc_id
    assert enriched.page_count == 2
    assert Path(enriched.file_uri).read_text(encoding="utf-8") == "page one\fpage two"
    assert Path(artifact.layout_uri).exists()


def test_task_store_enforces_workflow_order(tmp_path: Path) -> None:
    with TaskStore(tmp_path / "tasks.sqlite3") as tasks:
        tasks.create("doc-1")
        with pytest.raises(ValueError, match="invalid task transition"):
            tasks.transition("doc-1", TaskStatus.GOLD_LANDED)
        tasks.transition("doc-1", TaskStatus.CLASSIFIED)
        assert tasks.get("doc-1").status is TaskStatus.CLASSIFIED


def test_watcher_discovers_only_supported_visible_files(tmp_path: Path) -> None:
    (tmp_path / "b.pdf").touch()
    (tmp_path / "a.txt").touch()
    (tmp_path / ".hidden.txt").touch()
    (tmp_path / "ignored.csv").touch()
    (tmp_path / "README.md").touch()
    candidates = LandingZoneWatcher(tmp_path, source="drop").discover()
    assert [candidate.path.name for candidate in candidates] == ["a.txt", "b.pdf"]
