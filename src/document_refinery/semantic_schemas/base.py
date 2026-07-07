"""Schema specifications for semantic document extraction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


def identity_text(text: str) -> str:
    return text


@dataclass(frozen=True, slots=True)
class SemanticTextChunk:
    text: str
    chunk_id: str = "document"
    field_index_offset: int = 0


@dataclass(frozen=True, slots=True)
class SemanticSchemaSpec:
    doc_class: str
    schema_version: str
    constitution_version: str
    constitution: str
    schema_dictionary: str
    field_suffixes: frozenset[str]
    prepare_text: Callable[[str], str] = identity_text
    chunk_text: Callable[[str], tuple[SemanticTextChunk, ...]] | None = None
