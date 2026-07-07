"""Semantic extraction schema registry."""

from document_refinery.semantic_schemas.base import SemanticSchemaSpec
from document_refinery.semantic_schemas.registry import DEFAULT_SCHEMA, get_schema, schemas

__all__ = ["DEFAULT_SCHEMA", "SemanticSchemaSpec", "get_schema", "schemas"]
