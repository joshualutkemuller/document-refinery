from __future__ import annotations

import pytest

from document_refinery.agents.semantic import SemanticExtractor, SemanticValidator
from document_refinery.cli import _build_semantic_components


def test_cli_builds_separate_openai_semantic_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    extractor, validator = _build_semantic_components(
        provider="openai",
        extractor_model="gpt-5.5",
        validator_model="gpt-5.5",
        schema_version="eligibility-1.0.0",
        constitution_version="eligibility-1.1.0",
        timeout_seconds=5.0,
        max_retries=1,
    )

    assert isinstance(extractor, SemanticExtractor)
    assert isinstance(validator, SemanticValidator)
    assert extractor.model.session_id == "openai-extractor-session"
    assert validator.model.session_id == "openai-validator-session"
    assert extractor.model.session_id != validator.model.session_id


def test_cli_requires_complete_semantic_configuration() -> None:
    try:
        _build_semantic_components(
            provider="openai",
            extractor_model="gpt-5.5",
            validator_model=None,
            schema_version="eligibility-1.0.0",
            constitution_version="eligibility-1.1.0",
            timeout_seconds=5.0,
            max_retries=1,
        )
    except ValueError as error:
        assert "both extractor and validator" in str(error)
    else:
        raise AssertionError("incomplete semantic configuration should fail closed")
