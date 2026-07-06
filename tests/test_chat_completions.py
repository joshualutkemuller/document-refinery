from __future__ import annotations

import io
import json

import pytest

from document_refinery.agents.semantic import SemanticRequest
from document_refinery.cli import _build_semantic_components, build_parser
from document_refinery.infrastructure.chat_completions import (
    DEFAULT_OLLAMA_URL,
    ChatCompletionsSemanticModel,
    build_ollama_model,
    build_openai_compatible_model,
)


class _FakeResponse(io.BytesIO):
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _request() -> SemanticRequest:
    return SemanticRequest(
        session_id="s",
        system_prompt="system",
        user_payload="user",
        response_schema={"type": "object"},
        prompt_version="v1",
    )


def test_chat_completions_maps_payload_and_parses_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        captured["data"] = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        captured["headers"] = request.headers  # type: ignore[attr-defined]
        body = {
            "id": "chatcmpl-1",
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        return _FakeResponse(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    model = ChatCompletionsSemanticModel(
        model="llama3.1", base_url="http://host/v1/chat/completions",
        provider="ollama", session_id="s", api_key=None,
    )
    response = model.generate(_request())

    assert response.content == '{"ok": true}'
    assert response.provider == "ollama"
    assert response.usage == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    payload = captured["data"]
    assert payload["response_format"]["type"] == "json_schema"  # type: ignore[index]
    assert payload["response_format"]["json_schema"]["strict"] is True  # type: ignore[index]
    # No API key -> no Authorization header (Ollama).
    assert "Authorization" not in captured["headers"]  # type: ignore[operator]


def test_chat_completions_retries_transient_then_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import urllib.error

    calls = {"n": 0}

    def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        calls["n"] += 1
        raise urllib.error.HTTPError("url", 503, "busy", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    model = ChatCompletionsSemanticModel(
        model="m", base_url="http://host", provider="openai-compatible",
        session_id="s", api_key="k", max_retries=2,
    )
    with pytest.raises(RuntimeError, match="failed closed"):
        model.generate(_request())
    assert calls["n"] == 3  # initial + 2 retries


def test_ollama_factory_is_local_and_keyless() -> None:
    model = build_ollama_model(model="llama3.1", session_id="x")
    assert model.provider == "ollama"
    assert model.base_url == DEFAULT_OLLAMA_URL
    assert model._api_key is None  # local, no credentials


def test_openai_compatible_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_COMPATIBLE_API_KEY is required"):
        build_openai_compatible_model(
            model="m", base_url="https://api.groq.com/openai/v1/chat/completions", session_id="x"
        )


def test_openai_compatible_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "k")
    with pytest.raises(ValueError, match="base_url is required|base-url is required"):
        build_openai_compatible_model(model="m", base_url="", session_id="x")


def test_cli_builds_ollama_sessions_by_default() -> None:
    extractor, validator = _build_semantic_components(
        provider="ollama",
        base_url=None,
        extractor_model="llama3.1",
        validator_model="llama3.1",
        schema_version="eligibility-1.0.0",
        constitution_version="eligibility-1.1.0",
        timeout_seconds=5.0,
        max_retries=1,
    )
    assert extractor is not None and validator is not None
    assert extractor.model.provider == "ollama"
    assert extractor.model.session_id != validator.model.session_id


def test_cli_openai_compatible_requires_base_url() -> None:
    with pytest.raises(ValueError, match="--semantic-base-url is required"):
        _build_semantic_components(
            provider="openai-compatible",
            base_url=None,
            extractor_model="m",
            validator_model="m",
            schema_version="eligibility-1.0.0",
            constitution_version="eligibility-1.1.0",
            timeout_seconds=5.0,
            max_retries=1,
        )


def test_bare_semantic_provider_flag_defaults_to_ollama() -> None:
    args = build_parser().parse_args(
        ["run", "doc.txt", "--workspace", "ws", "--semantic-provider"]
    )
    assert args.semantic_provider == "ollama"
