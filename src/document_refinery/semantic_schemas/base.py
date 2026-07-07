"""Schema specifications for semantic document extraction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemanticSchemaSpec:
    doc_class: str
    schema_version: str
    constitution_version: str
    constitution: str
    schema_dictionary: str
    field_suffixes: frozenset[str]
