"""Immutable, content-addressed bronze and text artifact storage."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from document_refinery.infrastructure.layout import (
    LayoutAdapter,
    TextLineLayoutAdapter,
    write_layout_artifact,
)


@dataclass(frozen=True, slots=True)
class BronzeDocument:
    doc_id: str
    source: str
    file_uri: str
    file_hash: str
    received_at: datetime
    counterparty: str | None = None
    doc_class_hint: str | None = None
    page_count: int | None = None
    text_artifact_uri: str | None = None
    layout_artifact_uri: str | None = None


@dataclass(frozen=True, slots=True)
class TextArtifact:
    doc_id: str
    text: str
    page_count: int
    text_uri: str
    layout_uri: str


class ArtifactStore:
    """Filesystem implementation with hash-addressed, never-overwritten objects."""

    def __init__(self, root: Path, *, layout_adapter: LayoutAdapter | None = None) -> None:
        self.root = root
        self.layout_adapter = layout_adapter or TextLineLayoutAdapter()
        self.raw_root = root / "bronze" / "raw"
        self.metadata_root = root / "bronze" / "metadata"
        self.text_root = root / "bronze" / "text"
        self.layout_root = root / "bronze" / "layout"
        for directory in (
            self.raw_root,
            self.metadata_root,
            self.text_root,
            self.layout_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def ingest(
        self,
        path: Path,
        *,
        source: str,
        counterparty: str | None = None,
        doc_class_hint: str | None = None,
        received_at: datetime | None = None,
    ) -> BronzeDocument:
        content_hash = _sha256(path)
        doc_id = f"doc-{content_hash[:24]}"
        raw_path = self.raw_root / f"{content_hash}{path.suffix.casefold()}"
        if not raw_path.exists():
            shutil.copyfile(path, raw_path)
        elif _sha256(raw_path) != content_hash:
            raise RuntimeError(f"immutable bronze collision at {raw_path}")

        metadata_path = self.metadata_root / f"{doc_id}.json"
        if metadata_path.exists():
            return _read_bronze(metadata_path)

        document = BronzeDocument(
            doc_id=doc_id,
            source=source,
            counterparty=counterparty,
            doc_class_hint=doc_class_hint,
            file_uri=str(raw_path),
            file_hash=content_hash,
            received_at=received_at or datetime.now(UTC),
        )
        _write_new_json(metadata_path, _bronze_json(document))
        return document

    def extract_text(self, document: BronzeDocument) -> tuple[BronzeDocument, TextArtifact]:
        source_path = Path(document.file_uri)
        suffix = source_path.suffix.casefold()
        if suffix in {".txt", ".md"}:
            pages = source_path.read_text(encoding="utf-8").split("\f")
        elif suffix == ".pdf":
            pages = _read_pdf(source_path)
        else:
            raise ValueError(f"unsupported document format: {suffix}")

        text = "\n\f\n".join(pages)
        text_path = self.text_root / f"{document.file_hash}.txt"
        layout_path = self.layout_root / f"{document.file_hash}.json"
        _write_new_text(text_path, text)
        layout = self.layout_adapter.analyze(
            doc_id=document.doc_id,
            path=source_path,
            pages=tuple(pages),
        )
        write_layout_artifact(layout_path, layout)
        artifact = TextArtifact(
            doc_id=document.doc_id,
            text=text,
            page_count=len(pages),
            text_uri=str(text_path),
            layout_uri=str(layout_path),
        )
        enriched = BronzeDocument(
            doc_id=document.doc_id,
            source=document.source,
            counterparty=document.counterparty,
            doc_class_hint=document.doc_class_hint,
            file_uri=document.file_uri,
            file_hash=document.file_hash,
            received_at=document.received_at,
            page_count=artifact.page_count,
            text_artifact_uri=artifact.text_uri,
            layout_artifact_uri=artifact.layout_uri,
        )
        metadata_path = self.metadata_root / f"{document.doc_id}.json"
        metadata_path.write_text(json.dumps(_bronze_json(enriched), indent=2) + "\n")
        return enriched, artifact


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new_text(path: Path, value: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != value:
            raise RuntimeError(f"immutable artifact collision at {path}")
        return
    path.write_text(value, encoding="utf-8")


def _write_new_json(path: Path, value: object) -> None:
    serialized = json.dumps(value, indent=2, sort_keys=True) + "\n"
    _write_new_text(path, serialized)


def _bronze_json(document: BronzeDocument) -> dict[str, object]:
    payload = asdict(document)
    payload["received_at"] = document.received_at.isoformat()
    return payload


def _read_bronze(path: Path) -> BronzeDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["received_at"] = datetime.fromisoformat(payload["received_at"])
    return BronzeDocument(**payload)


def _read_pdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDF extraction requires the 'pdf' project extra") from error
    return [(page.extract_text() or "") for page in PdfReader(path).pages]
