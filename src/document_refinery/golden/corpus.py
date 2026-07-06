"""Provenance-tracked corpus manifest helpers.

The public corpus in ``example_schedules/`` is described by ``manifest.json``:
every document records its authoritative source URL, retrieval date, SHA-256
hash, parser profile, and expected pipeline route. These helpers compute hashes
and upsert manifest entries so a new document can be wired into the corpus in one
step (see ``scripts/add_corpus_document.py``).

Two routes are supported:

- ``deterministic`` — a known profile parses the document and it reaches
  ``gate_a_pending`` with at least ``expected_minimum_eligibility_records``.
- ``classification_review`` — an unknown layout (real CSAs, triparty schedules,
  central-bank haircut tables) that the classifier conservatively routes to
  owner review; without a configured semantic extractor the pipeline stops
  rather than force-parsing it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

Route = Literal["deterministic", "classification_review"]

_CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def build_entry(
    *,
    path: str,
    title: str,
    source_url: str,
    sha256: str,
    profile: str,
    expected_route: Route = "deterministic",
    expected_minimum_eligibility_records: int = 0,
    synthetic: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    if expected_route == "deterministic" and expected_minimum_eligibility_records <= 0:
        raise ValueError("deterministic documents require a positive expected record count")
    entry: dict[str, Any] = {
        "path": path,
        "title": title,
        "source_url": source_url,
        "sha256": sha256,
        "profile": profile,
        "expected_route": expected_route,
    }
    if expected_route == "deterministic":
        entry["expected_minimum_eligibility_records"] = expected_minimum_eligibility_records
    if synthetic:
        entry["synthetic"] = True
    if note:
        entry["note"] = note
    return entry


def upsert_entry(
    documents: list[dict[str, Any]],
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    """Replace an entry with the same ``path`` in place, or append a new one."""
    updated = [doc for doc in documents if doc.get("path") != entry["path"]]
    updated.append(entry)
    return updated


def load_manifest(path: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return manifest


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
